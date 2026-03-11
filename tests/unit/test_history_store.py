"""Tests for src/history_store.py — atomic writes, backup, migration, schema."""

import json
import os
import tempfile

import pytest

from src.history_store import HistoryStore, CURRENT_VERSION


# ── Helpers ──────────────────────────────────────────────────────────────────

def _tmp_path():
    """Return a temp file path (not created)."""
    d = tempfile.mkdtemp()
    return os.path.join(d, "history.json")


def _v1_history():
    """Sample v1 format history (flat dict, no version key)."""
    return {
        "Eminem|Lose Yourself": {
            "state": "added",
            "track": "Eminem — Lose Yourself",
            "spotify_uri": "spotify:track:abc123",
            "decided_at": "2026-03-10T15:38:48.159954",
        },
        "Unknown|Ghost": {
            "state": "unmatched",
            "track": "Unknown — Ghost",
            "spotify_uri": None,
            "decided_at": "2026-03-10T16:00:00.000000",
        },
    }


def _v2_history(tracks=None):
    """Sample v2 format history."""
    if tracks is None:
        tracks = {
            "Eminem|Lose Yourself": {
                "state": "added",
                "display": "Eminem — Lose Yourself",
                "spotify_uri": "spotify:track:abc123",
                "spotify_id": "abc123",
                "match_confidence": "exact",
                "search_attempts": 1,
                "first_seen": "2026-03-10T15:00:00",
                "last_updated": "2026-03-10T15:38:48",
                "source_file": None,
            }
        }
    return {"version": CURRENT_VERSION, "tracks": tracks}


# ── load ─────────────────────────────────────────────────────────────────────

def test_load_returns_empty_v2_when_no_file():
    store = HistoryStore("/nonexistent/path/history.json")
    result = store.load()
    assert result["version"] == CURRENT_VERSION
    assert result["tracks"] == {}


def test_load_reads_v2_format():
    path = _tmp_path()
    with open(path, "w") as f:
        json.dump(_v2_history(), f)

    store = HistoryStore(path)
    result = store.load()

    assert result["version"] == CURRENT_VERSION
    assert "Eminem|Lose Yourself" in result["tracks"]
    assert result["tracks"]["Eminem|Lose Yourself"]["spotify_id"] == "abc123"


def test_load_migrates_v1_to_v2():
    path = _tmp_path()
    with open(path, "w") as f:
        json.dump(_v1_history(), f)

    store = HistoryStore(path)
    result = store.load()

    assert result["version"] == CURRENT_VERSION
    assert "Eminem|Lose Yourself" in result["tracks"]
    entry = result["tracks"]["Eminem|Lose Yourself"]
    assert entry["state"] == "added"
    assert entry["spotify_uri"] == "spotify:track:abc123"
    assert entry["spotify_id"] == "abc123"
    assert entry["search_attempts"] == 1
    assert entry["display"] == "Eminem — Lose Yourself"


def test_load_migrates_v1_unmatched():
    path = _tmp_path()
    with open(path, "w") as f:
        json.dump(_v1_history(), f)

    store = HistoryStore(path)
    result = store.load()

    entry = result["tracks"]["Unknown|Ghost"]
    assert entry["state"] == "unmatched"
    assert entry["spotify_uri"] is None
    assert entry["spotify_id"] is None


def test_load_falls_back_to_backup_on_corruption():
    path = _tmp_path()
    backup_path = path + ".bak"

    # Write corrupt primary
    with open(path, "w") as f:
        f.write("{invalid json!!!")

    # Write valid backup
    with open(backup_path, "w") as f:
        json.dump(_v2_history(), f)

    store = HistoryStore(path)
    result = store.load()

    assert result["version"] == CURRENT_VERSION
    assert "Eminem|Lose Yourself" in result["tracks"]


def test_load_returns_empty_when_both_corrupt():
    path = _tmp_path()
    backup_path = path + ".bak"

    with open(path, "w") as f:
        f.write("broken")
    with open(backup_path, "w") as f:
        f.write("also broken")

    store = HistoryStore(path)
    result = store.load()

    assert result == {"version": CURRENT_VERSION, "tracks": {}}


