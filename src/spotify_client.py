"""Real Spotify API client — all network access isolated here.

Implements SpotifyInterface using spotipy. No other module may call spotipy directly.
Handles retries, rate limits, pagination, response format variations, batch splitting.
"""

import logging
import os
import time

import spotipy
from spotipy.oauth2 import SpotifyOAuth

from src.spotify_interface import SpotifyInterface, AddResult, RemoveResult
from src.matcher import clean_title, clean_artist, score_match

SCOPES = "playlist-modify-public playlist-modify-private playlist-read-private playlist-read-collaborative"

BASE_DIR = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
CACHE_PATH = os.path.join(BASE_DIR, "data", ".cache")

MAX_RETRY = 3
BATCH_SIZE = 100


def _get_track_obj(item: dict) -> dict | None:
    """Extract track object from playlist item, handling both API formats.

    Current (2026): item["item"] = track object
    Old format: item["track"] = track object
    """
    return item.get("item") or item.get("track")


def _retry_call(sp, method_name: str, *args, **kwargs):
    """Generic retry wrapper for any Spotify API call."""
    import requests.exceptions as req_exc
    func = getattr(sp, method_name)
    logging.debug(f"[API] {method_name} args={args[:1] if args else ''} kwargs_keys={list(kwargs.keys())}")
    for attempt in range(MAX_RETRY):
        try:
            result = func(*args, **kwargs)
            logging.debug(f"[API] {method_name} succeeded (attempt {attempt + 1})")
            return result
        except spotipy.exceptions.SpotifyException as e:
            if e.http_status == 429:
                retry_after = int(e.headers.get("Retry-After", 10)) if hasattr(e, "headers") and e.headers else 10
                wait = retry_after + 1
                logging.warning(f"Rate limited on {method_name} (429), sleeping {wait}s")
                time.sleep(wait)
            elif e.http_status in (500, 502, 503, 504):
                wait = 2 ** attempt
                logging.warning(f"Server error {e.http_status} on {method_name}, retry {attempt + 1}/{MAX_RETRY} in {wait}s")
                time.sleep(wait)
            else:
                raise
        except req_exc.Timeout:
            wait = 5 * (attempt + 1)
            logging.warning(f"Timeout on {method_name}, retry {attempt + 1}/{MAX_RETRY} in {wait}s")
            time.sleep(wait)
    raise RuntimeError(f"{method_name} failed after {MAX_RETRY} attempts")


