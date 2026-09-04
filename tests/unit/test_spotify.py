"""
Tests for src/spotify_client.py (RealSpotifyClient) and src/spotify_simulator.py.
All Spotify API calls are mocked — no real network access.

IMPORTANT: Spotify API returns playlist items under an "item" key (as of 2026),
NOT "track". Tests must use the current format.
"""
import pytest
from unittest.mock import MagicMock, patch
import spotipy

from spotify_tools.spotify_client import RealSpotifyClient, _get_track_obj
from spotify_tools.spotify_simulator import SimulatedSpotifyClient
from spotify_tools.spotify_interface import AddResult, RemoveResult


# ── Helpers ──────────────────────────────────────────────────────────────────

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
    """Old Spotify API format: each item uses "track" key."""
    return {
        "items": [{"track": {"id": i, "uri": f"spotify:track:{i}"}} for i in ids],
        "next": next_url,
    }


# ── _get_track_obj ───────────────────────────────────────────────────────────

def test_get_track_obj_new_format():
    item = {"item": {"id": "abc", "uri": "spotify:track:abc"}}
    assert _get_track_obj(item)["id"] == "abc"

def test_get_track_obj_old_format():
    item = {"track": {"id": "abc", "uri": "spotify:track:abc"}}
    assert _get_track_obj(item)["id"] == "abc"

def test_get_track_obj_prefers_item_over_track():
    item = {"item": {"id": "new"}, "track": {"id": "old"}}
    assert _get_track_obj(item)["id"] == "new"

def test_get_track_obj_returns_none_when_neither_key():
    item = {"added_at": "2024-01-01"}
    assert _get_track_obj(item) is None

def test_get_track_obj_returns_none_for_null_item():
    item = {"item": None, "track": None}
    assert _get_track_obj(item) is None


# ── SimulatedSpotifyClient ───────────────────────────────────────────────────

def test_simulator_empty_fixture():
    client = SimulatedSpotifyClient()
    assert client.get_playlist_uris("any") == set()
    assert client.playlist_contents == []


def test_simulator_search_returns_fixture_data():
    fixture = {
        "search_responses": {
            "Eminem|Lose Yourself": [
                {"spotify_id": "abc", "name": "Lose Yourself", "artist": "Eminem",
                 "album": "8 Mile", "confidence": "exact", "uri": "spotify:track:abc"}
            ]
        }
    }
    client = SimulatedSpotifyClient(fixture_data=fixture)
    results = client.search_track({"primary_artist": "Eminem", "title": "Lose Yourself"})
    assert len(results) == 1
    assert results[0]["confidence"] == "exact"


def test_simulator_search_no_match():
    fixture = {"search_responses": {"Unknown|Ghost": []}}
    client = SimulatedSpotifyClient(fixture_data=fixture)
    results = client.search_track({"primary_artist": "Unknown", "title": "Ghost"})
    assert results == []


def test_simulator_add_tracks():
    client = SimulatedSpotifyClient()
    result = client.add_tracks("pl", ["spotify:track:a", "spotify:track:b"])
    assert result.succeeded == ["spotify:track:a", "spotify:track:b"]
    assert set(client.playlist_contents) == {"spotify:track:a", "spotify:track:b"}


def test_simulator_add_no_duplicates():
    client = SimulatedSpotifyClient(fixture_data={"initial_playlist": ["spotify:track:a"]})
    client.add_tracks("pl", ["spotify:track:a", "spotify:track:b"])
    assert client.playlist_contents.count("spotify:track:a") == 1


def test_simulator_remove_tracks():
    client = SimulatedSpotifyClient(fixture_data={"initial_playlist": ["spotify:track:a", "spotify:track:b"]})
    result = client.remove_tracks("pl", ["spotify:track:a"])
    assert result.removed_count == 1
    assert client.playlist_contents == ["spotify:track:b"]


def test_simulator_operations_logged():
    client = SimulatedSpotifyClient()
    client.search_track({"primary_artist": "A", "title": "B"})
    client.get_playlist_uris("pl")
    assert len(client.operations) == 2
    assert client.operations[0]["type"] == "search"
    assert client.operations[1]["type"] == "get_playlist"


def test_simulator_error_scenario_timeout():
    fixture = {"error_scenarios": {"Bad|Track": "timeout"}}
    client = SimulatedSpotifyClient(fixture_data=fixture)
    with pytest.raises(RuntimeError, match="Simulated timeout"):
        client.search_track({"primary_artist": "Bad", "title": "Track"})


