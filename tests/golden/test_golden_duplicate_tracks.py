"""Golden Path Test: duplicate track handling.

Verifies the system correctly handles:
- Duplicates already in the playlist (dedup before sync)
- Duplicate tracks in XML library (same artist|title key)
- Re-running after adding tracks doesn't create duplicates
"""

import json
import os
import tempfile

from src.main import run_pipeline, track_key
from src.history_store import HistoryStore
from src.spotify_simulator import SimulatedSpotifyClient

FIXTURES_DIR = os.path.join(os.path.dirname(os.path.dirname(__file__)), "fixtures")
GOLDEN_LIBRARY = os.path.join(FIXTURES_DIR, "golden_library")
GOLDEN_RESPONSES = os.path.join(FIXTURES_DIR, "golden_spotify_responses.json")


def _load_fixture():
    with open(GOLDEN_RESPONSES, "r", encoding="utf-8") as f:
        return json.load(f)


def _run(tmpdir, client):
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
        client=client, config=config, history_store=store,
        history_path=history_path, report_dir=report_dir,
        search_delay=0, interactive=False,
    )


# ── Pre-existing duplicates in playlist ──────────────────────────────────────

def test_dedup_removes_pre_existing_duplicates():
    """If playlist already has duplicates, they should be removed before sync."""
    fixture = _load_fixture()
    # Playlist starts with duplicate URIs
    fixture["initial_playlist"] = [
        "spotify:track:exact001",
        "spotify:track:exact001",  # duplicate
        "spotify:track:exact002",
    ]
    with tempfile.TemporaryDirectory() as d:
        client = SimulatedSpotifyClient(fixture_data=fixture)
        _run(d, client)

        # After run, no duplicates should remain
        contents = client.playlist_contents
        assert len(contents) == len(set(contents)), \
            f"Duplicates remain after sync: {contents}"


def test_dedup_keeps_correct_track_count():
    """After dedup + sync, playlist should have exactly the matched tracks."""
    fixture = _load_fixture()
    fixture["initial_playlist"] = [
        "spotify:track:exact001",
        "spotify:track:exact001",
        "spotify:track:exact002",
        "spotify:track:exact002",
        "spotify:track:exact002",
    ]
    with tempfile.TemporaryDirectory() as d:
        client = SimulatedSpotifyClient(fixture_data=fixture)
        _run(d, client)

        # Should have 5 unique tracks (3 exact + 2 high)
        assert len(set(client.playlist_contents)) == 5


# ── Re-run doesn't create duplicates ────────────────────────────────────────

def test_rerun_after_full_sync_no_new_adds():
    """Running twice should not add any tracks the second time."""
    fixture = _load_fixture()
    with tempfile.TemporaryDirectory() as d:
        client = SimulatedSpotifyClient(fixture_data=fixture)

        # Run 1
        summary1 = _run(d, client)
        assert summary1["added"] == 5

        # Run 2
        client.operations.clear()
        summary2 = _run(d, client)

        add_ops = [op for op in client.operations if op["type"] == "add"]
        assert len(add_ops) == 0, f"Run 2 added tracks when it shouldn't have"


def test_three_runs_same_playlist_size():
    """Playlist size must not grow across repeated runs."""
    fixture = _load_fixture()
    with tempfile.TemporaryDirectory() as d:
        client = SimulatedSpotifyClient(fixture_data=fixture)

        for i in range(3):
            _run(d, client)

        assert len(client.playlist_contents) == 5, \
            f"Playlist grew to {len(client.playlist_contents)} after 3 runs (expected 5)"


# ── Playlist has unknown tracks ──────────────────────────────────────────────

def test_unknown_tracks_in_playlist_get_removed():
    """Tracks in playlist that aren't in the XML library should be removed."""
    fixture = _load_fixture()
    fixture["initial_playlist"] = [
        "spotify:track:unknown_orphan",
        "spotify:track:another_orphan",
    ]
    with tempfile.TemporaryDirectory() as d:
        client = SimulatedSpotifyClient(fixture_data=fixture)
        summary = _run(d, client)

        assert summary["removed"] == 2
        assert "spotify:track:unknown_orphan" not in client.playlist_contents
        assert "spotify:track:another_orphan" not in client.playlist_contents
