import pytest
from src.matcher import score_match, clean_title


def test_clean_title_removes_feat():
    assert clean_title("Song feat. Artist") == "Song"

def test_clean_title_removes_ft():
    assert clean_title("Song ft. Artist") == "Song"

def test_clean_title_removes_feat_parens():
    assert clean_title("Song (feat. Artist)") == "Song"

def test_clean_title_no_change():
    assert clean_title("Lose Yourself") == "Lose Yourself"

def test_score_match_exact():
    track = {"primary_artist": "Eminem", "title": "Lose Yourself", "album": "8 Mile"}
    result = {"artists": [{"name": "Eminem"}], "name": "Lose Yourself", "album": {"name": "8 Mile"}}
    assert score_match(track, result) == "exact"

def test_score_match_exact_case_insensitive():
    track = {"primary_artist": "eminem", "title": "lose yourself", "album": "8 mile"}
    result = {"artists": [{"name": "Eminem"}], "name": "Lose Yourself", "album": {"name": "8 Mile"}}
    assert score_match(track, result) == "exact"

def test_score_match_high_different_album():
    track = {"primary_artist": "Eminem", "title": "Lose Yourself", "album": "Something Else"}
    result = {"artists": [{"name": "Eminem"}], "name": "Lose Yourself", "album": {"name": "8 Mile"}}
    assert score_match(track, result) == "high"

def test_score_match_low_partial():
    track = {"primary_artist": "Eminem", "title": "Lose Yourself", "album": ""}
    result = {"artists": [{"name": "Eminem"}], "name": "Lose Yourself Remix", "album": {"name": ""}}
    assert score_match(track, result) in ("high", "low")

def test_score_match_none():
    track = {"primary_artist": "Eminem", "title": "Lose Yourself", "album": ""}
    result = {"artists": [{"name": "Completely Different"}], "name": "Unrelated Song", "album": {"name": ""}}
    assert score_match(track, result) == "none"