def test_simulator_error_scenario_empty():
    fixture = {
        "search_responses": {"A|B": [{"spotify_id": "x", "name": "B", "artist": "A",
                                       "album": "C", "confidence": "exact", "uri": "u:x"}]},
        "error_scenarios": {"A|B": "empty"}
    }
    client = SimulatedSpotifyClient(fixture_data=fixture)
    # Error scenario overrides search_responses
    assert client.search_track({"primary_artist": "A", "title": "B"}) == []


def test_simulator_find_duplicates():
    client = SimulatedSpotifyClient(fixture_data={
        "initial_playlist": ["spotify:track:a", "spotify:track:b", "spotify:track:a"]
    })
    dupes = client.find_duplicates("pl")
    assert dupes == {"spotify:track:a": 1}


def test_simulator_current_user():
    client = SimulatedSpotifyClient()
    user = client.current_user()
    assert user["id"] == "testuser123"


def test_simulator_error_scenario_rate_limit():
    fixture = {"error_scenarios": {"Busy|Track": "rate_limit"}}
    client = SimulatedSpotifyClient(fixture_data=fixture)
    with pytest.raises(RuntimeError, match="Simulated rate limit"):
        client.search_track({"primary_artist": "Busy", "title": "Track"})


def test_simulator_add_count_property():
    client = SimulatedSpotifyClient()
    assert client.add_count == 0
    client.add_tracks("pl", ["spotify:track:x"])
    client.add_tracks("pl", ["spotify:track:y"])
    assert client.add_count == 2


def test_simulator_remove_count_property():
    client = SimulatedSpotifyClient(fixture_data={
        "initial_playlist": ["spotify:track:a", "spotify:track:b"]
    })
    assert client.remove_count == 0
    client.remove_tracks("pl", ["spotify:track:a"])
    assert client.remove_count == 1


def test_simulator_get_liked_track_uris():
    client = SimulatedSpotifyClient(fixture_data={"initial_liked": ["spotify:track:a", "spotify:track:b"]})
    assert client.get_liked_track_uris() == {"spotify:track:a", "spotify:track:b"}


def test_simulator_remove_liked_tracks():
    client = SimulatedSpotifyClient(fixture_data={"initial_liked": ["spotify:track:a", "spotify:track:b"]})
    result = client.remove_liked_tracks(["spotify:track:a"])
    assert result.removed_count == 1
    assert client.get_liked_track_uris() == {"spotify:track:b"}


def test_simulator_remove_liked_tracks_empty():
    client = SimulatedSpotifyClient()
    result = client.remove_liked_tracks([])
    assert result.removed_count == 0


def test_simulator_get_or_create_playlist_creates_new():
    client = SimulatedSpotifyClient()
    playlist_id = client.get_or_create_playlist("AudioManager Inbox")
    assert playlist_id
    assert client.operations[-1]["created"] is True


def test_simulator_get_or_create_playlist_reuses_existing():
    client = SimulatedSpotifyClient(fixture_data={"initial_playlists": {"AudioManager Inbox": "pl_existing"}})
    playlist_id = client.get_or_create_playlist("AudioManager Inbox")
    assert playlist_id == "pl_existing"
    assert client.operations[-1]["created"] is False


# ── RealSpotifyClient (mocked spotipy) ──────────────────────────────────────
# These test the class methods with a mocked spotipy.Spotify instance.

def _mock_real_client():
    """Create a RealSpotifyClient with mocked internals."""
    with patch.object(RealSpotifyClient, '__init__', lambda self, config: None):
        client = RealSpotifyClient.__new__(RealSpotifyClient)
        client._sp = MagicMock()
        return client


def test_real_client_search_returns_scored():
    client = _mock_real_client()
    track = {"primary_artist": "Eminem", "title": "Lose Yourself", "album": "8 Mile"}
    client._sp.search.return_value = search_response([
        sp_track("Lose Yourself", "Eminem", "8 Mile", uri="spotify:track:xyz")
    ])

    results = client.search_track(track)
    assert len(results) == 1
    assert results[0]["uri"] == "spotify:track:xyz"


def test_real_client_search_fallback():
    client = _mock_real_client()
    track = {"primary_artist": "Eminem", "title": "Lose Yourself", "album": "8 Mile"}
    client._sp.search.side_effect = [
        search_response([]),
        search_response([sp_track("Lose Yourself", "Eminem", "8 Mile")]),
    ]

    results = client.search_track(track)
    assert len(results) == 1
    assert client._sp.search.call_count == 2


def test_real_client_get_playlist_uris_new_format():
    client = _mock_real_client()
    client._sp.playlist.return_value = {"items": playlist_page(["id1", "id2"])}

    uris = client.get_playlist_uris("playlist123")
    assert uris == {"spotify:track:id1", "spotify:track:id2"}


