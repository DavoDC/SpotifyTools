"""Tests for src/acquire.py (Stage 2A: Liked Songs -> inbox playlist)."""

from spotify_tools.acquire import move_liked_to_playlist, INBOX_PLAYLIST_NAME
from spotify_tools.spotify_simulator import SimulatedSpotifyClient


def test_moves_all_liked_tracks_to_new_playlist():
    client = SimulatedSpotifyClient(fixture_data={
        "initial_liked": ["spotify:track:a", "spotify:track:b"],
    })

    result = move_liked_to_playlist(client)

    assert result.moved_count == 2
    assert result.errors == []
    assert set(client.playlist_contents) == {"spotify:track:a", "spotify:track:b"}
    assert client.get_liked_track_uris() == set()


def test_reuses_existing_inbox_playlist():
    client = SimulatedSpotifyClient(fixture_data={
        "initial_liked": ["spotify:track:a"],
        "initial_playlists": {INBOX_PLAYLIST_NAME: "pl_existing"},
    })

    result = move_liked_to_playlist(client)

    assert result.playlist_id == "pl_existing"
    assert result.moved_count == 1


def test_empty_liked_songs_is_a_no_op():
    client = SimulatedSpotifyClient()

    result = move_liked_to_playlist(client)

    assert result.moved_count == 0
    assert result.errors == []
    assert result.playlist_id  # playlist still created/reused so the GUI has somewhere to point


def test_custom_playlist_name():
    client = SimulatedSpotifyClient(fixture_data={"initial_liked": ["spotify:track:a"]})

    result = move_liked_to_playlist(client, playlist_name="Custom Inbox")

    assert result.playlist_name == "Custom Inbox"
    assert client.get_or_create_playlist("Custom Inbox") == result.playlist_id
