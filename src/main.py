import json
import os
import logging
from datetime import datetime
from src.xml_parser import parse_library
from src.spotify import create_client, search_track, get_playlist_track_ids, add_tracks_to_playlist

BASE_DIR    = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
CONFIG_PATH = os.path.join(BASE_DIR, "config", "config.json")
HISTORY_PATH = os.path.join(BASE_DIR, "data", "history.json")
LOG_DIR     = os.path.join(BASE_DIR, "data", "logs")

# States
ADDED = "added"
CUSTOM = "custom"
REJECTED = "rejected"
UNMATCHED = "unmatched"
QUIT = "quit"


def setup_logging():
    os.makedirs(LOG_DIR, exist_ok=True)
    log_file = os.path.join(LOG_DIR, f"run_{datetime.now().strftime('%Y%m%d_%H%M%S')}.log")
    logging.basicConfig(
        level=logging.INFO,
        format="%(asctime)s %(message)s",
        handlers=[
            logging.FileHandler(log_file),
            logging.StreamHandler(),
        ]
    )
    return log_file


def load_json(path):
    if os.path.exists(path):
        with open(path, "r", encoding="utf-8") as f:
            return json.load(f)
    return {}


def save_json(path, data):
    with open(path, "w", encoding="utf-8") as f:
        json.dump(data, f, indent=2, ensure_ascii=False)


def track_key(track: dict) -> str:
    return f"{track['primary_artist']}|{track['title']}"


def review_match(track: dict, matches: list[dict]) -> tuple[str, str | None]:
    print(f"\n  Track: {track['primary_artist']} — {track['title']} ({track['album']})")

    if not matches or matches[0]["confidence"] == "none":
        print("  No good matches found.")
    else:
        print(f"  Best match [{matches[0]['confidence'].upper()}]: "
              f"{matches[0]['artist']} — {matches[0]['name']} ({matches[0]['album']})")
        if len(matches) > 1:
            print("  Alternatives:")
            for i, m in enumerate(matches[1:], 1):
                print(f"    {i}. [{m['confidence'].upper()}] {m['artist']} — {m['name']} ({m['album']})")

    print()
    print("  Options: [y] accept best  [1-4] pick alternative  [c] custom track  [s] skip/reject  [q] quit & save")
    choice = input("  > ").strip().lower()

    if choice == "q":
        return QUIT, None
    elif choice == "y" and matches:
        return ADDED, matches[0]["uri"]
    elif choice in ("1", "2", "3", "4"):
        idx = int(choice)
        if idx < len(matches):
            return ADDED, matches[idx]["uri"]
        print("  Invalid choice, skipping.")
        return REJECTED, None
    elif choice == "c":
        return CUSTOM, None
    else:
        return REJECTED, None


def main():
    start = datetime.now()
    log_file = setup_logging()
    logging.info(f"=== SpotifyPlaylistGen started ===")

    # Load config
    config = load_json(CONFIG_PATH)
    if not config:
        print(f"ERROR: {CONFIG_PATH} not found.")
        return

    # Load history
    history = load_json(HISTORY_PATH)

    print("\n=== SpotifyPlaylistGen ===")
    print(f"Log: {log_file}\n")

    # Stage 1: Parse library
    print("Stage 1/4: Reading AudioMirror library...")
    logging.info("Stage 1: Parsing XML library")
    tracks = parse_library(config["audiomirror_path"])
    logging.info(f"  Found {len(tracks)} tracks")
    print(f"  Found {len(tracks)} tracks")

    # Stage 2: Connect to Spotify
    print("\nStage 2/4: Connecting to Spotify...")
    logging.info("Stage 2: Connecting to Spotify")
    sp = create_client(config)
    user = sp.current_user()
    logging.info(f"  Authenticated as: {user['display_name']} ({user['id']})")
    print(f"  Authenticated as: {user['display_name']} ({user['id']})")
    existing_ids = get_playlist_track_ids(sp, config["spotify_playlist_id"])
    logging.info(f"  Playlist already has {len(existing_ids)} tracks")
    print(f"  Playlist already has {len(existing_ids)} tracks")

    # Stage 3: Match tracks
    print("\nStage 3/4: Matching tracks...")
    logging.info("Stage 3: Matching tracks")

    to_add_uris = []
    skipped = added = custom = unmatched = rejected = 0

    for i, track in enumerate(tracks, 1):
        key = track_key(track)
        state = history.get(key, {}).get("state")

        # Skip already resolved
        if state == ADDED:
            skipped += 1
            continue
        if state == CUSTOM:
            skipped += 1
            continue

        logging.info(f"Processing: {track['primary_artist']} — {track['title']}")

        matches = search_track(sp, track)

        # Auto-accept exact matches without prompting
        if matches and matches[0]["confidence"] == "exact":
            decision, uri = ADDED, matches[0]["uri"]
            print(f"\n[{i}/{len(tracks)}] AUTO: {track['primary_artist']} — {track['title']}")
        else:
            print(f"\n[{i}/{len(tracks)}]", end="")
            decision, uri = review_match(track, matches)

        if decision == QUIT:
            logging.info("User quit. Progress saved.")
            print("\nProgress saved. Re-run to continue from where you left off.")
            break

        history[key] = {
            "state": decision,
            "track": f"{track['primary_artist']} — {track['title']}",
            "spotify_uri": uri,
            "decided_at": datetime.now().isoformat(),
        }
        save_json(HISTORY_PATH, history)

        if decision == ADDED and uri:
            spotify_id = uri.split(":")[-1]
            if spotify_id not in existing_ids:
                to_add_uris.append(uri)
            added += 1
        elif decision == CUSTOM:
            custom += 1
        elif decision == REJECTED:
            rejected += 1

        if not matches or matches[0]["confidence"] == "none":
            history[key]["state"] = UNMATCHED
            save_json(HISTORY_PATH, history)
            unmatched += 1

    # Stage 4: Add to playlist
    print(f"\nStage 4/4: Adding {len(to_add_uris)} new tracks to playlist...")
    logging.info(f"Stage 4: Adding {len(to_add_uris)} tracks to playlist")

    if to_add_uris:
        add_tracks_to_playlist(sp, config["spotify_playlist_id"], to_add_uris)
        print(f"  Done!")
    else:
        print("  Nothing new to add.")

    # Summary
    elapsed = (datetime.now() - start).seconds
    print(f"""
=== Summary ===
  Total tracks:   {len(tracks)}
  Skipped:        {skipped} (already decided)
  Added:          {added}
  Custom tracks:  {custom}
  Unmatched:      {unmatched}
  Rejected:       {rejected}
  Time:           {elapsed}s
  Log:            {log_file}
""")
    logging.info(f"Done. Added={added} Custom={custom} Unmatched={unmatched} Rejected={rejected} Time={elapsed}s")
    input("Press Enter to exit...")


if __name__ == "__main__":
    main()
