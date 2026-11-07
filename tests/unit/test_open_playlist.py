"""Tests for src/spotify_tools/open_playlist.py: playlist helpers only."""

from spotify_tools import open_playlist
from spotify_tools.open_playlist import (
    build_search_url,
    extract_playlist_id,
    format_track_lines,
)


def test_format_track_lines_sorts_by_primary_artist_then_title():
    tracks = [
        ("Zara Larsson", "Last"),
        ("Akon", "Zeta"),
        ("Akon", "Alpha"),
        ("KYLE & Joshua Golden", "But Cha"),
    ]
    assert format_track_lines(tracks) == [
        "Akon - Alpha",
        "Akon - Zeta",
        "KYLE & Joshua Golden - But Cha",
        "Zara Larsson - Last",
    ]


def test_format_track_lines_empty_list():
    assert format_track_lines([]) == []


def test_format_track_lines_does_not_mutate_input():
    tracks = [("Zara Larsson", "Last"), ("Akon", "First")]
    format_track_lines(tracks)
    assert tracks == [("Zara Larsson", "Last"), ("Akon", "First")]


def test_no_external_opening_code_remains():
    leftovers = [n for n in dir(open_playlist)
                 if "open_in" in n.lower() or n == "webbrowser"]
    assert leftovers == []


def test_extract_playlist_id_from_url():
    url = "https://open.spotify.com/playlist/EXAMPLEPLAYLISTID0000?si=abc"
    assert extract_playlist_id(url) == "EXAMPLEPLAYLISTID0000"


def test_extract_playlist_id_raw_id_passthrough():
    assert extract_playlist_id("  EXAMPLEPLAYLISTID0000 ") == "EXAMPLEPLAYLISTID0000"


def test_build_search_url_escapes_slash_and_ampersand():
    url = build_search_url("AC/DC", "Rock & Roll")
    assert url == "https://open.spotify.com/search/AC%2FDC%20Rock%20%26%20Roll"


def test_build_search_url_is_public():
    from spotify_tools import PUBLIC_API
    assert "build_search_url" in PUBLIC_API
