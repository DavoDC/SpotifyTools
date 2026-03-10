import json
import os
import logging
from datetime import datetime
from src.xml_parser import parse_library
from src.spotify import create_client, search_track, get_playlist_track_ids, add_tracks_to_playlist

BASE_DIR     = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
CONFIG_PATH  = os.path.join(BASE_DIR, "config", "config.json")
HISTORY_PATH = os.path.join(BASE_DIR, "data", "history.json")
LOG_DIR      = os.path.join(BASE_DIR, "data", "logs")
REPORT_DIR   = os.path.join(BASE_DIR, "data", "reports")

ADDED     = "added"
UNMATCHED = "unmatched"

REQUIRED_CONFIG_KEYS = [
    "spotify_client_id",
    "spotify_client_secret",
    "spotify_redirect_uri",
    "spotify_playlist_id",
    "audiomirror_path",
]

SAVE_INTERVAL  = 25   # save history every N tracks processed
FLUSH_INTERVAL = 100  # upload URIs to playlist every N URIs collected


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
    os.makedirs(os.path.dirname(path), exist_ok=True)
    with open(path, "w", encoding="utf-8") as f:
        json.dump(data, f, indent=2, ensure_ascii=False)


def track_key(track: dict) -> str:
    return f"{track['primary_artist']}|{track['title']}"


def validate_config(config: dict) -> list[str]:
    return [k for k in REQUIRED_CONFIG_KEYS if not config.get(k)]


def generate_report(history: dict, low_conf_this_run: list[dict], total_tracks: int) -> str:
    """Write a human-readable markdown report of all unmatched and low-confidence tracks.

    Unmatched = full history (cumulative across all runs).
    Low confidence = current run only (match detail isn't stored in history).
    Returns the path to the written report file.
    """
    os.makedirs(REPORT_DIR, exist_ok=True)
    timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
    report_path = os.path.join(REPORT_DIR, f"report_{timestamp}.md")

    # All tracks marked unmatched in history
    all_unmatched = sorted(
        [v["track"] for v in history.values() if v.get("state") == UNMATCHED],
        key=str.lower,
    )

    total_matched = sum(1 for v in history.values() if v.get("state") == ADDED)
    total_custom  = sum(1 for v in history.values() if v.get("state") == "custom")

    lines = [
        f"# SpotifyPlaylistGen — Match Report",
        f"",
        f"Generated: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}",
        f"",
        f"| Stat | Count |",
        f"|------|-------|",
        f"| Library total | {total_tracks} |",
        f"| Matched (added to playlist) | {total_matched} |",
        f"| Unmatched (not found on Spotify) | {len(all_unmatched)} |",
        f"| Low confidence (added, worth checking) | {len(low_conf_this_run)} |",
        f"| Custom (skipped by design) | {total_custom} |",
        f"",
    ]

    lines += [
        f"## Unmatched Tracks ({len(all_unmatched)})",
        f"",
        f"These could not be found on Spotify across all runs. Check manually — ",
        f"they may exist under a different name, or not be on Spotify at all.",
        f"",
    ]
    if all_unmatched:
        lines += [f"- {t}" for t in all_unmatched]
    else:
        lines.append("_None — all tracks matched!_")

    lines += [
        f"",
        f"## Low Confidence Matches ({len(low_conf_this_run)})",
        f"",
        f"These were added to the playlist this run, but the match was uncertain.",
        f"The Spotify track may not be the right version.",
        f"",
    ]
    if low_conf_this_run:
        lines.append("| Your Track | Matched To |")
        lines.append("|------------|------------|")
        for r in sorted(low_conf_this_run, key=lambda x: x["track"].lower()):
            lines.append(f"| {r['track']} | {r['matched']} |")
    else:
        lines.append("_None this run._")

    with open(report_path, "w", encoding="utf-8") as f:
        f.write("\n".join(lines) + "\n")

    return report_path


