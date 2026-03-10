"""
Smoke tests for src/main.py.
These don't test logic — they verify the entry point is importable and
wired up correctly. Catches broken imports, missing files, bad paths.
"""
import importlib
import json
import os
import tempfile
from src.main import review_match, load_json, save_json, track_key, ADDED, QUIT, REJECTED, CUSTOM
from unittest.mock import patch


def test_main_module_imports():
    """Catches any ImportError in main.py or its dependencies instantly."""
    importlib.import_module("src.main")


def test_main_has_main_function():
    mod = importlib.import_module("src.main")
    assert callable(getattr(mod, "main", None)), "main() function missing from src/main.py"


def test_main_config_path_points_to_config_dir():
    mod = importlib.import_module("src.main")
    assert "config" in mod.CONFIG_PATH, f"CONFIG_PATH unexpected: {mod.CONFIG_PATH}"


def test_main_log_dir_points_to_repo_root():
    mod = importlib.import_module("src.main")
    assert mod.LOG_DIR.endswith(os.path.join("data", "logs")), f"LOG_DIR unexpected: {mod.LOG_DIR}"


# ── review_match behaviour ────────────────────────────────────────────────────

TRACK = {"primary_artist": "Eminem", "title": "Lose Yourself", "album": "8 Mile"}
MATCH = {"confidence": "high", "artist": "Eminem", "name": "Lose Yourself",
         "album": "8 Mile", "uri": "spotify:track:abc123"}

def test_review_match_y_accepts_best():
    with patch("builtins.input", return_value="y"):
        decision, uri = review_match(TRACK, [MATCH])
    assert decision == ADDED
    assert uri == "spotify:track:abc123"

def test_review_match_q_returns_quit():
    with patch("builtins.input", return_value="q"):
        decision, uri = review_match(TRACK, [MATCH])
    assert decision == QUIT
    assert uri is None

def test_review_match_s_rejects():
    with patch("builtins.input", return_value="s"):
        decision, uri = review_match(TRACK, [MATCH])
    assert decision == REJECTED
    assert uri is None

def test_review_match_no_matches():
    with patch("builtins.input", return_value="s"):
        decision, uri = review_match(TRACK, [])
    assert decision == REJECTED

def test_review_match_pick_alternative():
    alt = {"confidence": "low", "artist": "Eminem", "name": "Lose Yourself (Alt)",
           "album": "Other", "uri": "spotify:track:alt1"}
    with patch("builtins.input", return_value="1"):
        decision, uri = review_match(TRACK, [MATCH, alt])
    assert decision == ADDED
    assert uri == "spotify:track:alt1"

def test_review_match_alternative_out_of_range():
    # Only 1 match, picking "1" is out of range — should reject
    with patch("builtins.input", return_value="1"):
        decision, uri = review_match(TRACK, [MATCH])
    assert decision == REJECTED
    assert uri is None

def test_review_match_custom():
    with patch("builtins.input", return_value="c"):
        decision, uri = review_match(TRACK, [MATCH])
    assert decision == CUSTOM
    assert uri is None

def test_review_match_invalid_input_rejects():
    with patch("builtins.input", return_value="zzz"):
        decision, uri = review_match(TRACK, [MATCH])
    assert decision == REJECTED


# ── load_json / save_json ─────────────────────────────────────────────────────

def test_load_json_returns_empty_dict_if_missing():
    assert load_json("/nonexistent/path/file.json") == {}

def test_load_json_reads_valid_file():
    with tempfile.NamedTemporaryFile(mode="w", suffix=".json", delete=False) as f:
        json.dump({"key": "value"}, f)
        path = f.name
    try:
        assert load_json(path) == {"key": "value"}
    finally:
        os.unlink(path)

def test_save_json_writes_and_load_reads_back():
    with tempfile.NamedTemporaryFile(suffix=".json", delete=False) as f:
        path = f.name
    try:
        save_json(path, {"a": 1, "b": [1, 2]})
        assert load_json(path) == {"a": 1, "b": [1, 2]}
    finally:
        os.unlink(path)


# ── track_key ─────────────────────────────────────────────────────────────────

def test_track_key_format():
    track = {"primary_artist": "Eminem", "title": "Lose Yourself"}
    assert track_key(track) == "Eminem|Lose Yourself"
