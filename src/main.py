"""SpotifyPlaylistGen — CLI entrypoint.

Orchestrates the 4-stage playlist sync pipeline:
  Stage 1: Parse XML library
  Stage 2: Connect + reconcile (compute diff)
  Stage 3: Search Spotify for unmatched tracks
  Stage 4: Apply changes (add/remove/report)
"""

import logging
import os
import sys
import time
from datetime import datetime

from src.config import load_config, validate_config, CONFIG_PATH
from src.xml_parser import parse_library
from src.history_store import HistoryStore
from src.lockfile import LockFile
from src.reconciler import reconcile, MAX_SEARCH_ATTEMPTS
from src.report_generator import generate_report
from src.spotify_interface import SpotifyInterface

BASE_DIR = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
HISTORY_PATH = os.path.join(BASE_DIR, "data", "history.json")
LOCK_PATH = os.path.join(BASE_DIR, "data", "run.lock")
LOG_DIR = os.path.join(BASE_DIR, "data", "logs")
REPORT_DIR = os.path.join(BASE_DIR, "data", "reports")

ADDED = "added"
UNMATCHED = "unmatched"

SAVE_INTERVAL = 25
FLUSH_INTERVAL = 100

SEARCH_DELAY_S = 0.1
POST_BULK_DELAY_S = 15


def _wait_for_exit():
    """Prompt user to press Enter. Handles piped/non-interactive gracefully."""
    try:
        input("\nPress Enter to exit...")
    except EOFError:
        pass


def track_key(track: dict) -> str:
    return f"{track['primary_artist']}|{track['title']}"


def setup_logging(log_dir: str = LOG_DIR):
    os.makedirs(log_dir, exist_ok=True)
    log_file = os.path.join(log_dir, f"run_{datetime.now().strftime('%Y%m%d_%H%M%S')}.log")

    # File handler: DEBUG level — captures EVERYTHING for post-mortem
    file_handler = logging.FileHandler(log_file, encoding="utf-8")
    file_handler.setLevel(logging.DEBUG)
    file_handler.setFormatter(logging.Formatter("%(asctime)s %(message)s"))

    # Terminal handler: INFO level — cleaner output, skip per-track search detail
    stream_handler = logging.StreamHandler()
    stream_handler.setLevel(logging.INFO)
    stream_handler.setFormatter(logging.Formatter("%(asctime)s %(message)s"))

    logging.basicConfig(level=logging.DEBUG, handlers=[file_handler, stream_handler])
    return log_file


def _eta(start_time: datetime, done: int, total: int) -> str:
    if done == 0:
        return "..."
    elapsed = (datetime.now() - start_time).total_seconds()
    rate = done / elapsed
    remaining = (total - done) / rate
    m, s = divmod(int(remaining), 60)
    return f"~{m}m {s}s" if m else f"~{s}s"


