"""Tests for src/config.py — config loading and validation."""

import json
import os
import tempfile

from spotify_tools.config import CONFIG_PATH, load_config, validate_config


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


def test_config_path_resolves_to_a_real_file():
    """CONFIG_PATH (no override) must point at a file that actually exists.

    Regression test for the 2026-09-02 off-by-one bug: moving config.py from
    spotify_tools/ to src/spotify_tools/ added a directory level that BASE_DIR's
    dirname() count didn't account for, so CONFIG_PATH silently pointed at
    src/config/config.json instead of config/config.json. Every other test in
    this file passes an explicit path= and would stay green regardless.
    """
    assert os.path.exists(CONFIG_PATH), CONFIG_PATH


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
