"""
Tests for src/spotify.py.
All Spotify API calls are mocked — no real network access.
"""
import pytest
from unittest.mock import MagicMock, call
import spotipy

from src.spotify import search_track, get_playlist_track_ids, add_tracks_to_playlist


# ── Helpers ───────────────────────────────────────────────────────────────────

def sp_track(name, artist, album, uri="spotify:track:abc", track_id="abc"):
    return {
        "id": track_id,
        "name": name,
        "artists": [{"name": artist}],
        "album": {"name": album},
        "uri": uri,
    }


def search_response(items):
    return {"tracks": {"items": items}}


def playlist_page(ids, next_url=None):
    return {
        "items": [{"track": {"id": i}} for i in ids],
        "next": next_url,
    }


# ── search_track ──────────────────────────────────────────────────────────────

def test_search_track_returns_scored_results():
    sp = MagicMock()
    track = {"primary_artist": "Eminem", "title": "Lose Yourself", "album": "8 Mile"}
    sp.search.return_value = search_response([sp_track("Lose Yourself", "Eminem", "8 Mile", uri="spotify:track:xyz")])

    results = search_track(sp, track)

    assert len(results) == 1
    assert results[0]["uri"] == "spotify:track:xyz"
    assert results[0]["confidence"] in ("exact", "high", "low", "none")


def test_search_track_sorted_best_first():
    sp = MagicMock()
    track = {"primary_artist": "Eminem", "title": "Lose Yourself", "album": "8 Mile"}
    items = [
        sp_track("Something Else", "Other Artist", "Other Album", uri="uri:bad", track_id="bad"),
        sp_track("Lose Yourself", "Eminem", "8 Mile", uri="uri:good", track_id="good"),
    ]
    sp.search.return_value = search_response(items)

    results = search_track(sp, track)
    assert results[0]["uri"] == "uri:good"


def test_search_track_fallback_when_strict_empty():
    sp = MagicMock()
    track = {"primary_artist": "Eminem", "title": "Lose Yourself", "album": "8 Mile"}
    sp.search.side_effect = [
        search_response([]),
        search_response([sp_track("Lose Yourself", "Eminem", "8 Mile")]),
    ]

    results = search_track(sp, track)

    assert len(results) == 1
    assert sp.search.call_count == 2


def test_search_track_returns_empty_when_both_empty():
    sp = MagicMock()
    track = {"primary_artist": "Unknown", "title": "No Such Track", "album": "Nothing"}
    sp.search.return_value = search_response([])

    results = search_track(sp, track)
    assert results == []


def test_search_track_empty_artists_does_not_crash():
    # Spotify API can return tracks with empty artists list — must not IndexError
    sp = MagicMock()
    track = {"primary_artist": "Eminem", "title": "Lose Yourself", "album": "8 Mile"}
    bad_item = sp_track("Lose Yourself", "Eminem", "8 Mile")
    bad_item["artists"] = []
    sp.search.return_value = search_response([bad_item])

    results = search_track(sp, track)
    assert isinstance(results, list)


def test_search_track_missing_album_does_not_crash():
    # Spotify API can return tracks with None album
    sp = MagicMock()
    track = {"primary_artist": "Eminem", "title": "Lose Yourself", "album": "8 Mile"}
    bad_item = sp_track("Lose Yourself", "Eminem", "8 Mile")
    bad_item["album"] = None
    sp.search.return_value = search_response([bad_item])

    # Should not raise
    try:
        results = search_track(sp, track)
        assert isinstance(results, list)
    except (TypeError, AttributeError):
        pytest.fail("search_track crashed on None album from Spotify")


# ── get_playlist_track_ids ────────────────────────────────────────────────────

def test_get_playlist_track_ids_returns_ids():
    # Current Spotify API returns paged tracks under "items" key
    sp = MagicMock()
    sp.playlist.return_value = {"items": playlist_page(["id1", "id2"])}

    ids = get_playlist_track_ids(sp, "playlist123")

    assert ids == {"id1", "id2"}


def test_get_playlist_track_ids_falls_back_to_tracks_key():
    # Older API / spotipy versions return "tracks" key — must handle both
    sp = MagicMock()
    sp.playlist.return_value = {"tracks": playlist_page(["id1", "id2"])}

    ids = get_playlist_track_ids(sp, "playlist123")

    assert ids == {"id1", "id2"}


def test_get_playlist_track_ids_handles_pagination():
    sp = MagicMock()
    sp.playlist.return_value = {"items": playlist_page(["id1"], next_url="http://next")}
    sp.next.return_value = playlist_page(["id2"])

    ids = get_playlist_track_ids(sp, "playlist123")

    assert ids == {"id1", "id2"}
    sp.next.assert_called_once()


def test_get_playlist_track_ids_skips_null_tracks():
    sp = MagicMock()
    sp.playlist.return_value = {"items": {
        "items": [{"track": None}, {"track": {"id": "id1"}}, {"track": {"id": None}}],
        "next": None,
    }}

    ids = get_playlist_track_ids(sp, "playlist123")

    assert ids == {"id1"}


def test_get_playlist_track_ids_empty_playlist():
    sp = MagicMock()
    sp.playlist.return_value = {"items": playlist_page([])}

    ids = get_playlist_track_ids(sp, "playlist123")

    assert ids == set()


def test_get_playlist_track_ids_uses_playlist_not_tracks_endpoint():
    """Must use sp.playlist() not sp.playlist_tracks() — /tracks endpoint is deprecated."""
    sp = MagicMock()
    sp.playlist.return_value = {"items": playlist_page(["id1"])}

    get_playlist_track_ids(sp, "playlist123")

    sp.playlist.assert_called_once_with("playlist123")
    sp.playlist_tracks.assert_not_called()


# ── add_tracks_to_playlist ────────────────────────────────────────────────────

def test_add_tracks_single_batch():
    sp = MagicMock()
    uris = ["uri:1", "uri:2", "uri:3"]

    add_tracks_to_playlist(sp, "playlist123", uris)

    sp.playlist_add_items.assert_called_once_with("playlist123", uris)


def test_add_tracks_batches_over_100():
    sp = MagicMock()
    uris = [f"uri:{i}" for i in range(250)]

    add_tracks_to_playlist(sp, "playlist123", uris)

    assert sp.playlist_add_items.call_count == 3
    calls = sp.playlist_add_items.call_args_list
    assert len(calls[0][0][1]) == 100
    assert len(calls[1][0][1]) == 100
    assert len(calls[2][0][1]) == 50


def test_add_tracks_empty_list_makes_no_calls():
    sp = MagicMock()

    add_tracks_to_playlist(sp, "playlist123", [])

    sp.playlist_add_items.assert_not_called()
