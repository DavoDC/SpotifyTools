import logging
import os
import time
import spotipy
from spotipy.oauth2 import SpotifyOAuth
from src.matcher import score_match, clean_title


SCOPES = "playlist-modify-public playlist-modify-private playlist-read-private playlist-read-collaborative"

BASE_DIR   = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
CACHE_PATH = os.path.join(BASE_DIR, "data", ".cache")


def create_client(config: dict) -> spotipy.Spotify:
    os.makedirs(os.path.dirname(CACHE_PATH), exist_ok=True)
    auth = SpotifyOAuth(
        client_id=config["spotify_client_id"],
        client_secret=config["spotify_client_secret"],
        redirect_uri=config["spotify_redirect_uri"],
        scope=SCOPES,
        cache_path=CACHE_PATH,
        open_browser=True,
    )
    return spotipy.Spotify(
        auth_manager=auth,
        requests_timeout=15,           # 15s timeout per request (default is 5)
        retries=5,                     # retry transient failures up to 5 times
        status_forcelist=[429, 500, 502, 503, 504],  # auto-retry these HTTP errors
        backoff_factor=1,              # 1s, 2s, 4s, 8s, 16s between retries
    )


def _search_with_retry(sp: spotipy.Spotify, **kwargs) -> dict:
    """sp.search() with retry on 429 rate-limit and timeout errors."""
    import requests.exceptions as req_exc
    for attempt in range(3):
        try:
            return sp.search(**kwargs)
        except spotipy.exceptions.SpotifyException as e:
            if e.http_status == 429:
                retry_after = int(e.headers.get("Retry-After", 10)) if hasattr(e, "headers") and e.headers else 10
                wait = retry_after + 1
                print(f"  [rate limited] sleeping {wait}s...", flush=True)
                logging.warning(f"Rate limited (429), sleeping {wait}s")
                time.sleep(wait)
            else:
                raise
        except req_exc.Timeout:
            wait = 5 * (attempt + 1)
            print(f"  [timeout] sleeping {wait}s before retry {attempt + 1}/3...", flush=True)
            logging.warning(f"Search timed out, sleeping {wait}s (attempt {attempt + 1})")
            time.sleep(wait)
    raise RuntimeError("Search failed after 3 attempts (timeout)")


def search_track(sp: spotipy.Spotify, track: dict) -> list[dict]:
    artist = track["primary_artist"]
    title = clean_title(track["title"])
    album = track["album"]

    query = f'artist:"{artist}" track:"{title}"'
    results = _search_with_retry(sp, q=query, type="track", limit=5)
    items = results.get("tracks", {}).get("items", [])

    if not items:
        # Broader fallback search
        query = f'{artist} {title}'
        results = _search_with_retry(sp, q=query, type="track", limit=5)
        items = results.get("tracks", {}).get("items", [])

    scored = []
    for item in items:
        confidence = score_match(track, item)
        scored.append({
            "spotify_id": item["id"],
            "name": item["name"],
            "artist": item["artists"][0]["name"] if item.get("artists") else "",
            "album": (item.get("album") or {}).get("name", ""),
            "confidence": confidence,
            "uri": item["uri"],
        })

    # Sort: exact > high > low > none
    order = {"exact": 0, "high": 1, "low": 2, "none": 3}
    scored.sort(key=lambda x: order[x["confidence"]])
    return scored


def _get_track_obj(item: dict) -> dict | None:
    """Extract the track object from a playlist item, handling both API response formats.

    Spotify API response has changed over time:
    - Old format: item["track"] = track object
    - New format: item["item"] = track object (as of 2026)
    """
    return item.get("item") or item.get("track")


