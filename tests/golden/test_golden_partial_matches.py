"""Golden Path Test: partial match handling.

Verifies the system correctly handles:
- LOW confidence matches are excluded from playlist
- LOW matches appear in the report for manual review
- Unmatched tracks are retried on subsequent runs
- Exhausted tracks are not retried after MAX_SEARCH_ATTEMPTS
"""

import json
import os
import tempfile

from src.main import run_pipeline, track_key
from src.history_store import HistoryStore
from src.spotify_simulator import SimulatedSpotifyClient
from src.reconciler import MAX_SEARCH_ATTEMPTS

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


# ── LOW confidence handling ──────────────────────────────────────────────────

def test_low_confidence_tracks_not_in_playlist():
    """Led Zeppelin and Eagles have LOW confidence — must NOT be in playlist."""
    fixture = _load_fixture()
    with tempfile.TemporaryDirectory() as d:
        client = SimulatedSpotifyClient(fixture_data=fixture)
        _run(d, client)

        uris = set(client.playlist_contents)
        assert "spotify:track:low001" not in uris, "LOW match (Led Zeppelin) was added to playlist"
        assert "spotify:track:low002" not in uris, "LOW match (Eagles) was added to playlist"


def test_low_confidence_in_report():
    """LOW matches must appear in the low confidence section of the report."""
    fixture = _load_fixture()
    with tempfile.TemporaryDirectory() as d:
        client = SimulatedSpotifyClient(fixture_data=fixture)
        summary = _run(d, client)

        with open(summary["report_path"], "r", encoding="utf-8") as f:
            report = f.read()

        assert "Low Confidence" in report
        # Led Zeppelin had a low match
        assert "Stairway to Heaven" in report or "Led Zeppelin" in report
        # Eagles had a low match
        assert "Hotel California" in report or "Eagles" in report


def test_low_confidence_stored_as_unmatched_in_history():
    """LOW matches should be stored as 'unmatched' so they're retried."""
    fixture = _load_fixture()
    with tempfile.TemporaryDirectory() as d:
        client = SimulatedSpotifyClient(fixture_data=fixture)
        summary = _run(d, client)

        tracks = summary["history"]["tracks"]
        led_zep = tracks.get("Led Zeppelin|Stairway to Heaven", {})
        eagles = tracks.get("Eagles|Hotel California", {})

        assert led_zep.get("state") == "unmatched"
        assert eagles.get("state") == "unmatched"


# ── Unmatched retry behavior ────────────────────────────────────────────────

def test_unmatched_tracks_retried_on_second_run():
    """Unmatched tracks (including LOW) should be searched again on run 2."""
    fixture = _load_fixture()
    with tempfile.TemporaryDirectory() as d:
        client = SimulatedSpotifyClient(fixture_data=fixture)

        # Run 1
        summary1 = _run(d, client)
        assert summary1["unmatched"] == 5  # 2 low + 3 none

        # Run 2 — unmatched should be retried
        client.operations.clear()
        summary2 = _run(d, client)

        search_ops = [op for op in client.operations if op["type"] == "search"]
        # Should have searched the 5 unmatched tracks again
        assert len(search_ops) == 5, \
            f"Expected 5 search retries, got {len(search_ops)}"


def test_exhausted_tracks_not_retried():
    """After MAX_SEARCH_ATTEMPTS, tracks should stop being retried."""
    fixture = _load_fixture()
    with tempfile.TemporaryDirectory() as d:
        client = SimulatedSpotifyClient(fixture_data=fixture)

        # Run MAX_SEARCH_ATTEMPTS times
        for i in range(MAX_SEARCH_ATTEMPTS):
            _run(d, client)

        # Load history and check the no-match tracks
        history_path = os.path.join(d, "history.json")
        with open(history_path, "r", encoding="utf-8") as f:
            history = json.load(f)

        # The 3 tracks that always return no results should be exhausted
        ghost = history["tracks"].get("Unknown Local Band|Obscure Underground Track", {})
        rare = history["tracks"].get("Forgotten Artist|Rare Vinyl Only Release", {})
        demo = history["tracks"].get("Studio Ghost|Private Session Demo", {})

        assert ghost.get("state") == "exhausted", f"Expected exhausted, got {ghost.get('state')}"
        assert rare.get("state") == "exhausted", f"Expected exhausted, got {rare.get('state')}"
        assert demo.get("state") == "exhausted", f"Expected exhausted, got {demo.get('state')}"

        # Run once more — exhausted tracks should NOT be searched
        client.operations.clear()
        _run(d, client)

        search_ops = [op for op in client.operations if op["type"] == "search"]
        searched_keys = [op["key"] for op in search_ops]

        assert "Unknown Local Band|Obscure Underground Track" not in searched_keys
        assert "Forgotten Artist|Rare Vinyl Only Release" not in searched_keys
        assert "Studio Ghost|Private Session Demo" not in searched_keys


def test_search_attempts_increment():
    """search_attempts should increment with each retry."""
    fixture = _load_fixture()
    with tempfile.TemporaryDirectory() as d:
        client = SimulatedSpotifyClient(fixture_data=fixture)

        # Run 3 times
        for _ in range(3):
            _run(d, client)

        history_path = os.path.join(d, "history.json")
        with open(history_path, "r", encoding="utf-8") as f:
            history = json.load(f)

        ghost = history["tracks"]["Unknown Local Band|Obscure Underground Track"]
        assert ghost["search_attempts"] == 3, \
            f"Expected 3 search attempts after 3 runs, got {ghost['search_attempts']}"