# ── save ─────────────────────────────────────────────────────────────────────

def test_save_writes_valid_json():
    path = _tmp_path()
    store = HistoryStore(path)
    history = _v2_history()

    store.save(history)

    with open(path, "r", encoding="utf-8") as f:
        loaded = json.load(f)
    assert loaded == history


def test_save_is_atomic_no_temp_leftover():
    path = _tmp_path()
    store = HistoryStore(path)

    store.save(_v2_history())

    assert os.path.exists(path)
    assert not os.path.exists(path + ".tmp")


def test_save_creates_parent_dirs():
    d = tempfile.mkdtemp()
    path = os.path.join(d, "sub", "dir", "history.json")
    store = HistoryStore(path)

    store.save(_v2_history())

    assert os.path.exists(path)


def test_save_then_load_roundtrip():
    path = _tmp_path()
    store = HistoryStore(path)
    history = _v2_history()

    store.save(history)
    loaded = store.load()

    assert loaded == history


# ── create_backup ────────────────────────────────────────────────────────────

def test_create_backup_copies_file():
    path = _tmp_path()
    store = HistoryStore(path)
    store.save(_v2_history())

    store.create_backup()

    assert os.path.exists(path + ".bak")
    with open(path + ".bak", "r", encoding="utf-8") as f:
        backup = json.load(f)
    assert backup == _v2_history()


def test_create_backup_noop_when_no_file():
    path = _tmp_path()
    store = HistoryStore(path)

    # Should not raise
    store.create_backup()
    assert not os.path.exists(path + ".bak")


# ── set_track ────────────────────────────────────────────────────────────────

def test_set_track_creates_new_entry():
    history = _v2_history(tracks={})
    store = HistoryStore("/tmp/test.json")

    store.set_track(history, "Artist|Title",
                    state="added",
                    display="Artist — Title",
                    spotify_uri="spotify:track:xyz",
                    match_confidence="exact")

    entry = history["tracks"]["Artist|Title"]
    assert entry["state"] == "added"
    assert entry["spotify_id"] == "xyz"
    assert entry["match_confidence"] == "exact"
    assert entry["search_attempts"] == 1


def test_set_track_increments_search_attempts():
    history = _v2_history(tracks={
        "A|B": {
            "state": "unmatched",
            "display": "A — B",
            "spotify_uri": None,
            "spotify_id": None,
            "match_confidence": None,
            "search_attempts": 3,
            "first_seen": "2026-01-01T00:00:00",
            "last_updated": "2026-01-01T00:00:00",
            "source_file": None,
        }
    })
    store = HistoryStore("/tmp/test.json")

    store.set_track(history, "A|B",
                    state="unmatched",
                    display="A — B")

    assert history["tracks"]["A|B"]["search_attempts"] == 4


def test_set_track_preserves_first_seen():
    history = _v2_history(tracks={
        "A|B": {
            "state": "unmatched",
            "display": "A — B",
            "spotify_uri": None,
            "spotify_id": None,
            "match_confidence": None,
            "search_attempts": 1,
            "first_seen": "2025-01-01T00:00:00",
            "last_updated": "2025-06-01T00:00:00",
            "source_file": None,
        }
    })
    store = HistoryStore("/tmp/test.json")

    store.set_track(history, "A|B",
                    state="added",
                    display="A — B",
                    spotify_uri="spotify:track:xyz",
                    match_confidence="high")

    assert history["tracks"]["A|B"]["first_seen"] == "2025-01-01T00:00:00"


def test_set_track_extracts_spotify_id():
    history = _v2_history(tracks={})
    store = HistoryStore("/tmp/test.json")

    store.set_track(history, "A|B",
                    state="added",
                    display="A — B",
                    spotify_uri="spotify:track:abc123")

    assert history["tracks"]["A|B"]["spotify_id"] == "abc123"


def test_set_track_null_uri_gives_null_id():
    history = _v2_history(tracks={})
    store = HistoryStore("/tmp/test.json")

    store.set_track(history, "A|B",
                    state="unmatched",
                    display="A — B",
                    spotify_uri=None)

    assert history["tracks"]["A|B"]["spotify_id"] is None
