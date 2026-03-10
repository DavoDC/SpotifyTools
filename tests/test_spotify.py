"""
Tests for src/spotify.py.
All Spotify API calls are mocked — no real network access.

IMPORTANT: Spotify API returns playlist items under an "item" key (as of 2026),
NOT "track". Tests must use the current format. Old "track" key tests are kept
for backward compatibility. This was a real production bug — see git history.
"""
import pytest
from unittest.mock import MagicMock, call
import spotipy

from src.spotify import search_track, get_playlist_track_ids, add_tracks_to_playlist, remove_playlist_duplicates, _get_track_obj


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
    """Current Spotify API format: each item uses "item" key (NOT "track")."""
    return {
        "items": [{"item": {"id": i, "uri": f"spotify:track:{i}"}} for i in ids],
        "next": next_url,
    }


def playlist_page_old_format(ids, next_url=None):
    """Old Spotify API format: each item uses "track" key. Keep for compat tests."""
    return {
        "items": [{"track": {"id": i, "uri": f"spotify:track:{i}"}} for i in ids],
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


# ── _get_track_obj ────────────────────────────────────────────────────────────

def test_get_track_obj_new_format():
    """Current API (2026+): track object is under "item" key."""
    item = {"item": {"id": "abc", "uri": "spotify:track:abc"}}
    assert _get_track_obj(item)["id"] == "abc"


def test_get_track_obj_old_format():
    """Old API: track object was under "track" key — must still work."""
    item = {"track": {"id": "abc", "uri": "spotify:track:abc"}}
    assert _get_track_obj(item)["id"] == "abc"


def test_get_track_obj_prefers_item_over_track():
    """If both keys exist, "item" takes priority (current format)."""
    item = {"item": {"id": "new"}, "track": {"id": "old"}}
    assert _get_track_obj(item)["id"] == "new"


def test_get_track_obj_returns_none_when_neither_key():
    item = {"added_at": "2024-01-01"}
    assert _get_track_obj(item) is None


def test_get_track_obj_returns_none_for_null_item():
    item = {"item": None, "track": None}
    assert _get_track_obj(item) is None


# ── get_playlist_track_ids ────────────────────────────────────────────────────

def test_get_playlist_track_ids_new_api_format():
    """Regression test: current Spotify API uses "item" key, not "track".
    This test would have caught the 2026 duplication bug before it ran."""
    sp = MagicMock()
    sp.playlist.return_value = {"items": playlist_page(["id1", "id2"])}

    ids = get_playlist_track_ids(sp, "playlist123")

    # If this fails with ids==set(), the "item"/"track" key mapping is broken
    assert ids == {"id1", "id2"}, (
        "Expected 2 IDs but got 0. "
        "Likely cause: Spotify API changed track key from 'track' to 'item' and code wasn't updated."
    )


def test_get_playlist_track_ids_old_track_key_still_works():
    """Backward compat: old API format with "track" key must still return IDs."""
    sp = MagicMock()
    sp.playlist.return_value = {"items": playlist_page_old_format(["id1", "id2"])}

    ids = get_playlist_track_ids(sp, "playlist123")

    assert ids == {"id1", "id2"}


def test_get_playlist_track_ids_falls_back_to_tracks_key():
    """Older spotipy versions wrap tracks under a "tracks" key — must handle both."""
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
    """Tracks deleted from Spotify catalog have null item objects — must skip, not crash."""
    sp = MagicMock()
    sp.playlist.return_value = {"items": {
        "items": [
            {"item": None},
            {"item": {"id": "id1", "uri": "spotify:track:id1"}},
            {"item": {"id": None}},
        ],
        "next": None,
    }}

    ids = get_playlist_track_ids(sp, "playlist123")

    assert ids == {"id1"}


def test_get_playlist_track_ids_empty_playlist():
    sp = MagicMock()
    sp.playlist.return_value = {"items": playlist_page([])}

    ids = get_playlist_track_ids(sp, "playlist123")

    assert ids == set()


def test_get_playlist_track_ids_nonzero_total_but_zero_ids_is_detectable():
    """Regression: if API says total=500 but we read 0 IDs, something is structurally wrong.
    The function itself returns empty set — caller must check and NOT proceed with uploads."""
    sp = MagicMock()
    # Simulate broken response: items present but none have recognised track keys
    sp.playlist.return_value = {"items": {
        "items": [{"unknown_key": {"id": "abc"}} for _ in range(100)],
        "next": None,
        "total": 100,
    }}

    ids = get_playlist_track_ids(sp, "playlist123")

    # Function returns empty — caller (main.py) must treat 0-ids-from-nonzero-total as error
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
    sp._get_id.return_value = "playlist123"
    uris = ["uri:1", "uri:2", "uri:3"]

    add_tracks_to_playlist(sp, "playlist123", uris)

    sp._post.assert_called_once_with("playlists/playlist123/items", payload={"uris": uris})


def test_add_tracks_uses_items_endpoint_not_tracks():
    """Must use /items endpoint — /tracks endpoint is deprecated and returns 403."""
    sp = MagicMock()
    sp._get_id.return_value = "playlist123"

    add_tracks_to_playlist(sp, "playlist123", ["uri:1"])

    call_url = sp._post.call_args[0][0]
    assert call_url.endswith("/items"), f"Expected /items endpoint, got: {call_url}"
    assert "/tracks" not in call_url


def test_add_tracks_batches_over_100():
    sp = MagicMock()
    sp._get_id.return_value = "playlist123"
    uris = [f"uri:{i}" for i in range(250)]

    add_tracks_to_playlist(sp, "playlist123", uris)

    assert sp._post.call_count == 3
    calls = sp._post.call_args_list
    assert len(calls[0][1]["payload"]["uris"]) == 100
    assert len(calls[1][1]["payload"]["uris"]) == 100
    assert len(calls[2][1]["payload"]["uris"]) == 50


def test_add_tracks_empty_list_makes_no_calls():
    sp = MagicMock()
    sp._get_id.return_value = "playlist123"

    add_tracks_to_playlist(sp, "playlist123", [])

    sp._post.assert_not_called()


# ── remove_playlist_duplicates ────────────────────────────────────────────────

def _mock_playlist_page(uris, next_url=None, snapshot_id="snap1"):
    """Build a mock sp.playlist() response with given track URIs.
    Uses the CURRENT API format: "item" key (not "track")."""
    items = [{"item": {"uri": u, "id": u.split(":")[-1]}} for u in uris]
    return {
        "snapshot_id": snapshot_id,
        "items": {"items": items, "next": next_url, "total": len(items)},
    }


def test_remove_duplicates_no_dupes_makes_no_delete():
    sp = MagicMock()
    sp._get_id.return_value = "pl123"
    sp.playlist.return_value = _mock_playlist_page(
        ["spotify:track:a", "spotify:track:b", "spotify:track:c"]
    )

    result = remove_playlist_duplicates(sp, "pl123")

    assert result == 0
    sp._delete.assert_not_called()


def test_remove_duplicates_finds_one_dupe():
    sp = MagicMock()
    sp._get_id.return_value = "pl123"
    # URI "a" appears at positions 0 and 2
    sp.playlist.return_value = {
        "snapshot_id": "snap1",
        "items": {
            "items": [
                {"item": {"uri": "spotify:track:a", "id": "a"}},
                {"item": {"uri": "spotify:track:b", "id": "b"}},
                {"item": {"uri": "spotify:track:a", "id": "a"}},  # duplicate at pos 2
            ],
            "next": None,
            "total": 3,
        },
    }

    result = remove_playlist_duplicates(sp, "pl123")

    assert result == 1
    sp._delete.assert_called_once()
    payload = sp._delete.call_args[1]["payload"]
    assert payload["snapshot_id"] == "snap1"
    # New /items endpoint uses "items" key (not "tracks"), and no "positions" field
    assert "items" in payload
    assert len(payload["items"]) == 1
    assert payload["items"][0]["uri"] == "spotify:track:a"
    assert "positions" not in payload["items"][0]


def test_remove_duplicates_multiple_dupes():
    sp = MagicMock()
    sp._get_id.return_value = "pl123"
    # "a" at 0,2,4 — two dupes. "b" at 1,3 — one dupe.
    sp.playlist.return_value = {
        "snapshot_id": "snap1",
        "items": {
            "items": [
                {"item": {"uri": "spotify:track:a", "id": "a"}},  # pos 0 — kept
                {"item": {"uri": "spotify:track:b", "id": "b"}},  # pos 1 — kept
                {"item": {"uri": "spotify:track:a", "id": "a"}},  # pos 2 — dupe
                {"item": {"uri": "spotify:track:b", "id": "b"}},  # pos 3 — dupe
                {"item": {"uri": "spotify:track:a", "id": "a"}},  # pos 4 — dupe
            ],
            "next": None,
            "total": 5,
        },
    }

    result = remove_playlist_duplicates(sp, "pl123")

    assert result == 3  # 2 extra "a"s + 1 extra "b"
    payload = sp._delete.call_args[1]["payload"]
    uris = [t["uri"] for t in payload["items"]]
    assert uris.count("spotify:track:a") == 2
    assert uris.count("spotify:track:b") == 1


def test_remove_duplicates_empty_playlist_returns_zero():
    sp = MagicMock()
    sp.playlist.return_value = {
        "snapshot_id": "snap1",
        "items": {"items": [], "next": None, "total": 0},
    }

    result = remove_playlist_duplicates(sp, "pl123")

    assert result == 0
    sp._delete.assert_not_called()