def get_playlist_track_ids(sp: spotipy.Spotify, playlist_id: str) -> set[str]:
    # sp.playlist() returns tracks under "items" key (current API) or "tracks" (older).
    # First page may have items=[] with total>0 — must follow "next" URL to get tracks.
    ids = set()
    playlist = sp.playlist(playlist_id)

    page = playlist.get("items") or playlist.get("tracks")
    if page is None:
        logging.warning(f"  Playlist response has no items/tracks key. Keys: {list(playlist.keys())}")
        return ids

    api_total = page.get("total", "?")
    logging.info(f"  Playlist API: total={api_total} first_page_count={len(page.get('items') or [])} has_next={bool(page.get('next'))}")

    page_num = 0
    while page:
        page_num += 1
        items = page.get("items") or []
        logging.info(f"  Paginating: page={page_num} items={len(items)} running_total={len(ids)}")
        for item in items:
            track = _get_track_obj(item) if item else None
            if track and track.get("id"):
                ids.add(track["id"])
        if page.get("next"):
            try:
                page = sp.next(page)
            except Exception as e:
                logging.warning(f"  Pagination stopped at page {page_num}: {e}")
                break
        else:
            break

    logging.info(f"  Read {len(ids)} unique track IDs (API reported total={api_total})")
    if len(ids) == 0 and api_total not in (0, "?", "0"):
        logging.warning(f"  WARNING: API says {api_total} tracks but read 0 IDs — possible API pagination issue")
    return ids


def get_playlist_items_with_positions(sp: spotipy.Spotify, playlist_id: str) -> tuple[list[tuple[str, int]], str]:
    """Return ([(uri, position), ...], snapshot_id) for all tracks in the playlist."""
    playlist = sp.playlist(playlist_id)
    snapshot_id = playlist.get("snapshot_id", "")

    items_with_pos = []
    page = playlist.get("items") or playlist.get("tracks")
    pos = 0
    while page:
        for item in (page.get("items") or []):
            track = _get_track_obj(item) if item else None
            if track and track.get("uri"):
                items_with_pos.append((track["uri"], pos))
            pos += 1
        if page.get("next"):
            try:
                page = sp.next(page)
            except Exception as e:
                logging.warning(f"  Pagination stopped at position {pos}: {e}")
                break
        else:
            break

    return items_with_pos, snapshot_id


def remove_playlist_duplicates(sp: spotipy.Spotify, playlist_id: str) -> int:
    """Remove duplicate tracks from the playlist, keeping the first occurrence.
    Returns the number of duplicate entries removed."""
    items_with_pos, snapshot_id = get_playlist_items_with_positions(sp, playlist_id)

    if not items_with_pos:
        return 0

    # Collect extra positions for each URI (skip first occurrence)
    seen: set[str] = set()
    dupes: dict[str, list[int]] = {}
    for uri, position in items_with_pos:
        if uri in seen:
            dupes.setdefault(uri, []).append(position)
        else:
            seen.add(uri)

    if not dupes:
        return 0

    total = sum(len(p) for p in dupes.values())

    # Flatten duplicate URIs into a single list (one entry per extra occurrence to remove)
    # DELETE /playlists/{id}/items — new endpoint uses "items" key (not "tracks")
    # No positions support — each item here is one extra occurrence to delete
    items_to_delete = []
    for uri, positions in dupes.items():
        for _ in positions:
            items_to_delete.append({"uri": uri})

    plid = sp._get_id("playlist", playlist_id)
    for i in range(0, len(items_to_delete), 100):
        batch = items_to_delete[i:i + 100]
        payload = {"items": batch}
        if snapshot_id:
            payload["snapshot_id"] = snapshot_id
        sp._delete(f"playlists/{plid}/items", payload=payload)

    logging.info(f"  Removed {total} duplicate track entries from playlist")
    return total


def add_tracks_to_playlist(sp: spotipy.Spotify, playlist_id: str, track_uris: list[str]):
    # POST /playlists/{id}/items — current non-deprecated endpoint (max 100 per request)
    # sp.playlist_add_items() uses the deprecated /tracks endpoint and returns 403
    # Payload must be {"uris": [...]} — bare list is not accepted
    plid = sp._get_id("playlist", playlist_id)
    for i in range(0, len(track_uris), 100):
        batch = track_uris[i:i+100]
        sp._post(f"playlists/{plid}/items", payload={"uris": batch})
