"""
Smoke tests for src/main.py.
These don't test logic — they verify the entry point is importable and
wired up correctly. Catches broken imports, missing files, bad paths.
"""
import importlib
import os
from src.main import review_match, ADDED, QUIT, REJECTED
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
