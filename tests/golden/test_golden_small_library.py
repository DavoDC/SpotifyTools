"""Golden Path Test: 10-track library with known match distribution.

Fixture: 10 XML tracks with pre-configured Spotify responses:
  3 exact matches  → added to playlist
  2 high matches   → added to playlist
  2 low matches    → NOT added (saved for review)
  3 no matches     → NOT added (unmatched)

This test validates the ENTIRE pipeline from XML input to final state.
If this test fails, the implementation is incorrect.
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


def _run_golden(tmpdir, initial_playlist=None, existing_history=None):
    """Run the full pipeline with golden fixtures. Returns (summary, client, history_store)."""
    with open(GOLDEN_RESPONSES, "r", encoding="utf-8") as f:
        fixture = json.load(f)

    if initial_playlist is not None:
        fixture["initial_playlist"] = initial_playlist

    client = SimulatedSpotifyClient(fixture_data=fixture)
    history_path = os.path.join(tmpdir, "history.json")
    report_dir = os.path.join(tmpdir, "reports")

    if existing_history:
        with open(history_path, "w", encoding="utf-8") as f:
            json.dump(existing_history, f)

    store = HistoryStore(history_path)
    config = {
        "spotify_client_id": "test",
        "spotify_client_secret": "test",
        "spotify_redirect_uri": "http://localhost:8888",
        "spotify_playlist_id": "test_playlist",
        "audiomirror_path": GOLDEN_LIBRARY,
    }

    summary = run_pipeline(
        client=client,
        config=config,
        history_store=store,
        history_path=history_path,
        report_dir=report_dir,
        search_delay=0,
        interactive=False,
    )

    return summary, client, store


# ── Core golden path ─────────────────────────────────────────────────────────

def test_golden_finds_10_tracks_in_library():
    with tempfile.TemporaryDirectory() as d:
        summary, _, _ = _run_golden(d)
        assert summary["library_total"] == 10


def test_golden_adds_5_tracks_to_playlist():
    """3 exact + 2 high = 5 tracks should be added."""
    with tempfile.TemporaryDirectory() as d:
        summary, client, _ = _run_golden(d)
        assert summary["added"] == 5
        assert len(client.playlist_contents) == 5


def test_golden_correct_uris_in_playlist():
    """Only exact and high confidence tracks should be in playlist."""
    expected_uris = {
        "spotify:track:exact001",
        "spotify:track:exact002",
        "spotify:track:exact003",
        "spotify:track:high001",
        "spotify:track:high002",
    }
    with tempfile.TemporaryDirectory() as d:
        summary, client, _ = _run_golden(d)
        assert set(client.playlist_contents) == expected_uris


def test_golden_low_confidence_not_added():
    """LOW matches must NOT be in the playlist."""
    with tempfile.TemporaryDirectory() as d:
        summary, client, _ = _run_golden(d)
        playlist = set(client.playlist_contents)
        assert "spotify:track:low001" not in playlist
        assert "spotify:track:low002" not in playlist


def test_golden_unmatched_count():
    """2 low + 3 none = 5 unmatched."""
    with tempfile.TemporaryDirectory() as d:
        summary, _, _ = _run_golden(d)
        assert summary["unmatched"] == 5


def test_golden_history_has_all_10_tracks():
    with tempfile.TemporaryDirectory() as d:
        summary, _, _ = _run_golden(d)
        history = summary["history"]
        assert len(history["tracks"]) == 10


def test_golden_history_added_tracks_correct():
    """5 tracks should have state=added."""
    with tempfile.TemporaryDirectory() as d:
        summary, _, _ = _run_golden(d)
        tracks = summary["history"]["tracks"]
        added = [k for k, v in tracks.items() if v["state"] == "added"]
        assert len(added) == 5


def test_golden_history_unmatched_tracks_correct():
    """5 tracks should have state=unmatched (2 low + 3 none)."""
    with tempfile.TemporaryDirectory() as d:
        summary, _, _ = _run_golden(d)
        tracks = summary["history"]["tracks"]
        unmatched = [k for k, v in tracks.items() if v["state"] == "unmatched"]
        assert len(unmatched) == 5


def test_golden_report_generated():
    with tempfile.TemporaryDirectory() as d:
        summary, _, _ = _run_golden(d)
        assert "report_path" in summary
        assert os.path.exists(summary["report_path"])


def test_golden_report_contains_unmatched():
    with tempfile.TemporaryDirectory() as d:
        summary, _, _ = _run_golden(d)
        with open(summary["report_path"], "r", encoding="utf-8") as f:
            content = f.read()
        # The 3 no-match tracks should appear in unmatched section
        assert "Unknown Local Band" in content
        assert "Forgotten Artist" in content
        assert "Studio Ghost" in content


def test_golden_report_contains_low_confidence():
    with tempfile.TemporaryDirectory() as d:
        summary, _, _ = _run_golden(d)
        with open(summary["report_path"], "r", encoding="utf-8") as f:
            content = f.read()
        assert "Low Confidence" in content
        assert "Led Zeppelin" in content
        assert "Eagles" in content


def test_golden_no_duplicate_playlist_operations():
    """Each URI should be added exactly once."""
    with tempfile.TemporaryDirectory() as d:
        _, client, _ = _run_golden(d)
        add_ops = [op for op in client.operations if op["type"] == "add"]
        all_added_uris = []
        for op in add_ops:
            all_added_uris.extend(op["uris"])
        assert len(all_added_uris) == len(set(all_added_uris)), "Duplicate add operations detected!"
