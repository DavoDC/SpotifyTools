#!/usr/bin/env python3
"""Spotify playlist helpers: ID parsing, search links, and track listing.

Accepts a playlist ID or a full Spotify URL:
  https://open.spotify.com/playlist/EXAMPLEPLAYLISTID0000?si=...
"""

import json
import logging
import os
import re
import sys

# This file lives at <repo>/src/spotify_tools/open_playlist.py, so one
# dirname() from here always lands at <repo>/src - needed on sys.path so
# `spotify_tools` is importable even when this script isn't launched from
# inside src/.
SRC_DIR = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, SRC_DIR)

from spotify_tools.config import load_config, CONFIG_PATH
from spotify_tools.spotify_client import RealSpotifyClient
from spotify_tools.paths import REPO_ROOT

CACHE_DIR = os.path.join(REPO_ROOT, "data", "playlist_cache")
LOG_FILE = os.path.join(REPO_ROOT, "data", "logs", "open_playlist.log")


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


def build_search_url(artist: str, title: str) -> str:
    """Spotify search link for "artist title". safe="" escapes a slash or ampersand."""
    from urllib.parse import quote
    return "https://open.spotify.com/search/" + quote(f"{artist} {title}", safe="")


def format_track_lines(tracks: list[tuple[str, str]]) -> list[str]:
    """Return "artist - title" lines sorted by primary artist, then title."""
    ordered = sorted(tracks, key=lambda t: (t[0].split(' & ')[0].strip().lower(), t[1].lower()))
    return [f"{artist} - {title}" for artist, title in ordered]


def main():
    raw = input("\nEnter Spotify playlist URL: ").strip()
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

    for line in format_track_lines(tracks):
        print(line)
    logger.info(f"Printed {len(tracks)} tracks.")


if __name__ == "__main__":
    main()
