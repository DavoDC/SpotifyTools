import json
import os
import logging
import time
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
        f"## Low Confidence — Not Added ({len(low_conf_this_run)})",
        f"",
        f"A partial Spotify match was found but confidence was too low to add automatically.",
        f"Check each one manually and add to the playlist if correct.",
        f"These will be retried on the next run.",
        f"",
    ]
    if low_conf_this_run:
        lines.append("| Your Track | Closest Spotify Match |")
        lines.append("|------------|-----------------------|")
        for r in sorted(low_conf_this_run, key=lambda x: x["track"].lower()):
            lines.append(f"| {r['track']} | {r['matched']} |")
    else:
        lines.append("_None this run._")

    with open(report_path, "w", encoding="utf-8") as f:
        f.write("\n".join(lines) + "\n")

    return report_path


def _eta(start_time: datetime, done: int, total: int) -> str:
    """Return a human-readable ETA string, e.g. '~4m 30s'."""
    if done == 0:
        return "..."
    elapsed = (datetime.now() - start_time).total_seconds()
    rate = done / elapsed            # tracks per second
    remaining = (total - done) / rate
    m, s = divmod(int(remaining), 60)
    return f"~{m}m {s}s" if m else f"~{s}s"


def main():
    start = datetime.now()
    log_file = setup_logging()
    logging.info("=== SpotifyPlaylistGen started ===")

    # --- Config ---
    config = load_json(CONFIG_PATH)
    if not config:
        logging.error(f"Config not found: {CONFIG_PATH}")
        print(f"\nERROR: Config not found at {CONFIG_PATH}")
        input("\nPress Enter to exit...")
        return
    missing = validate_config(config)
    if missing:
        logging.error(f"Config missing required keys: {missing}")
        print(f"\nERROR: Config is missing required keys: {missing}")
        print(f"  Edit {CONFIG_PATH} and fill in the missing values.")
        input("\nPress Enter to exit...")
        return

    history = load_json(HISTORY_PATH)

    print(f"\n{'='*60}")
    print(f"  SpotifyPlaylistGen")
    print(f"  Log: {log_file}")
    print(f"{'='*60}")

    # -------------------------------------------------------------------------
    # Stage 1: Parse library
    # Reads AudioMirror XML files and classifies each track:
    #   - "added"    → history says it's matched; should already be in playlist
    #   - "unmatched"→ tried before, not found; will retry this run
    #   - (none)     → brand new track, never searched
    #   - "custom"   → user marked as not-on-Spotify; always skipped
    # -------------------------------------------------------------------------
    print(f"\n[Stage 1/4] Reading local music library...")
    logging.info("Stage 1: Parsing XML library")
    try:
        tracks = parse_library(config["audiomirror_path"])
    except Exception as e:
        logging.error(f"Failed to parse library: {e}")
        print(f"  ERROR: Could not read AudioMirror library: {e}")
        input("\nPress Enter to exit...")
        return
    if not tracks:
        print(f"  ERROR: No tracks found at {config['audiomirror_path']}")
        input("\nPress Enter to exit...")
        return

    to_search  = []
    in_history = []
    custom     = []
    for t in tracks:
        state = history.get(track_key(t), {}).get("state")
        if state == ADDED:
            in_history.append(t)
        elif state == "custom":
            custom.append(t)
        else:
            to_search.append(t)

    logging.info(f"  Found {len(tracks)} tracks — matched={len(in_history)} to_search={len(to_search)} custom={len(custom)}")
    print(f"  Found {len(tracks)} tracks in library")
    print(f"  Already matched : {len(in_history):>5}  (saved in history, should be in playlist)")
    print(f"  Need searching  : {len(to_search):>5}  (new tracks or previous 'not found')")
    print(f"  Custom / skip   : {len(custom):>5}  (manually marked as not on Spotify)")

    # -------------------------------------------------------------------------
    # Stage 2: Connect to Spotify + compute sync diff
    # Reads the live playlist and computes:
    #   - tracks in history["added"] that are MISSING from the playlist (need upload)
    #   - tracks already confirmed present (nothing to do for them)
    # -------------------------------------------------------------------------
    print(f"\n[Stage 2/4] Connecting to Spotify...")
    logging.info("Stage 2: Connecting to Spotify")
    try:
        sp = create_client(config)
        user = sp.current_user()
        logging.info(f"  Authenticated as: {user.get('display_name')} ({user.get('id')})")
        print(f"  Logged in as: {user.get('display_name')} ({user.get('id')})")
    except Exception as e:
        logging.error(f"Spotify auth failed: {e}")
        print(f"  ERROR: Could not connect to Spotify: {e}")
        input("\nPress Enter to exit...")
        return

    print(f"  Reading playlist contents...", end="", flush=True)
    try:
        existing_ids = get_playlist_track_ids(sp, config["spotify_playlist_id"])
        logging.info(f"  Playlist currently has {len(existing_ids)} tracks")
        print(f" {len(existing_ids)} tracks found")
    except Exception as e:
        logging.error(f"Failed to read playlist: {e}")
        print(f"\n  ERROR: Could not read playlist: {e}")
        input("\nPress Enter to exit...")
        return

    # Helper: upload URIs to playlist and update existing_ids cache
    flushed_total = 0

    def flush_to_playlist(uris: list[str], label: str = ""):
        nonlocal flushed_total
        if not uris:
            return
        print(f"\n  --> Uploading {len(uris)} tracks to Spotify playlist...", end="", flush=True)
        try:
            add_tracks_to_playlist(sp, config["spotify_playlist_id"], uris)
            for uri in uris:
                existing_ids.add(uri.split(":")[-1])
            flushed_total += len(uris)
            print(f" done. Playlist now has {len(existing_ids)} tracks.")
            logging.info(f"  Uploaded {len(uris)} tracks ({label}) — playlist total: {len(existing_ids)}")
        except Exception as e:
            print(f" FAILED: {e}")
            logging.error(f"Upload failed ({label}): {e}")

    # Diff: matched in history but missing from live playlist
    missing_uris = [
        v["spotify_uri"]
        for v in history.values()
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

    print(f"\n  Sync diff:")
    print(f"    {already_in_playlist:>5}  already in playlist  (no action needed)")
    print(f"    {len(missing_uris):>5}  matched but missing  (will upload now)")
    print(f"    {len(to_search):>5}  not yet searched     (will search in Stage 3)")
    logging.info(f"  Sync: in_playlist={already_in_playlist} missing={len(missing_uris)} to_search={len(to_search)}")

    # -------------------------------------------------------------------------
    # Early exit: everything is already in sync
    # -------------------------------------------------------------------------
    if not missing_uris and not to_search:
        elapsed = int((datetime.now() - start).total_seconds())
        print(f"\n{'='*60}")
        print(f"  Playlist is fully in sync. Nothing to do.")
        print(f"  {already_in_playlist} tracks in playlist | {len(custom)} custom | {len(tracks)} library total")
        print(f"  Time: {elapsed}s")
        print(f"{'='*60}")
        logging.info(f"Up to date. InPlaylist={already_in_playlist} Time={elapsed}s")
        input("\nPress Enter to exit...")
        return

    # -------------------------------------------------------------------------
    # Recovery: upload history-matched tracks missing from playlist
    # These were matched in a previous run but never made it to Spotify
    # (e.g. interrupted run, or previous payload bug)
    # -------------------------------------------------------------------------
    if missing_uris:
        flush_to_playlist(missing_uris, "recovery")
        if to_search:
            print(f"  Waiting 15s before searching (prevents rate limiting after bulk upload)...")
            for i in range(15, 0, -1):
                print(f"\r  Waiting {i}s... ", end="", flush=True)
                time.sleep(1)
            print(f"\r  Ready.              ")

    if not to_search:
        elapsed = int((datetime.now() - start).total_seconds())
        print(f"\n  All tracks already matched. Sync complete.")
        print(f"  Uploaded {flushed_total} previously matched tracks.")
        logging.info(f"Recovery only. Uploaded={flushed_total} Time={elapsed}s")
        input("\nPress Enter to exit...")
        return

    # -------------------------------------------------------------------------
    # Stage 3: Search Spotify for unmatched tracks
    # For each track, searches Spotify and rates the match:
    #   EXACT  — title, artist and album all match
    #   HIGH   — title + artist match (different album/version)
    #   LOW    — partial match (title matches but artist differs, etc.)
    #   NONE   — nothing found at all
    # EXACT/HIGH/LOW are all added to playlist. LOW flagged in report.
    # NONE is saved to history and retried on next run.
    # Flushes to Spotify every 100 matched tracks (progress is never lost).
    # Saves history to disk every 25 tracks.
    # -------------------------------------------------------------------------
    n = len(to_search)
    print(f"\n[Stage 3/4] Searching Spotify for {n} tracks...")
    print(f"  (EXACT/HIGH/LOW = added to playlist | NONE = not found, retried next run)")
    print(f"  Each track shown as it's searched. Progress auto-saves every 25 tracks.\n")
    logging.info(f"Stage 3: Searching {n} tracks")

    to_add_uris  = []
    needs_review = []
    added = unmatched = errors = 0
    history_dirty = False
    search_start = datetime.now()

    CONF_SYMBOL = {"exact": "✓ EXACT", "high": "✓ HIGH ", "low": "✗ LOW  ", "none": "✗ NONE "}

    for i, track in enumerate(to_search, 1):
        key   = track_key(track)
        label = f"{track['primary_artist']} - {track['title']}"

        # Live updating line: show what's being searched right now
        print(f"\r  [{i:>{len(str(n))}}/{n}] {label[:55]:<55}", end="", flush=True)

        try:
            matches = search_track(sp, track)
        except Exception as e:
            print(f"  ERROR")
            logging.warning(f"Search failed for {label}: {e}")
            errors += 1
            time.sleep(0.1)
            continue

        best       = matches[0] if matches else None
        confidence = best["confidence"] if best else "none"
        symbol     = CONF_SYMBOL.get(confidence, "?")

        # EXACT/HIGH: quiet success, overwrite line. LOW/NONE: print permanently so user sees rejections.
        if confidence in ("exact", "high"):
            print(f"  {symbol}", end="\r", flush=True)
        elif confidence == "low":
            print(f"  {symbol}  (partial: {best['artist']} - {best['name']})")
        else:
            print(f"  {symbol}")

        if confidence in ("exact", "high"):
            decision, uri = ADDED, best["uri"]
        elif confidence == "low":
            decision, uri = UNMATCHED, None   # not added — partial match only
            needs_review.append({
                "track":      label,
                "matched":    f"{best['artist']} - {best['name']} ({best['album']})",
                "confidence": "low",
            })
        else:
            decision, uri = UNMATCHED, None
            needs_review.append({"track": label, "matched": None, "confidence": "none"})

        history[key] = {
            "state":       decision,
            "track":       label,
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

        logging.info(f"[{confidence.upper()}] {label}")

        time.sleep(0.1)  # 100ms between searches — prevents rate limiting (~10/s max)

        # Periodic history save
        if i % SAVE_INTERVAL == 0 and history_dirty:
            save_json(HISTORY_PATH, history)
            history_dirty = False

        # Periodic playlist flush — print on new line, resume \r progress after
        if len(to_add_uris) >= FLUSH_INTERVAL:
            print()  # end the \r line before printing upload status
            flush_to_playlist(to_add_uris, f"batch at {i}/{n}")
            to_add_uris = []
            eta = _eta(search_start, i, n)
            print(f"  Progress: {i}/{n} searched | {added} matched | {unmatched} not found | {errors} errors | ETA {eta}")

    print()  # end final \r line

    # Final history save
    if history_dirty:
        save_json(HISTORY_PATH, history)

    # -------------------------------------------------------------------------
    # Stage 4: Final flush of any remaining matched tracks
    # -------------------------------------------------------------------------
    print(f"\n[Stage 4/4] Final upload...")
    logging.info(f"Stage 4: Final upload {len(to_add_uris)} tracks")
    flush_to_playlist(to_add_uris, "final")

    # -------------------------------------------------------------------------
    # Summary
    # -------------------------------------------------------------------------
    elapsed  = int((datetime.now() - start).total_seconds())
    low_conf = [r for r in needs_review if r["confidence"] == "low"]
    no_match = [r for r in needs_review if r["confidence"] == "none"]

    print(f"\n{'='*60}")
    print(f"  Run complete in {elapsed}s")
    print(f"{'='*60}")
    print(f"  Library total      : {len(tracks)}")
    print(f"  Already in playlist: {already_in_playlist}  (confirmed present, no action)")
    print(f"  Recovered          : {len(missing_uris)}  (matched in history, uploaded now)")
    print(f"  Newly matched      : {added}  (EXACT or HIGH confidence — added to playlist)")
    print(f"  Not added          : {unmatched}  (LOW confidence or no match — see report, retried next run)")
    print(f"  Search errors      : {errors}")
    print(f"  Custom / skipped   : {len(custom)}")
    print(f"  Total uploaded     : {flushed_total}")
    print(f"{'='*60}")

    logging.info(f"Done. InSync={already_in_playlist} Recovered={len(missing_uris)} Added={added} Unmatched={unmatched} Errors={errors} Uploaded={flushed_total} Time={elapsed}s")

    report_path = generate_report(history, low_conf, total_tracks=len(tracks))
    print(f"\n  Match report: {report_path}")
    logging.info(f"Report: {report_path}")

    input("\nPress Enter to exit...")


if __name__ == "__main__":
    main()
