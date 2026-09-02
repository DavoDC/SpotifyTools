"""Idempotency Test: running the CLI multiple times must produce identical state.

Definition: Running the pipeline N times with the same input must converge
to the same final playlist, history, and report state.

This test runs the pipeline 3 times and asserts stability after run 1.
"""

import json
import os
import tempfile

from spotify_tools.main import run_pipeline, track_key
from spotify_tools.history_store import HistoryStore
from spotify_tools.spotify_simulator import SimulatedSpotifyClient

FIXTURES_DIR = os.path.join(os.path.dirname(os.path.dirname(__file__)), "fixtures")
GOLDEN_LIBRARY = os.path.join(FIXTURES_DIR, "golden_library")
GOLDEN_RESPONSES = os.path.join(FIXTURES_DIR, "golden_spotify_responses.json")


def _load_fixture():
    with open(GOLDEN_RESPONSES, "r", encoding="utf-8") as f:
        return json.load(f)


def _run_pipeline(tmpdir, client):
    """Run pipeline against given client and tmpdir."""
    history_path = os.path.join(tmpdir, "history.json")
    report_dir = os.path.join(tmpdir, "reports")
    store = HistoryStore(history_path)

    config = {
        "spotify_client_id": "test",
        "spotify_client_secret": "test",
        "spotify_redirect_uri": "http://localhost:8888",
        "spotify_playlist_id": "test_playlist",
        "audiomirror_path": GOLDEN_LIBRARY,
    }

    return run_pipeline(
        client=client,
        config=config,
        history_store=store,
        history_path=history_path,
        report_dir=report_dir,
        search_delay=0,
        interactive=False,
    )


def test_idempotency_three_runs():
    """Run pipeline 3 times. After run 1, state must not change."""
    with tempfile.TemporaryDirectory() as tmpdir:
        # The simulator persists state across runs (same instance)
        fixture = _load_fixture()
        client = SimulatedSpotifyClient(fixture_data=fixture)

        # Run 1: initial sync
        summary1 = _run_pipeline(tmpdir, client)
        playlist_after_1 = sorted(client.playlist_contents)
        history_path = os.path.join(tmpdir, "history.json")
        with open(history_path, "r", encoding="utf-8") as f:
            history_after_1 = json.load(f)

        assert summary1["added"] == 5, f"Run 1: expected 5 added, got {summary1['added']}"
        assert len(playlist_after_1) == 5

        # Reset operation log to track run 2 operations
        client.operations.clear()

        # Run 2: should be a no-op
        summary2 = _run_pipeline(tmpdir, client)
        playlist_after_2 = sorted(client.playlist_contents)

        with open(history_path, "r", encoding="utf-8") as f:
            history_after_2 = json.load(f)

        # Playlist must be identical
        assert playlist_after_2 == playlist_after_1, \
            f"Run 2 changed playlist! Before: {playlist_after_1}, After: {playlist_after_2}"

        # No new adds or removes should have happened
        add_ops = [op for op in client.operations if op["type"] == "add"]
        remove_ops = [op for op in client.operations if op["type"] == "remove"]
        assert len(add_ops) == 0, f"Run 2 performed {len(add_ops)} add operations (expected 0)"
        assert len(remove_ops) == 0, f"Run 2 performed {len(remove_ops)} remove operations (expected 0)"

        # History track states must be unchanged
        for key in history_after_1["tracks"]:
            assert history_after_2["tracks"][key]["state"] == history_after_1["tracks"][key]["state"], \
                f"Run 2 changed state of {key}"

        # Reset and run 3
        client.operations.clear()

        # Run 3: also a no-op
        summary3 = _run_pipeline(tmpdir, client)
        playlist_after_3 = sorted(client.playlist_contents)

        assert playlist_after_3 == playlist_after_1, \
            f"Run 3 changed playlist!"

        add_ops = [op for op in client.operations if op["type"] == "add"]
        remove_ops = [op for op in client.operations if op["type"] == "remove"]
        assert len(add_ops) == 0, f"Run 3 performed {len(add_ops)} add operations"
        assert len(remove_ops) == 0, f"Run 3 performed {len(remove_ops)} remove operations"


def test_idempotency_no_duplicate_tracks():
    """After 3 runs, every URI in playlist appears exactly once."""
    with tempfile.TemporaryDirectory() as tmpdir:
        fixture = _load_fixture()
        client = SimulatedSpotifyClient(fixture_data=fixture)

        for _ in range(3):
            _run_pipeline(tmpdir, client)

        contents = client.playlist_contents
        assert len(contents) == len(set(contents)), \
            f"Duplicate tracks found after 3 runs: {[u for u in contents if contents.count(u) > 1]}"


def test_idempotency_search_count_decreases():
    """Run 2 should search fewer tracks than run 1 (matched ones are skipped)."""
    with tempfile.TemporaryDirectory() as tmpdir:
        fixture = _load_fixture()
        client = SimulatedSpotifyClient(fixture_data=fixture)

        summary1 = _run_pipeline(tmpdir, client)
        client.operations.clear()

        summary2 = _run_pipeline(tmpdir, client)

        assert summary2["searched"] <= summary1["searched"], \
            f"Run 2 searched {summary2['searched']} tracks, more than run 1's {summary1['searched']}"
