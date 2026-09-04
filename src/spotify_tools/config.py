"""Configuration loading and validation."""

import json
import os
import logging

from spotify_tools.paths import REPO_ROOT

CONFIG_PATH = os.path.join(REPO_ROOT, "config", "config.json")

REQUIRED_KEYS = [
    "spotify_client_id",
    "spotify_client_secret",
    "spotify_redirect_uri",
    "spotify_playlist_id",
    "audiomirror_path",
]


def load_config(path: str = CONFIG_PATH) -> dict:
    """Load config from JSON file. Returns empty dict if missing."""
    if not os.path.exists(path):
        return {}
    with open(path, "r", encoding="utf-8") as f:
        return json.load(f)


def validate_config(config: dict) -> list[str]:
    """Return list of missing/empty required config keys."""
    return [k for k in REQUIRED_KEYS if not config.get(k)]
