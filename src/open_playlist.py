#!/usr/bin/env python3
"""Open Spotify playlist tracks in local music manager GUI.

Accepts a playlist ID or a full Spotify URL:
  https://open.spotify.com/playlist/5KdoBnznZE4q1p7ODE2871?si=...
"""

import json
import logging
import os
import re
import sys
import webbrowser
from urllib.parse import quote_plus

BASE_DIR = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, BASE_DIR)

from src.config import load_config, CONFIG_PATH
from src.spotify_client import RealSpotifyClient

MANAGER_URL = "http://localhost:6595/search"
CACHE_DIR = os.path.join(BASE_DIR, "data", "playlist_cache")
LOG_FILE = os.path.join(BASE_DIR, "data", "logs", "open_playlist.log")


def _setup_logging():
    os.makedirs(os.path.dirname(LOG_FILE), exist_ok=True)
    logger = logging.getLogger()
    logger.setLevel(logging.DEBUG)

    fh = logging.FileHandler(LOG_FILE, mode="w")
    fh.setLevel(logging.DEBUG)
    fh.setFormatter(logging.Formatter("%(message)s"))

    ch = logging.StreamHandler()
    ch.setLevel(logging.INFO)
    ch.setFormatter(logging.Formatter("%(message)s"))

    logger.addHandler(fh)
    logger.addHandler(ch)
    return logging.getLogger(__name__)


logger = _setup_logging()


def extract_playlist_id(value: str) -> str:
    """Accept raw ID or Spotify URL, return playlist ID."""
    match = re.search(r'playlist/([A-Za-z0-9]+)', value)
    return match.group(1) if match else value.strip()


def _cache_path(playlist_id: str) -> str:
    os.makedirs(CACHE_DIR, exist_ok=True)
    return os.path.join(CACHE_DIR, f"{playlist_id}.json")


def _load_cache(playlist_id: str) -> list | None:
    path = _cache_path(playlist_id)
    if os.path.exists(path):
        logger.info(f"Loading from cache: {path}")
        with open(path) as f:
            return json.load(f)
    return None


def _save_cache(playlist_id: str, tracks: list):
    path = _cache_path(playlist_id)
    with open(path, "w") as f:
        json.dump(tracks, f, indent=2)
    logger.info(f"Cached {len(tracks)} tracks to {path}")


def _open_in_manager(artist: str, title: str):
    url = f"{MANAGER_URL}?term={quote_plus(f'{artist} {title}')}"
    webbrowser.open(url)


def main():
    raw = input("\nEnter Spotify playlist ID or URL: ").strip()
    if not raw:
        print("No input provided.")
        sys.exit(1)

    playlist_id = extract_playlist_id(raw)
    logger.info(f"Playlist ID: {playlist_id}")
    logger.info(f"Log: {LOG_FILE}")

    tracks = _load_cache(playlist_id)
    if tracks:
        logger.info(f"Using cached {len(tracks)} tracks")
    else:
        config = load_config(CONFIG_PATH)
        if not config:
            logger.error(f"Config not found at {CONFIG_PATH}")
            sys.exit(1)

        client = RealSpotifyClient(config)
        tracks = client.get_playlist_tracks(playlist_id)
        if not tracks:
            logger.error("No tracks found")
            sys.exit(1)
        _save_cache(playlist_id, tracks)

    logger.info(f"Opening {len(tracks)} tracks in manager...")
    for artist, title in tracks:
        logger.info(f"  {artist} - {title}")
        _open_in_manager(artist, title)

    logger.info("Done. Check your browser.")


if __name__ == "__main__":
    main()
