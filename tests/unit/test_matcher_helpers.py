"""Pure artist and title key helpers in spotify_tools.matcher.

Expected values are derived by hand from the reference matching code, step by step:
clean_artist, then mark removal, then the first-artist split; title rewrite, clean_title,
edit-word suffix strip, then normalise.
"""

import os

import pytest

import spotify_tools
from spotify_tools import PUBLIC_API, matcher
from spotify_tools.matcher import content_key, normalise, primary_artist, title_key

REPO_ROOT = os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
NEW_HELPERS = ("primary_artist", "title_key", "content_key")

PRIMARY_CASES = [
    ("Drake feat. Rihanna", "Drake"),
    ("Drake ft. Rihanna", "Drake"),
    ("Simon & Garfunkel", "Simon"),
    ("Earth, Wind & Fire", "Earth"),
    ("AC/DC;Foo", "AC/DC"),
    ("Artist A ; Artist B", "Artist A"),
    ("Tyler, The Creator", "Tyler"),
    ("BNYX(R)", "BNYX"),
    ("BNYX®", "BNYX"),
    ("Taylor Swift™", "Taylor Swift"),
    ("Band(C)", "Band"),
    ("Drake (R) feat. Future", "Drake"),
    ("Simon & Garfunkel feat. Someone", "Simon"),
    ("Beyoncé & JAY-Z", "Beyoncé"),
    ("  Drake  ", "Drake"),
    ("", ""),
]

TITLE_CASES = [
    ("Hey Jude", "hey jude"),
    ("Hey Jude - Single Version", "hey jude"),
    ("Hey Jude (Single Version)", "hey jude"),
    ("Song (feat. Rihanna)", "song"),
    ("Song - feat. Rihanna", "song"),
    ("Song (Edited)", "song edited"),
    ("Song - Edited", "song edited"),
    ("Song (Remastered 2009)", "song"),
    ("Song - Remastered 2009", "song"),
    ("Song - Explicit", "song"),
    ("Song (Explicit Version)", "song"),
    ("Song (Radio Edit)", "song"),
    ("Song [Clean]", "song"),
    ("Song (Deluxe Edition)", "song"),
    ("Song - Bonus Track", "song"),
    ("Song (with Drake)", "song"),
    ("The Way", "way"),
    ("Café Noir", "cafe noir"),
    ("Don't Stop Me Now", "dont stop me now"),
    ("", ""),
]

CONTENT_CASES = [
    ("Drake feat. Rihanna", "Hey Jude - Single Version", "drake:hey jude single version"),
    ("Simon & Garfunkel", "The Sound of Silence", "simon:sound of silence"),
    ("BNYX(R)", "Song (Edited)", "bnyxr:song edited"),
    ("Earth, Wind & Fire", "September", "earth:september"),
    ("The Beatles", "Hey Jude", "beatles:hey jude"),
    ("Beyoncé & JAY-Z", "Déjà Vu", "beyonce:deja vu"),
    ("Drake (R)", "Don't Stop - Remastered 2009", "drake r:dont stop remastered 2009"),
    ("Tyler, The Creator", "Song (feat. X)", "tyler:song"),
    ("", "", ":"),
]


@pytest.mark.parametrize("artist, expected", PRIMARY_CASES)
def test_primary_artist(artist, expected):
    assert primary_artist(artist) == expected


@pytest.mark.parametrize("title, expected", TITLE_CASES)
def test_title_key(title, expected):
    assert title_key(title) == expected


@pytest.mark.parametrize("artist, title, expected", CONTENT_CASES)
def test_content_key(artist, title, expected):
    assert content_key(artist, title) == expected


def test_content_key_is_stable_persistence_key():
    # Stored keys must not change: no dash-suffix rewrite and no mark stripping in content_key.
    assert content_key("Simon & Garfunkel", "Hey Jude - Single Version") == "simon:hey jude single version"


def test_new_helpers_live_in_matcher():
    for name in NEW_HELPERS:
        assert callable(getattr(matcher, name))


def test_public_api_lists_new_helpers_and_existing_names():
    for name in NEW_HELPERS + ("clean_title", "clean_artist", "normalise", "build_client",
                               "API_VERSION", "build_search_url"):
        assert name in PUBLIC_API, name


def test_public_api_names_resolve():
    from spotify_tools import config, open_playlist
    modules = (spotify_tools, matcher, config, open_playlist)
    for name in PUBLIC_API:
        assert any(hasattr(mod, name) for mod in modules), name


@pytest.mark.parametrize("doc", ["README.md", "CLAUDE.md"])
def test_new_helpers_documented(doc):
    with open(os.path.join(REPO_ROOT, doc), encoding="utf-8") as fh:
        text = fh.read()
    for name in NEW_HELPERS:
        assert name in text, f"{name} missing from {doc}"
