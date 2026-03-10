"""
Tests for src/main.py — entry point wiring, helpers, and report generation.
"""
import importlib
import json
import os
import tempfile
from src.main import (
    load_json, save_json, track_key, validate_config, generate_report,
    ADDED, UNMATCHED,
)


# ── module sanity ─────────────────────────────────────────────────────────────

def test_main_module_imports():
    importlib.import_module("src.main")

def test_main_has_main_function():
    mod = importlib.import_module("src.main")
    assert callable(getattr(mod, "main", None)), "main() function missing"

def test_main_config_path_points_to_config_dir():
    mod = importlib.import_module("src.main")
    assert "config" in mod.CONFIG_PATH

def test_main_log_dir_points_to_data_logs():
    mod = importlib.import_module("src.main")
    assert mod.LOG_DIR.endswith(os.path.join("data", "logs"))

def test_main_report_dir_points_to_data_reports():
    mod = importlib.import_module("src.main")
    assert mod.REPORT_DIR.endswith(os.path.join("data", "reports"))

def test_main_constants_defined():
    mod = importlib.import_module("src.main")
    assert mod.ADDED == "added"
    assert mod.UNMATCHED == "unmatched"
    assert mod.SAVE_INTERVAL > 0
    assert mod.FLUSH_INTERVAL > 0


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

def test_save_json_creates_missing_parent_dirs():
    with tempfile.TemporaryDirectory() as d:
        path = os.path.join(d, "sub", "dir", "file.json")
        save_json(path, {"x": 1})
        assert load_json(path) == {"x": 1}


# ── track_key ─────────────────────────────────────────────────────────────────

def test_track_key_format():
    track = {"primary_artist": "Eminem", "title": "Lose Yourself"}
    assert track_key(track) == "Eminem|Lose Yourself"

def test_track_key_special_chars():
    track = {"primary_artist": "Beyoncé", "title": "Love On Top"}
    assert track_key(track) == "Beyoncé|Love On Top"


# ── validate_config ───────────────────────────────────────────────────────────

FULL_CONFIG = {
    "spotify_client_id":     "id",
    "spotify_client_secret": "secret",
    "spotify_redirect_uri":  "http://localhost:8888",
    "spotify_playlist_id":   "playlistid",
    "audiomirror_path":      "/some/path",
}

def test_validate_config_passes_when_complete():
    assert validate_config(FULL_CONFIG) == []

def test_validate_config_catches_missing_key():
    cfg = {**FULL_CONFIG}
    del cfg["spotify_client_id"]
    missing = validate_config(cfg)
    assert "spotify_client_id" in missing

def test_validate_config_catches_empty_string():
    cfg = {**FULL_CONFIG, "spotify_client_secret": ""}
    missing = validate_config(cfg)
    assert "spotify_client_secret" in missing

def test_validate_config_catches_multiple_missing():
    missing = validate_config({})
    assert len(missing) == 5

def test_validate_config_returns_only_missing():
    cfg = {**FULL_CONFIG, "audiomirror_path": ""}
    missing = validate_config(cfg)
    assert missing == ["audiomirror_path"]


# ── generate_report ───────────────────────────────────────────────────────────

def _make_history(added=2, unmatched=1, custom=1):
    h = {}
    for i in range(added):
        h[f"Artist{i}|Track{i}"] = {
            "state": "added", "track": f"Artist{i} - Track{i}",
            "spotify_uri": f"spotify:track:id{i}", "decided_at": "2026-01-01T00:00:00",
        }
    for i in range(unmatched):
        h[f"Unknown{i}|Ghost{i}"] = {
            "state": "unmatched", "track": f"Unknown{i} - Ghost{i}",
            "spotify_uri": None, "decided_at": "2026-01-01T00:00:00",
        }
    for i in range(custom):
        h[f"Custom{i}|Rare{i}"] = {
            "state": "custom", "track": f"Custom{i} - Rare{i}",
            "spotify_uri": None, "decided_at": "2026-01-01T00:00:00",
        }
    return h

def test_generate_report_creates_file():
    import src.main as m
    original = m.REPORT_DIR
    with tempfile.TemporaryDirectory() as d:
        m.REPORT_DIR = d
        try:
            path = generate_report(_make_history(), low_conf_this_run=[], total_tracks=4)
            assert os.path.exists(path)
        finally:
            m.REPORT_DIR = original

def test_generate_report_contains_unmatched_track():
    import src.main as m
    original = m.REPORT_DIR
    with tempfile.TemporaryDirectory() as d:
        m.REPORT_DIR = d
        try:
            path = generate_report(_make_history(unmatched=1), low_conf_this_run=[], total_tracks=4)
            content = open(path, encoding="utf-8").read()
            assert "Unknown0 - Ghost0" in content
        finally:
            m.REPORT_DIR = original

def test_generate_report_contains_low_conf_match():
    import src.main as m
    original = m.REPORT_DIR
    with tempfile.TemporaryDirectory() as d:
        m.REPORT_DIR = d
        low_conf = [{"track": "Me - Song", "matched": "Them - Other Song (Album)", "confidence": "low"}]
        try:
            path = generate_report(_make_history(), low_conf_this_run=low_conf, total_tracks=4)
            content = open(path, encoding="utf-8").read()
            assert "Me - Song" in content
            assert "Them - Other Song" in content
        finally:
            m.REPORT_DIR = original

def test_generate_report_no_unmatched_shows_none_message():
    import src.main as m
    original = m.REPORT_DIR
    with tempfile.TemporaryDirectory() as d:
        m.REPORT_DIR = d
        try:
            path = generate_report(_make_history(unmatched=0), low_conf_this_run=[], total_tracks=3)
            content = open(path, encoding="utf-8").read()
            assert "all tracks matched" in content.lower() or "_None" in content
        finally:
            m.REPORT_DIR = original

def test_generate_report_counts_correct():
    import src.main as m
    original = m.REPORT_DIR
    with tempfile.TemporaryDirectory() as d:
        m.REPORT_DIR = d
        try:
            path = generate_report(_make_history(added=3, unmatched=2, custom=1), low_conf_this_run=[], total_tracks=6)
            content = open(path, encoding="utf-8").read()
            assert "| 3 |" in content  # matched count
            assert "| 2 |" in content  # unmatched count
        finally:
            m.REPORT_DIR = original
