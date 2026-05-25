"""Tests for src/open_playlist._open_interactively."""

from unittest.mock import patch

from src.open_playlist import _open_interactively

TRACKS = [
    ("Eminem", "My Name Is"),
    ("JAY-Z", "Encore"),
    ("Mura Masa", "bbycakes"),
]


def test_opens_all_tracks_with_enter(capsys):
    pass


def test_quit_mid_way(capsys):
    pass


def test_ctrl_c_stops_gracefully(capsys):
    pass


def test_empty_list_prints_message(capsys):
    pass


def test_single_track_no_next_prompt():
    pass