def run_pipeline(client: SpotifyInterface,
                 config: dict,
                 history_store: HistoryStore,
                 history_path: str = HISTORY_PATH,
                 report_dir: str = REPORT_DIR,
                 search_delay: float = SEARCH_DELAY_S,
                 interactive: bool = True) -> dict:
    """Run the full sync pipeline. Returns summary dict for testing.

    Args:
        client: SpotifyInterface implementation (real or simulated)
        config: validated config dict
        history_store: HistoryStore instance
        history_path: path to history.json (for periodic saves)
        report_dir: directory for reports
        search_delay: seconds between search calls (0 for tests)
        interactive: if True, shows progress and waits for Enter at end
    """
    start = datetime.now()

    # Load history + create backup
    history = history_store.load()
    history_store.create_backup()

    # ── Stage 1: Parse library ───────────────────────────────────────────
    print(f"\n[Stage 1/4] Reading local music library...")
    logging.info("Stage 1: Parsing XML library")
    try:
        tracks = parse_library(config["audiomirror_path"])
    except Exception as e:
        logging.error(f"Failed to parse library: {e}")
        print(f"  ERROR: Could not read AudioMirror library: {e}")
        return {"error": str(e)}

    if not tracks:
        print(f"  ERROR: No tracks found at {config['audiomirror_path']}")
        return {"error": "no tracks found"}

    logging.info(f"  Found {len(tracks)} tracks in library")
    print(f"  Found {len(tracks)} tracks in library")

    # ── Stage 2: Connect + Reconcile ─────────────────────────────────────
    print(f"\n[Stage 2/4] Reading playlist & computing sync plan...")
    logging.info("Stage 2: Connecting to Spotify")

    try:
        user = client.current_user()
        logging.info(f"  Authenticated as: {user.get('display_name')}")
        print(f"  Logged in as: {user.get('display_name')} ({user.get('id')})")
    except Exception as e:
        logging.error(f"Auth failed: {e}")
        print(f"  ERROR: Could not authenticate: {e}")
        return {"error": str(e)}

    playlist_id = config["spotify_playlist_id"]

    try:
        playlist_uris = client.get_playlist_uris(playlist_id)
        print(f"  Playlist has {len(playlist_uris)} unique tracks")
    except Exception as e:
        logging.error(f"Failed to read playlist: {e}")
        print(f"  ERROR: Could not read playlist: {e}")
        return {"error": str(e)}

    # Deduplicate
    dupes = client.find_duplicates(playlist_id)
    if dupes:
        dupe_uris = []
        for uri, count in dupes.items():
            dupe_uris.extend([uri] * count)
        print(f"  Removing {len(dupe_uris)} duplicates...")
        client.remove_tracks(playlist_id, dupe_uris)
        playlist_uris = client.get_playlist_uris(playlist_id)
        print(f"  Playlist now has {len(playlist_uris)} tracks")

    # Compute reconciliation plan
    plan = reconcile(tracks, history, playlist_uris, track_key)

    print(f"\n  Sync plan:")
    print(f"    {plan.skipped_synced:>5}  already in sync")
    print(f"    {len(plan.to_recover):>5}  matched but missing from playlist (will recover)")
    print(f"    {len(plan.to_search):>5}  need searching")
    print(f"    {len(plan.to_remove):>5}  in playlist but not in library (will remove)")
    print(f"    {plan.skipped_custom:>5}  custom/skipped")
    print(f"    {plan.skipped_exhausted:>5}  exhausted (gave up after {MAX_SEARCH_ATTEMPTS} attempts)")

    # Early exit
    if not plan.has_work:
        elapsed = int((datetime.now() - start).total_seconds())
        print(f"\n  Playlist is fully in sync. Nothing to do. ({elapsed}s)")
        logging.info(f"Up to date. Time={elapsed}s")
        if interactive:
            _wait_for_exit()
        return {
            "library_total": len(tracks),
            "synced": plan.skipped_synced,
            "searched": 0, "added": 0, "unmatched": 0,
            "recovered": 0, "removed": 0, "errors": 0,
        }

    # ── Recovery: re-add history-matched tracks missing from playlist ────
    recovered_list = []
    if plan.to_recover:
        recovery_uris = [r["uri"] for r in plan.to_recover]
        print(f"\n  Recovering {len(recovery_uris)} missing tracks...")
        result = client.add_tracks(playlist_id, recovery_uris)
        for uri in result.succeeded:
            playlist_uris.add(uri)
        recovered_list = plan.to_recover
        logging.info(f"  Recovery: {len(result.succeeded)} succeeded, {len(result.failed)} failed")

        if plan.to_search and search_delay > 0:
            print(f"  Waiting {POST_BULK_DELAY_S}s before searching...")
            time.sleep(POST_BULK_DELAY_S)

    # ── Remove tracks not in library ─────────────────────────────────────
    removed_uris = []
    if plan.to_remove:
        print(f"\n  Removing {len(plan.to_remove)} tracks not in library...")
        result = client.remove_tracks(playlist_id, plan.to_remove)
        removed_uris = plan.to_remove
        for uri in plan.to_remove:
            playlist_uris.discard(uri)
        logging.info(f"  Removed {result.removed_count} tracks")

    # ── Stage 3: Search & Match ──────────────────────────────────────────
    n = len(plan.to_search)
    added_count = 0
    unmatched_count = 0
    error_count = 0
    low_confidence = []
    to_add_uris = []
    pending_tracks = {}  # uri -> (key, label, confidence, source_file) — awaiting Spotify confirmation
    history_dirty = False
    search_start = datetime.now()

    if n > 0:
        print(f"\n[Stage 3/4] Searching Spotify for {n} tracks...")
        logging.info(f"Stage 3: Searching {n} tracks")

        CONF_SYMBOL = {"exact": "+ EXACT", "high": "+ HIGH ", "low": "- LOW  ", "none": "- NONE "}

        for i, t in enumerate(plan.to_search, 1):
            key = track_key(t)
            label = f"{t['primary_artist']} - {t['title']}"

            if interactive:
                print(f"  [{i:>{len(str(n))}}/{n}] {label[:55]:<55}", end="", flush=True)

            try:
                matches = client.search_track(t)
            except Exception as e:
                logging.warning(f"Search failed for {label}: {e}")
                error_count += 1
                if search_delay > 0:
                    time.sleep(search_delay)
                continue

            best = matches[0] if matches else None
            confidence = best["confidence"] if best else "none"
            symbol = CONF_SYMBOL.get(confidence, "?")

            if interactive:
                if confidence in ("exact", "high"):
                    print(f"  {symbol}")
                elif confidence == "low":
                    print(f"  {symbol}  (partial: {best['artist']} - {best['name']})")
                else:
                    print(f"  {symbol}")

            if confidence in ("exact", "high"):
                uri = best["uri"]
                if uri in playlist_uris:
                    # Already confirmed in playlist — mark added immediately
                    history_store.set_track(history, key,
                                            state=ADDED,
                                            display=label,
                                            spotify_uri=uri,
                                            match_confidence=confidence,
                                            source_file=t.get("source_file"))
                    logging.debug(f"[DECISION] {label} -> {confidence.upper()} (already in playlist)")
                else:
                    # Queue for upload — mark added only after Spotify confirms
                    to_add_uris.append(uri)
                    pending_tracks[uri] = (key, label, confidence, t.get("source_file"))
                    logging.debug(f"[DECISION] {label} -> {confidence.upper()} queued for upload ({len(to_add_uris)} pending)")
                added_count += 1
            elif confidence == "low":
                # LOW = not added, saved for review. Check exhaustion.
                existing = history.get("tracks", {}).get(key, {})
                attempts = existing.get("search_attempts", 0) + 1
                state = "exhausted" if attempts >= MAX_SEARCH_ATTEMPTS else UNMATCHED
                history_store.set_track(history, key,
                                        state=state,
                                        display=label,
                                        match_confidence="low",
                                        source_file=t.get("source_file"))
                low_confidence.append({
                    "track": label,
                    "matched": f"{best['artist']} - {best['name']} ({best['album']})",
                    "confidence": "low",
                })
                logging.debug(f"[DECISION] {label} -> LOW ({state}, attempt {attempts}) best={best['artist']} - {best['name']}")
                unmatched_count += 1
            else:
                # NONE match — check if should be exhausted
                existing = history.get("tracks", {}).get(key, {})
                attempts = existing.get("search_attempts", 0) + 1
                state = "exhausted" if attempts >= MAX_SEARCH_ATTEMPTS else UNMATCHED
                history_store.set_track(history, key,
                                        state=state,
                                        display=label,
                                        source_file=t.get("source_file"))
                logging.debug(f"[DECISION] {label} -> NONE ({state}, attempt {attempts})")
                unmatched_count += 1

            history_dirty = True

            if search_delay > 0:
                time.sleep(search_delay)

            # Periodic history save
            if i % SAVE_INTERVAL == 0 and history_dirty:
                history_store.save(history)
                history_dirty = False

            # Periodic playlist flush
            if len(to_add_uris) >= FLUSH_INTERVAL:
                if interactive:
                    print()
                logging.info(f"[FLUSH] Uploading batch of {len(to_add_uris)} URIs to playlist")
                result = client.add_tracks(playlist_id, to_add_uris)
                logging.info(f"[FLUSH] Batch result: {len(result.succeeded)} succeeded, {len(result.failed)} failed")
                for uri in result.succeeded:
                    playlist_uris.add(uri)
                    if uri in pending_tracks:
                        pk, pl, pc, ps = pending_tracks.pop(uri)
                        history_store.set_track(history, pk, state=ADDED,
                                                display=pl, spotify_uri=uri,
                                                match_confidence=pc, source_file=ps)
                for uri in result.failed:
                    if uri in pending_tracks:
                        pk, pl, _, ps = pending_tracks.pop(uri)
                        history_store.set_track(history, pk, state=UNMATCHED,
                                                display=pl, source_file=ps)
                        logging.warning(f"Upload failed for {pl}, marked unmatched for retry")
                # Save history AFTER successful playlist write
                history_store.save(history)
                history_dirty = False
                to_add_uris = []

                if interactive:
                    eta = _eta(search_start, i, n)
                    print(f"  Progress: {i}/{n} | {added_count} matched | {unmatched_count} unmatched | ETA {eta}")

        if interactive:
            print()

    # ── Stage 4: Final upload & report ───────────────────────────────────
    print(f"\n[Stage 4/4] Finalizing...")
    logging.info(f"Stage 4: Final upload {len(to_add_uris)} tracks")

    if to_add_uris:
        logging.info(f"[FINAL] Uploading final batch of {len(to_add_uris)} URIs")
        result = client.add_tracks(playlist_id, to_add_uris)
        logging.info(f"[FINAL] Result: {len(result.succeeded)} succeeded, {len(result.failed)} failed")
        for uri in result.succeeded:
            playlist_uris.add(uri)
            if uri in pending_tracks:
                pk, pl, pc, ps = pending_tracks.pop(uri)
                history_store.set_track(history, pk, state=ADDED,
                                        display=pl, spotify_uri=uri,
                                        match_confidence=pc, source_file=ps)
                history_dirty = True
        for uri in result.failed:
            if uri in pending_tracks:
                pk, pl, _, ps = pending_tracks.pop(uri)
                history_store.set_track(history, pk, state=UNMATCHED,
                                        display=pl, source_file=ps)
                logging.warning(f"Upload failed for {pl}, marked unmatched for retry")
                history_dirty = True

    # Final history save
    if history_dirty or pending_tracks:
        # Any remaining pending_tracks had no upload result — mark unmatched for safety
        for uri, (pk, pl, _, ps) in pending_tracks.items():
            history_store.set_track(history, pk, state=UNMATCHED,
                                    display=pl, source_file=ps)
            logging.warning(f"Pending track {pl} never confirmed, marked unmatched")
        history_store.save(history)

    elapsed = int((datetime.now() - start).total_seconds())

    # Generate report
    report_path = generate_report(
        report_dir=report_dir,
        history=history,
        low_confidence=low_confidence,
        recovered=recovered_list,
        removed_uris=removed_uris,
        total_tracks=len(tracks),
    )

    print(f"\n{'='*60}")
    print(f"  Run complete in {elapsed}s")
    print(f"{'='*60}")
    print(f"  Library total      : {len(tracks)}")
    print(f"  Already in sync    : {plan.skipped_synced}")
    print(f"  Recovered          : {len(recovered_list)}")
    print(f"  Newly matched      : {added_count}")
    print(f"  Unmatched          : {unmatched_count}")
    print(f"  Removed            : {len(removed_uris)}")
    print(f"  Search errors      : {error_count}")
    print(f"  Custom / skipped   : {plan.skipped_custom}")
    print(f"  Exhausted          : {plan.skipped_exhausted}")
    print(f"{'='*60}")
    print(f"\n  Report: {report_path}")
    logging.info(f"Done. Synced={plan.skipped_synced} Recovered={len(recovered_list)} Added={added_count} Unmatched={unmatched_count} Removed={len(removed_uris)} Errors={error_count} Time={elapsed}s")

    if interactive:
        _wait_for_exit()

    return {
        "library_total": len(tracks),
        "synced": plan.skipped_synced,
        "searched": n,
        "added": added_count,
        "unmatched": unmatched_count,
        "recovered": len(recovered_list),
        "removed": len(removed_uris),
        "errors": error_count,
        "report_path": report_path,
        "history": history,
        "playlist_uris": playlist_uris,
    }