def test_real_client_get_playlist_uris_pagination():
    client = _mock_real_client()
    client._sp.playlist.return_value = {"items": playlist_page(["id1"], next_url="http://next")}
    client._sp.next.return_value = playlist_page(["id2"])

    uris = client.get_playlist_uris("playlist123")
    assert uris == {"spotify:track:id1", "spotify:track:id2"}


def test_real_client_get_playlist_uris_old_format():
    client = _mock_real_client()
    client._sp.playlist.return_value = {"items": playlist_page_old_format(["id1"])}

    uris = client.get_playlist_uris("playlist123")
    assert uris == {"spotify:track:id1"}


def test_real_client_add_tracks_batches():
    client = _mock_real_client()
    client._sp._get_id.return_value = "pl123"
    uris = [f"spotify:track:{i}" for i in range(250)]

    result = client.add_tracks("pl123", uris)

    assert len(result.succeeded) == 250
    assert client._sp._post.call_count == 3


def test_real_client_add_tracks_empty():
    client = _mock_real_client()
    result = client.add_tracks("pl123", [])
    assert result.succeeded == []
    assert result.failed == []


def test_real_client_add_uses_items_endpoint():
    client = _mock_real_client()
    client._sp._get_id.return_value = "pl123"

    client.add_tracks("pl123", ["spotify:track:a"])

    call_url = client._sp._post.call_args[0][0]
    assert call_url.endswith("/items")


def test_real_client_remove_tracks():
    client = _mock_real_client()
    client._sp._get_id.return_value = "pl123"

    result = client.remove_tracks("pl123", ["spotify:track:a", "spotify:track:b"])

    assert result.removed_count == 2
    client._sp._delete.assert_called_once()


def test_real_client_get_liked_track_uris():
    client = _mock_real_client()
    client._sp.current_user_saved_tracks.return_value = {
        "items": [{"track": {"uri": "spotify:track:a"}}, {"track": {"uri": "spotify:track:b"}}],
        "next": None,
    }

    uris = client.get_liked_track_uris()
    assert uris == {"spotify:track:a", "spotify:track:b"}


def test_real_client_get_liked_track_uris_pagination():
    client = _mock_real_client()
    client._sp.current_user_saved_tracks.side_effect = [
        {"items": [{"track": {"uri": "spotify:track:a"}}], "next": "http://next"},
        {"items": [{"track": {"uri": "spotify:track:b"}}], "next": None},
    ]

    uris = client.get_liked_track_uris()
    assert uris == {"spotify:track:a", "spotify:track:b"}
    assert client._sp.current_user_saved_tracks.call_count == 2


def test_real_client_remove_liked_tracks():
    client = _mock_real_client()
    result = client.remove_liked_tracks(["spotify:track:a", "spotify:track:b"])
    assert result.removed_count == 2
    client._sp.current_user_saved_tracks_delete.assert_called_once_with(tracks=["spotify:track:a", "spotify:track:b"])


def test_real_client_remove_liked_tracks_empty():
    client = _mock_real_client()
    result = client.remove_liked_tracks([])
    assert result.removed_count == 0
    client._sp.current_user_saved_tracks_delete.assert_not_called()


def test_real_client_get_or_create_playlist_reuses_existing():
    client = _mock_real_client()
    client._sp.current_user_playlists.return_value = {
        "items": [{"name": "AudioManager Inbox", "id": "pl_existing"}], "next": None,
    }

    playlist_id = client.get_or_create_playlist("AudioManager Inbox")
    assert playlist_id == "pl_existing"
    client._sp.user_playlist_create.assert_not_called()


def test_real_client_get_or_create_playlist_creates_new():
    client = _mock_real_client()
    client._sp.current_user_playlists.return_value = {"items": [], "next": None}
    client._sp.current_user.return_value = {"id": "user1"}
    client._sp.user_playlist_create.return_value = {"id": "pl_new"}

    playlist_id = client.get_or_create_playlist("AudioManager Inbox")
    assert playlist_id == "pl_new"
    client._sp.user_playlist_create.assert_called_once_with("user1", "AudioManager Inbox", public=False)


# ── detailed track reads (playlist + Liked Songs) ───────────────────────────
# Both return the same row shape, because AudioManager's Acquire tab feeds
# either source into the same table. The shared shape is asserted here so the
# two can never drift apart.

DETAIL_KEYS = {"artist", "title", "album", "year", "duration_ms"}


