"""Tests for src/open_playlist._open_interactively and _clean_for_search."""

from unittest.mock import patch

from src.open_playlist import _open_interactively, _clean_for_search

TRACKS = [
    ("Eminem", "My Name Is"),
    ("JAY-Z", "Encore"),
    ("Mura Masa", "bbycakes"),
]


def test_opens_all_tracks_with_enter(capsys):
    """All Enter presses: all three tracks opened."""
    # start prompt + 2 inter-track prompts (no prompt after last track)
    with patch("builtins.input", side_effect=["", "", ""]), \
         patch("src.open_playlist._open_in_manager") as mock_open:
        _open_interactively(TRACKS)
    assert mock_open.call_count == 3
    mock_open.assert_any_call("Eminem", "My Name Is")
    mock_open.assert_any_call("JAY-Z", "Encore")
    mock_open.assert_any_call("Mura Masa", "bbycakes")
    out = capsys.readouterr().out
    assert "All 3 tracks opened" in out


def test_quit_mid_way(capsys):
    """'q' after second track: only 2 tracks opened."""
    # start prompt -> '' after track 1 -> 'q' after track 2
    with patch("builtins.input", side_effect=["", "", "q"]), \
         patch("src.open_playlist._open_in_manager") as mock_open:
        _open_interactively(TRACKS)
    assert mock_open.call_count == 2
    out = capsys.readouterr().out
    assert "Stopped" in out


def test_ctrl_c_stops_gracefully(capsys):
    """KeyboardInterrupt after first open: stops cleanly after 1 track."""
    with patch("builtins.input", side_effect=["", KeyboardInterrupt]), \
         patch("src.open_playlist._open_in_manager") as mock_open:
        _open_interactively(TRACKS)
    assert mock_open.call_count == 1
    out = capsys.readouterr().out
    assert "Stopped" in out


def test_empty_list_prints_message(capsys):
    """Empty track list: no opens, prints informative message."""
    with patch("src.open_playlist._open_in_manager") as mock_open:
        _open_interactively([])
    assert mock_open.call_count == 0
    out = capsys.readouterr().out
    assert "No tracks" in out


def test_single_track_no_next_prompt():
    """Single track: only the start prompt fires, no inter-track prompt."""
    with patch("builtins.input", side_effect=[""]) as mock_input, \
         patch("src.open_playlist._open_in_manager") as mock_open:
        _open_interactively([("Eminem", "My Name Is")])
    assert mock_open.call_count == 1
    assert mock_input.call_count == 1  # only the "Ready to start" prompt


# ── _clean_for_search ────────────────────────────────────────────────────────

def test_clean_for_search_strips_ampersand():
    assert _clean_for_search("TJ Hickey & Nate Good") == "TJ Hickey Nate Good"


def test_clean_for_search_strips_hyphen():
    assert _clean_for_search("Ne-Yo") == "Ne Yo"


def test_clean_for_search_strips_period():
    assert _clean_for_search("Ms. Tundra") == "Ms Tundra"


def test_clean_for_search_collapses_whitespace():
    assert _clean_for_search("a  &  b") == "a b"


def test_open_in_manager_url_has_no_percent_encoded_symbols():
    """URL built for artist with & must not contain %26 or other %XX symbols."""
    captured = []
    with patch("src.open_playlist.webbrowser.open", side_effect=lambda u: captured.append(u)):
        from src.open_playlist import _open_in_manager
        _open_in_manager("TJ Hickey & Nate Good", "sea side nights")
    url = captured[0]
    assert "%26" not in url
    assert "%27" not in url
    assert "TJ" in url and "Hickey" in url and "Nate" in url
