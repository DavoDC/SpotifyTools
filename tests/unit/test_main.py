"""
Tests for src/main.py — entry point wiring and helpers.
Tests for extracted modules (config, report_generator) are in their own files.
"""
import importlib
import os
from spotify_tools.main import track_key, ADDED, UNMATCHED, SAVE_INTERVAL, FLUSH_INTERVAL


# ── module sanity ─────────────────────────────────────────────────────────────

def test_main_module_imports():
    importlib.import_module("spotify_tools.main")

def test_main_has_main_function():
    mod = importlib.import_module("spotify_tools.main")
    assert callable(getattr(mod, "main", None)), "main() function missing"

def test_main_has_run_pipeline():
    mod = importlib.import_module("spotify_tools.main")
    assert callable(getattr(mod, "run_pipeline", None)), "run_pipeline() function missing"

def test_main_constants_defined():
    assert ADDED == "added"
    assert UNMATCHED == "unmatched"
    assert SAVE_INTERVAL > 0
    assert FLUSH_INTERVAL > 0


# ── track_key ─────────────────────────────────────────────────────────────────

def test_track_key_format():
    track = {"primary_artist": "Eminem", "title": "Lose Yourself"}
    assert track_key(track) == "Eminem|Lose Yourself"

def test_track_key_special_chars():
    track = {"primary_artist": "Beyoncé", "title": "Love On Top"}
    assert track_key(track) == "Beyoncé|Love On Top"


# ── reset_exhausted_tracks ────────────────────────────────────────────────────

def test_reset_exhausted_resets_state_and_attempts():
    from spotify_tools.main import reset_exhausted_tracks
    history = {"version": 2, "tracks": {
        "Artist|Song": {"state": "exhausted", "search_attempts": 5, "display": "Artist - Song"},
    }}
    count = reset_exhausted_tracks(history)
    assert count == 1
    assert history["tracks"]["Artist|Song"]["state"] == "unmatched"
    assert history["tracks"]["Artist|Song"]["search_attempts"] == 0

def test_reset_exhausted_leaves_other_states_unchanged():
    from spotify_tools.main import reset_exhausted_tracks
    history = {"version": 2, "tracks": {
        "A|Song1": {"state": "added", "search_attempts": 1, "display": "..."},
        "A|Song2": {"state": "unmatched", "search_attempts": 2, "display": "..."},
        "A|Song3": {"state": "custom", "search_attempts": 0, "display": "..."},
    }}
    count = reset_exhausted_tracks(history)
    assert count == 0
    assert history["tracks"]["A|Song1"]["state"] == "added"
    assert history["tracks"]["A|Song2"]["state"] == "unmatched"
    assert history["tracks"]["A|Song3"]["state"] == "custom"

def test_reset_exhausted_returns_correct_count():
    from spotify_tools.main import reset_exhausted_tracks
    history = {"version": 2, "tracks": {
        "A|1": {"state": "exhausted", "search_attempts": 5, "display": "..."},
        "A|2": {"state": "exhausted", "search_attempts": 6, "display": "..."},
        "A|3": {"state": "added", "search_attempts": 1, "display": "..."},
    }}
    count = reset_exhausted_tracks(history)
    assert count == 2

def test_reset_exhausted_empty_history():
    from spotify_tools.main import reset_exhausted_tracks
    history = {"version": 2, "tracks": {}}
    assert reset_exhausted_tracks(history) == 0