class RealSpotifyClient(SpotifyInterface):
    """Production Spotify client wrapping spotipy."""

    def __init__(self, config: dict):
        os.makedirs(os.path.dirname(CACHE_PATH), exist_ok=True)
        auth = SpotifyOAuth(
            client_id=config["spotify_client_id"],
            client_secret=config["spotify_client_secret"],
            redirect_uri=config["spotify_redirect_uri"],
            scope=SCOPES,
            cache_path=CACHE_PATH,
            open_browser=True,
        )
        self._sp = spotipy.Spotify(
            auth_manager=auth,
            requests_timeout=15,
            retries=5,
            status_forcelist=[500, 502, 503, 504],
            backoff_factor=1,
        )

    def current_user(self) -> dict:
        return self._sp.current_user()

    def search_track(self, track: dict) -> list[dict]:
        raw_artist = track["primary_artist"]
        raw_title = track["title"]
        artist = clean_artist(raw_artist)
        title = clean_title(raw_title)

        label = f"{raw_artist} - {raw_title}"
        if artist != raw_artist or title != raw_title:
            logging.debug(f"[SEARCH] {label} -> cleaned to: {artist} - {title}")

        # Strict search first
        query = f'artist:"{artist}" track:"{title}"'
        logging.debug(f"[SEARCH] query={query}")
        results = _retry_call(self._sp, "search", q=query, type="track", limit=5)
        items = results.get("tracks", {}).get("items", [])
        logging.debug(f"[SEARCH] strict: {len(items)} results")

        used_fallback = False
        if not items:
            # Broad fallback
            query = f'{artist} {title}'
            logging.debug(f"[SEARCH] fallback query={query}")
            results = _retry_call(self._sp, "search", q=query, type="track", limit=5)
            items = results.get("tracks", {}).get("items", [])
            used_fallback = True
            logging.debug(f"[SEARCH] fallback: {len(items)} results")

        if not items:
            logging.debug(f"[SEARCH] ZERO results for {label} (tried strict + fallback)")

        scored = []
        for item in items:
            confidence = score_match(track, item)
            r_artist = item["artists"][0]["name"] if item.get("artists") else ""
            r_title = item.get("name", "")
            r_album = (item.get("album") or {}).get("name", "")
            scored.append({
                "spotify_id": item["id"],
                "name": r_title,
                "artist": r_artist,
                "album": r_album,
                "confidence": confidence,
                "uri": item["uri"],
            })
            logging.debug(f"[MATCH] {confidence.upper():>5} | {r_artist} - {r_title} ({r_album}) | uri={item['uri']}")

        order = {"exact": 0, "high": 1, "low": 2, "none": 3}
        scored.sort(key=lambda x: order[x["confidence"]])

        best = scored[0] if scored else None
        if best:
            logging.debug(f"[RESULT] {label} -> {best['confidence'].upper()}: {best['artist']} - {best['name']} (fallback={'yes' if used_fallback else 'no'})")
        else:
            logging.debug(f"[RESULT] {label} -> NO MATCH")

        return scored

    def get_playlist_uris(self, playlist_id: str) -> set[str]:
        playlist = self._sp.playlist(playlist_id)

        page = playlist.get("items") or playlist.get("tracks")
        if page is None:
            logging.warning(f"Playlist response has no items/tracks key. Keys: {list(playlist.keys())}")
            return set()

        api_total = page.get("total", "?")
        logging.info(f"Playlist API: total={api_total}")

        uris = set()
        page_num = 0
        while page:
            page_num += 1
            items = page.get("items") or []
            for item in items:
                track = _get_track_obj(item) if item else None
                if track and track.get("uri"):
                    uris.add(track["uri"])
            if page.get("next"):
                try:
                    page = self._sp.next(page)
                except Exception as e:
                    logging.warning(f"Pagination stopped at page {page_num}: {e}")
                    break
            else:
                break

        logging.info(f"Read {len(uris)} unique track URIs (API reported total={api_total})")

        if len(uris) == 0 and api_total not in (0, "?", "0"):
            raise RuntimeError(
                f"Playlist API reported {api_total} tracks but 0 URIs were read. "
                "The API response structure may have changed."
            )

        return uris

    def add_tracks(self, playlist_id: str, uris: list[str]) -> AddResult:
        if not uris:
            return AddResult()

        plid = self._sp._get_id("playlist", playlist_id)
        succeeded = []
        failed = []

        for i in range(0, len(uris), BATCH_SIZE):
            batch = uris[i:i + BATCH_SIZE]
            try:
                _retry_call(self._sp, "_post", f"playlists/{plid}/items", payload={"uris": batch})
                succeeded.extend(batch)
                logging.info(f"Added batch of {len(batch)} tracks")
            except Exception as e:
                failed.extend(batch)
                logging.error(f"Failed to add batch of {len(batch)} tracks: {e}")

        return AddResult(succeeded=succeeded, failed=failed)

    def remove_tracks(self, playlist_id: str, uris: list[str]) -> RemoveResult:
        if not uris:
            return RemoveResult()

        plid = self._sp._get_id("playlist", playlist_id)
        removed = 0

        for i in range(0, len(uris), BATCH_SIZE):
            batch = uris[i:i + BATCH_SIZE]
            items_to_delete = [{"uri": uri} for uri in batch]
            try:
                _retry_call(self._sp, "_delete", f"playlists/{plid}/items", payload={"items": items_to_delete})
                removed += len(batch)
                logging.info(f"Removed batch of {len(batch)} tracks")
            except Exception as e:
                logging.error(f"Failed to remove batch: {e}")
                return RemoveResult(removed_count=removed, failed=True)

        return RemoveResult(removed_count=removed)

    def find_duplicates(self, playlist_id: str) -> dict[str, int]:
        playlist = self._sp.playlist(playlist_id)

        page = playlist.get("items") or playlist.get("tracks")
        seen: set[str] = set()
        dupes: dict[str, int] = {}

        while page:
            for item in (page.get("items") or []):
                track = _get_track_obj(item) if item else None
                if track and track.get("uri"):
                    uri = track["uri"]
                    if uri in seen:
                        dupes[uri] = dupes.get(uri, 0) + 1
                    else:
                        seen.add(uri)
            if page.get("next"):
                try:
                    page = self._sp.next(page)
                except Exception:
                    break
            else:
                break

        return dupes
