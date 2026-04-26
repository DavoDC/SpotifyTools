#!/usr/bin/env python3
"""Open Spotify playlist tracks in local music manager GUI.

Usage: python scripts/open_playlist_in_manager.py <playlist_id>
Example: python scripts/open_playlist_in_manager.py 5KdoBnznZE4q1p7ODE2871
"""

import sys
import os
import webbrowser
import logging
from urllib.parse import quote

SCRIPT_DIR = os.path.dirname(os.path.abspath(__file__))
REPO_ROOT = os.path.dirname(os.path.dirname(SCRIPT_DIR))
sys.path.insert(0, REPO_ROOT)

import spotipy
from spotipy.oauth2 import SpotifyOAuth

import json

logging.basicConfig(level=logging.DEBUG, format='%(message)s')
logger = logging.getLogger(__name__)

SCOPES = "playlist-read-private playlist-read-collaborative"
CACHE_PATH = os.path.join(REPO_ROOT, "data", ".cache")
CONFIG_PATH = os.path.join(REPO_ROOT, "config", "config.json")
MANAGER_URL = "http://localhost:6595/search"
PLAYLIST_CACHE_DIR = SCRIPT_DIR


def load_config():
    with open(CONFIG_PATH) as f:
        return json.load(f)


def get_cache_file(playlist_id: str):
    """Return path to cache file for playlist."""
    return os.path.join(PLAYLIST_CACHE_DIR, f"{playlist_id}.json")


def load_cache(playlist_id: str):
    """Load tracks from cache if exists."""
    cache_file = get_cache_file(playlist_id)
    if os.path.exists(cache_file):
        logger.info(f"Loading from cache: {cache_file}")
        with open(cache_file) as f:
            return json.load(f)
    return None


def save_cache(playlist_id: str, tracks: list):
    """Save tracks to cache file."""
    cache_file = get_cache_file(playlist_id)
    with open(cache_file, 'w') as f:
        json.dump(tracks, f, indent=2)
    logger.info(f"Cached {len(tracks)} tracks to {cache_file}")


def get_playlist_tracks(sp, playlist_id: str):
    """Fetch all tracks from a playlist."""
    logger.info(f"Fetching tracks from playlist {playlist_id}...")

    playlist = sp.playlist(playlist_id)
    logger.debug(f"Playlist response keys: {list(playlist.keys())}")
    page = playlist.get("tracks") or playlist.get("items")
    logger.debug(f"Page structure: {type(page)}, keys: {list(page.keys()) if page else 'None'}")

    tracks = []

    while page:
        items_in_page = page.get("items", [])
        logger.debug(f"Page has {len(items_in_page)} items")
        for item in items_in_page:
            if not item:
                logger.debug("Skipping None item")
                continue
            track = item.get("item") or item.get("track") or item
            if not track or not track.get("id"):
                logger.debug(f"Skipping item without id: {item.get('name', '?')}")
                continue

            artists = track.get("artists", [])
            artist_names = [a.get("name", "Unknown") for a in artists]
            artist = " & ".join(artist_names) if artist_names else "Unknown"
            title = track.get("name", "Unknown")

            tracks.append((artist, title))

        if page.get("next"):
            page = sp.next(page)
        else:
            break

    logger.info(f"Found {len(tracks)} tracks")
    return tracks


def open_track_in_manager(artist: str, title: str):
    """Build search URL and open in browser."""
    search_term = f"{artist} {title}"
    search_url = f"{MANAGER_URL}?term={quote(search_term)}"
    webbrowser.open(search_url)


def main():
    if len(sys.argv) < 2:
        print(__doc__)
        sys.exit(1)

    playlist_id = sys.argv[1]

    tracks = load_cache(playlist_id)
    if tracks:
        logger.info(f"Using cached {len(tracks)} tracks")
    else:
        config = load_config()
        os.makedirs(os.path.dirname(CACHE_PATH), exist_ok=True)
        auth = SpotifyOAuth(
            client_id=config["spotify_client_id"],
            client_secret=config["spotify_client_secret"],
            redirect_uri=config["spotify_redirect_uri"],
            scope=SCOPES,
            cache_path=CACHE_PATH,
            open_browser=False,
        )
        sp = spotipy.Spotify(auth_manager=auth)

        tracks = get_playlist_tracks(sp, playlist_id)
        if not tracks:
            logger.error("No tracks found")
            sys.exit(1)
        save_cache(playlist_id, tracks)

    logger.info(f"Opening {len(tracks)} tracks in manager...")
    for artist, title in tracks:
        logger.info(f"  {artist} - {title}")
        open_track_in_manager(artist, title)

    logger.info("Done. Check your browser.")


if __name__ == "__main__":
    main()
