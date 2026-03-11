"""Tests for src/config.py — config loading and validation."""

import json
import os
import tempfile

from src.config import load_config, validate_config


FULL_CONFIG = {
    "spotify_client_id": "id",
    "spotify_client_secret": "secret",
    "spotify_redirect_uri": "http://localhost:8888",
    "spotify_playlist_id": "playlistid",
    "audiomirror_path": "/some/path",
}


# ── load_config ──────────────────────────────────────────────────────────────

def test_load_config_returns_empty_dict_if_missing():
    assert load_config("/nonexistent/path/config.json") == {}


def test_load_config_reads_valid_file():
    with tempfile.NamedTemporaryFile(mode="w", suffix=".json", delete=False) as f:
        json.dump(FULL_CONFIG, f)
        path = f.name
    try:
        result = load_config(path)
        assert result == FULL_CONFIG
    finally:
        os.unlink(path)


# ── validate_config ──────────────────────────────────────────────────────────

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


def test_validate_config_catches_all_missing():
    assert len(validate_config({})) == 5


def test_validate_config_returns_only_missing():
    cfg = {**FULL_CONFIG, "audiomirror_path": ""}
    missing = validate_config(cfg)
    assert missing == ["audiomirror_path"]
