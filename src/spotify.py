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
    return spotipy.Spotify(auth_manager=auth)


def _search_with_retry(sp: spotipy.Spotify, **kwargs) -> dict:
    """sp.search() with a single retry on 429 rate-limit response."""
    try:
        return sp.search(**kwargs)
    except spotipy.exceptions.SpotifyException as e:
        if e.http_status == 429:
            retry_after = int(e.headers.get("Retry-After", 5)) if hasattr(e, "headers") and e.headers else 5
            time.sleep(retry_after + 1)
            return sp.search(**kwargs)
        raise


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


def get_playlist_track_ids(sp: spotipy.Spotify, playlist_id: str) -> set[str]:
    # Use sp.playlist() — the /tracks endpoint is deprecated and returns 403.
    # Current API returns the paged track collection under the "items" key.
    ids = set()
    playlist = sp.playlist(playlist_id)
    results = playlist.get("items") or playlist.get("tracks")
    while results:
        for item in results["items"]:
            if item.get("track") and item["track"].get("id"):
                ids.add(item["track"]["id"])
        results = sp.next(results) if results.get("next") else None
    return ids


def add_tracks_to_playlist(sp: spotipy.Spotify, playlist_id: str, track_uris: list[str]):
    # POST /playlists/{id}/items — current non-deprecated endpoint (max 100 per request)
    # sp.playlist_add_items() uses the deprecated /tracks endpoint and returns 403
    # Payload must be {"uris": [...]} — bare list is not accepted
    plid = sp._get_id("playlist", playlist_id)
    for i in range(0, len(track_uris), 100):
        batch = track_uris[i:i+100]
        sp._post(f"playlists/{plid}/items", payload={"uris": batch})
