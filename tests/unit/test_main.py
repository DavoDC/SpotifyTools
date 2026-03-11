"""
Tests for src/main.py — entry point wiring and helpers.
Tests for extracted modules (config, report_generator) are in their own files.
"""
import importlib
import os
from src.main import track_key, ADDED, UNMATCHED, SAVE_INTERVAL, FLUSH_INTERVAL


# ── module sanity ─────────────────────────────────────────────────────────────

def test_main_module_imports():
    importlib.import_module("src.main")

def test_main_has_main_function():
    mod = importlib.import_module("src.main")
    assert callable(getattr(mod, "main", None)), "main() function missing"

def test_main_has_run_pipeline():
    mod = importlib.import_module("src.main")
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