def main():
    # Force UTF-8 output on Windows (cp1252 can't handle music metadata)
    if sys.stdout.encoding != "utf-8":
        sys.stdout.reconfigure(encoding="utf-8", errors="replace")
        sys.stderr.reconfigure(encoding="utf-8", errors="replace")

    log_file = setup_logging()
    logging.info("=== SpotifyPlaylistGen started ===")

    # Parse CLI flags
    simulate = "--simulate" in sys.argv

    config = load_config(CONFIG_PATH)
    if not config:
        print(f"\nERROR: Config not found at {CONFIG_PATH}")
        _wait_for_exit()
        return
    missing = validate_config(config)
    if missing:
        print(f"\nERROR: Config missing keys: {missing}")
        _wait_for_exit()
        return

    print(f"\n{'='*60}")
    print(f"  SpotifyPlaylistGen")
    print(f"  Log: {log_file}")
    if simulate:
        print(f"  Mode: SIMULATION")
    print(f"{'='*60}")

    if simulate:
        from src.spotify_simulator import SimulatedSpotifyClient
        fixture_path = os.path.join(BASE_DIR, "tests", "fixtures", "golden_spotify_responses.json")
        client = SimulatedSpotifyClient(fixture_path=fixture_path)
    else:
        from src.spotify_client import RealSpotifyClient
        try:
            client = RealSpotifyClient(config)
        except Exception as e:
            logging.error(f"Spotify auth failed: {e}")
            print(f"  ERROR: Could not connect to Spotify: {e}")
            _wait_for_exit()
            return

    history_store = HistoryStore(HISTORY_PATH)

    try:
        with LockFile(LOCK_PATH):
            run_pipeline(
                client=client,
                config=config,
                history_store=history_store,
                history_path=HISTORY_PATH,
                report_dir=REPORT_DIR,
                search_delay=SEARCH_DELAY_S if not simulate else 0,
                interactive=True,
            )
    except RuntimeError as e:
        if "Another instance" in str(e):
            print(f"\nERROR: {e}")
            logging.error(str(e))
            _wait_for_exit()
        else:
            raise


if __name__ == "__main__":
    main()