def detailed_track(name="Song", artists=("Artist",), album="Album",
                   release_date="1999-02-23", duration_ms=210000, track_id="t1"):
    return {
        "id": track_id,
        "name": name,
        "artists": [{"name": a} for a in artists],
        "album": {"name": album, "release_date": release_date},
        "duration_ms": duration_ms,
    }


def saved_page(tracks, next_url=None):
    """Shape of GET /me/tracks: items are {"added_at":..., "track": {...}}."""
    return {"items": [{"track": t} for t in tracks], "next": next_url}


def test_get_playlist_tracks_detailed_shape():
    client = _mock_real_client()
    client._sp.playlist.return_value = {
        "items": {"items": [{"item": detailed_track()}], "next": None}
    }

    rows = client.get_playlist_tracks_detailed("pl1")
    assert len(rows) == 1
    assert set(rows[0]) == DETAIL_KEYS
    assert rows[0]["year"] == "1999"
    assert rows[0]["duration_ms"] == 210000


def test_get_liked_tracks_detailed_shape_matches_playlist_rows():
    """Liked Songs rows must be interchangeable with playlist rows."""
    client = _mock_real_client()
    client._sp.current_user_saved_tracks.return_value = saved_page([detailed_track()])

    rows = client.get_liked_tracks_detailed()
    assert len(rows) == 1
    assert set(rows[0]) == DETAIL_KEYS
    assert rows[0] == {
        "artist": "Artist", "title": "Song", "album": "Album",
        "year": "1999", "duration_ms": 210000,
    }


def test_get_liked_tracks_detailed_joins_multiple_artists():
    client = _mock_real_client()
    client._sp.current_user_saved_tracks.return_value = saved_page(
        [detailed_track(artists=("KYLE", "Joshua Golden"))]
    )

    rows = client.get_liked_tracks_detailed()
    assert rows[0]["artist"] == "KYLE & Joshua Golden"


def test_get_liked_tracks_detailed_paginates():
    client = _mock_real_client()
    client._sp.current_user_saved_tracks.side_effect = [
        saved_page([detailed_track(name="A", track_id="a")], next_url="http://next"),
        saved_page([detailed_track(name="B", track_id="b")]),
    ]

    rows = client.get_liked_tracks_detailed()
    assert [r["title"] for r in rows] == ["A", "B"]
    assert client._sp.current_user_saved_tracks.call_count == 2


def test_get_liked_tracks_detailed_preserves_order():
    """Spotify returns Liked Songs most-recently-added first; keep that order."""
    client = _mock_real_client()
    client._sp.current_user_saved_tracks.return_value = saved_page([
        detailed_track(name="newest", track_id="1"),
        detailed_track(name="older", track_id="2"),
        detailed_track(name="oldest", track_id="3"),
    ])

    rows = client.get_liked_tracks_detailed()
    assert [r["title"] for r in rows] == ["newest", "older", "oldest"]


def test_get_liked_tracks_detailed_skips_malformed_items():
    """Defensive: null items, null tracks and id-less tracks are dropped."""
    client = _mock_real_client()
    client._sp.current_user_saved_tracks.return_value = {
        "items": [
            None,
            {"track": None},
            {"track": {"name": "no id", "artists": []}},
            {"track": detailed_track(name="good", track_id="ok")},
        ],
        "next": None,
    }

    rows = client.get_liked_tracks_detailed()
    assert [r["title"] for r in rows] == ["good"]


def test_get_liked_tracks_detailed_missing_fields_do_not_raise():
    client = _mock_real_client()
    client._sp.current_user_saved_tracks.return_value = {
        "items": [{"track": {"id": "x", "artists": []}}],
        "next": None,
    }

    rows = client.get_liked_tracks_detailed()
    assert rows == [{"artist": "Unknown", "title": "Unknown", "album": "",
                     "year": "", "duration_ms": 0}]


def test_get_liked_tracks_detailed_limit_caps_and_stops_paging():
    """limit=2 must return 2 rows and not request a second page."""
    client = _mock_real_client()
    client._sp.current_user_saved_tracks.side_effect = [
        saved_page([detailed_track(name=n, track_id=n) for n in ("a", "b", "c")],
                   next_url="http://next"),
        saved_page([detailed_track(name="d", track_id="d")]),
    ]

    rows = client.get_liked_tracks_detailed(limit=2)
    assert [r["title"] for r in rows] == ["a", "b"]
    assert client._sp.current_user_saved_tracks.call_count == 1


def test_get_liked_tracks_detailed_empty_library():
    client = _mock_real_client()
    client._sp.current_user_saved_tracks.return_value = {"items": [], "next": None}
    assert client.get_liked_tracks_detailed() == []
