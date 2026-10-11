"""Public API surface consumed by the consumer."""

from unittest.mock import patch

from spotify_tools import API_VERSION, build_client
from spotify_tools.config import CONFIG_PATH, load_config
from spotify_tools.matcher import clean_artist, clean_title, normalise
from spotify_tools.open_playlist import (
    _build_search_url,
    build_search_url,
    extract_playlist_id,
)
from spotify_tools.acquire import move_liked_to_playlist
from spotify_tools.spotify_client import RealSpotifyClient


def test_api_version_is_int():
    assert isinstance(API_VERSION, int) and API_VERSION >= 1


def test_alias_is_same_object():
    assert build_search_url is _build_search_url


def test_public_names_importable():
    for obj in (CONFIG_PATH, load_config, clean_artist, clean_title,
                normalise, extract_playlist_id, move_liked_to_playlist,
                RealSpotifyClient):
        assert obj is not None


def test_build_client_with_explicit_config():
    cfg = {"k": "v"}
    with patch("spotify_tools.spotify_client.RealSpotifyClient") as cls:
        assert build_client(cfg) is cls.return_value
        cls.assert_called_once_with(cfg)


def test_build_client_default_loads_config():
    with patch("spotify_tools.config.load_config", return_value={"a": 1}) as lc, \
         patch("spotify_tools.spotify_client.RealSpotifyClient") as cls:
        build_client()
        lc.assert_called_once_with()
        cls.assert_called_once_with({"a": 1})