def main():
    start = datetime.now()
    log_file = setup_logging()
    logging.info("=== SpotifyPlaylistGen started ===")

    # --- Config ---
    config = load_json(CONFIG_PATH)
    if not config:
        logging.error(f"Config not found: {CONFIG_PATH}")
        print(f"ERROR: Config not found at {CONFIG_PATH}")
        input("\nPress Enter to exit...")
        return
    missing = validate_config(config)
    if missing:
        logging.error(f"Config missing required keys: {missing}")
        print(f"ERROR: Config is missing required keys: {missing}")
        print(f"  Edit {CONFIG_PATH} and fill in the missing values.")
        input("\nPress Enter to exit...")
        return

    history = load_json(HISTORY_PATH)

    print("\n=== SpotifyPlaylistGen ===")
    print(f"Log: {log_file}\n")

    # --- Stage 1: Parse library ---
    print("Stage 1/4: Reading AudioMirror library...")
    logging.info("Stage 1: Parsing XML library")
    try:
        tracks = parse_library(config["audiomirror_path"])
    except Exception as e:
        logging.error(f"Failed to parse library: {e}")
        print(f"ERROR: Could not read AudioMirror library: {e}")
        input("\nPress Enter to exit...")
        return
    if not tracks:
        print(f"ERROR: No tracks found at {config['audiomirror_path']}")
        input("\nPress Enter to exit...")
        return
    logging.info(f"  Found {len(tracks)} tracks")
    print(f"  Found {len(tracks)} tracks")

    # Classify library tracks by history state
    to_search   = []   # no history entry OR previously unmatched — need a Spotify search
    in_history  = []   # history says "added" — should be in playlist
    custom      = []   # history says "custom" — not on Spotify by design, always skip

    for t in tracks:
        state = history.get(track_key(t), {}).get("state")
        if state == ADDED:
            in_history.append(t)
        elif state == "custom":
            custom.append(t)
        else:
            # No entry, or "unmatched" — retry search
            to_search.append(t)

    print(f"  Already matched: {len(in_history)}  |  To search: {len(to_search)}  |  Custom (skip): {len(custom)}")
    logging.info(f"  Classified: matched={len(in_history)} to_search={len(to_search)} custom={len(custom)}")

    # --- Stage 2: Connect to Spotify ---
    print("\nStage 2/4: Connecting to Spotify...")
    logging.info("Stage 2: Connecting to Spotify")
    try:
        sp = create_client(config)
        user = sp.current_user()
        logging.info(f"  Authenticated as: {user.get('display_name')} ({user.get('id')})")
        print(f"  Authenticated as: {user.get('display_name')} ({user.get('id')})")
    except Exception as e:
        logging.error(f"Spotify auth failed: {e}")
        print(f"ERROR: Could not connect to Spotify: {e}")
        input("\nPress Enter to exit...")
        return
    try:
        existing_ids = get_playlist_track_ids(sp, config["spotify_playlist_id"])
        logging.info(f"  Playlist currently has {len(existing_ids)} tracks")
        print(f"  Playlist currently has {len(existing_ids)} tracks")
    except Exception as e:
        logging.error(f"Failed to read playlist: {e}")
        print(f"ERROR: Could not read playlist: {e}")
        input("\nPress Enter to exit...")
        return

    # Helper: upload URIs to playlist and update existing_ids cache
    flushed_total = 0

    def flush_to_playlist(uris: list[str], label: str = ""):
        nonlocal flushed_total
        if not uris:
            return
        try:
            add_tracks_to_playlist(sp, config["spotify_playlist_id"], uris)
            for uri in uris:
                existing_ids.add(uri.split(":")[-1])
            flushed_total += len(uris)
            logging.info(f"  Uploaded {len(uris)} tracks{' (' + label + ')' if label else ''} — playlist total: {len(existing_ids)}")
        except Exception as e:
            logging.error(f"Upload failed ({label}): {e}")
            print(f"WARNING: Could not upload batch to playlist: {e}")

    # --- Compute diff: matched tracks not yet in playlist ---
    # This is the core sync logic: library says "added", but playlist doesn't have it yet.
    missing_uris = [
        v["spotify_uri"]
        for k, v in history.items()
        if v.get("state") == ADDED
        and v.get("spotify_uri")
        and v["spotify_uri"].split(":")[-1] not in existing_ids
    ]

    already_in_playlist = sum(
        1 for v in history.values()
        if v.get("state") == ADDED
        and v.get("spotify_uri")
        and v["spotify_uri"].split(":")[-1] in existing_ids
    )

    print(f"\n  Sync status:")
    print(f"    {already_in_playlist} matched tracks already in playlist")
    print(f"    {len(missing_uris)} matched tracks missing from playlist (will upload)")
    print(f"    {len(to_search)} tracks still need searching")
    logging.info(f"  Sync: in_playlist={already_in_playlist} missing={len(missing_uris)} to_search={len(to_search)}")

    # --- Early exit: playlist is fully in sync and no new tracks to search ---
    if not missing_uris and not to_search:
        elapsed = (datetime.now() - start).seconds
        print(f"\nPlaylist is fully in sync with library. Nothing to do.")
        print(f"  {already_in_playlist} tracks in playlist | {len(custom)} custom (skipped) | {len(tracks)} library total")
        print(f"  Time: {elapsed}s  |  Log: {log_file}")
        logging.info(f"Up to date. InPlaylist={already_in_playlist} Time={elapsed}s")
        input("\nPress Enter to exit...")
        return

    # --- Upload missing matched tracks (sync recovery) ---
    if missing_uris:
        print(f"\n  Uploading {len(missing_uris)} previously matched tracks to playlist...")
        flush_to_playlist(missing_uris, "recovery")

    if not to_search:
        # Nothing left to search — recovery was the only work needed
        elapsed = (datetime.now() - start).seconds
        print(f"\nSync complete. Uploaded {flushed_total} previously matched tracks.")
        print(f"  Time: {elapsed}s  |  Log: {log_file}")
        logging.info(f"Recovery only. Uploaded={flushed_total} Time={elapsed}s")
        input("\nPress Enter to exit...")
        return

    # --- Stage 3: Search for undecided / previously unmatched tracks ---
    print(f"\nStage 3/4: Searching Spotify for {len(to_search)} tracks...")
    logging.info(f"Stage 3: Searching {len(to_search)} tracks")

    to_add_uris  = []
    needs_review = []
    added = unmatched = errors = 0
    history_dirty = False

    for i, track in enumerate(to_search, 1):
        key = track_key(track)

        if i % 100 == 0 or i == 1:
            print(f"  [{i}/{len(to_search)}] Searching... (matched={added} unmatched={unmatched} errors={errors} uploaded={flushed_total})")

        try:
            matches = search_track(sp, track)
        except Exception as e:
            logging.warning(f"Search failed for {track['primary_artist']} - {track['title']}: {e}")
            errors += 1
            continue

        best       = matches[0] if matches else None
        confidence = best["confidence"] if best else "none"

        if confidence in ("exact", "high"):
            decision, uri = ADDED, best["uri"]
        elif confidence == "low":
            decision, uri = ADDED, best["uri"]
            needs_review.append({
                "track":      f"{track['primary_artist']} - {track['title']}",
                "matched":    f"{best['artist']} - {best['name']} ({best['album']})",
                "confidence": "low",
            })
        else:
            decision, uri = UNMATCHED, None
            needs_review.append({
                "track":      f"{track['primary_artist']} - {track['title']}",
                "matched":    None,
                "confidence": "none",
            })

        history[key] = {
            "state":       decision,
            "track":       f"{track['primary_artist']} - {track['title']}",
            "spotify_uri": uri,
            "decided_at":  datetime.now().isoformat(),
        }
        history_dirty = True

        if decision == ADDED and uri:
            if uri.split(":")[-1] not in existing_ids:
                to_add_uris.append(uri)
            added += 1
        else:
            unmatched += 1

        logging.info(f"[{confidence.upper()}] {track['primary_artist']} - {track['title']}")

        # Periodic history save
        if i % SAVE_INTERVAL == 0 and history_dirty:
            save_json(HISTORY_PATH, history)
            history_dirty = False

        # Periodic playlist flush — progress is safe even if run is interrupted
        if len(to_add_uris) >= FLUSH_INTERVAL:
            flush_to_playlist(to_add_uris, f"batch at track {i}")
            to_add_uris = []

    # Final history save
    if history_dirty:
        save_json(HISTORY_PATH, history)

    # --- Stage 4: Final flush of remaining matched tracks ---
    remaining = len(to_add_uris)
    print(f"\nStage 4/4: Final upload of {remaining} tracks (already uploaded {flushed_total})...")
    logging.info(f"Stage 4: Final upload {remaining} tracks")
    flush_to_playlist(to_add_uris, "final")

    # --- Summary ---
    elapsed   = (datetime.now() - start).seconds
    low_conf  = [r for r in needs_review if r["confidence"] == "low"]
    no_match  = [r for r in needs_review if r["confidence"] == "none"]

    print(f"""
=== Summary ===
  Library total:  {len(tracks)}
  Already in sync:{already_in_playlist} (were already in playlist)
  Recovered:      {len(missing_uris)} (matched in history, now uploaded)
  Newly matched:  {added} (searched and matched this run)
  Unmatched:      {unmatched} (not found on Spotify — will retry next run)
  Search errors:  {errors}
  Custom (skip):  {len(custom)}
  Total uploaded: {flushed_total}
  Time:           {elapsed}s
  Log:            {log_file}
""")

    if no_match:
        print(f"=== Could Not Match ({len(no_match)}) ===")
        for r in no_match:
            print(f"  - {r['track']}")

    if low_conf:
        print(f"\n=== Low Confidence - Worth Checking ({len(low_conf)}) ===")
        for r in low_conf:
            print(f"  - {r['track']}")
            print(f"      matched to: {r['matched']}")

    logging.info(f"Done. InSync={already_in_playlist} Recovered={len(missing_uris)} Added={added} Unmatched={unmatched} Errors={errors} Uploaded={flushed_total} Time={elapsed}s")

    report_path = generate_report(history, low_conf, total_tracks=len(tracks))
    print(f"\nMatch report written to:\n  {report_path}")
    logging.info(f"Report: {report_path}")

    input("\nPress Enter to exit...")


if __name__ == "__main__":
    main()
