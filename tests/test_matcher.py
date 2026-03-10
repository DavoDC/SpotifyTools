import pytest
from src.matcher import score_match, clean_title, normalise


def test_clean_title_removes_feat():
    assert clean_title("Song feat. Artist") == "Song"

def test_clean_title_removes_ft():
    assert clean_title("Song ft. Artist") == "Song"

def test_clean_title_removes_feat_parens():
    assert clean_title("Song (feat. Artist)") == "Song"

def test_clean_title_no_change():
    assert clean_title("Lose Yourself") == "Lose Yourself"

def test_clean_title_removes_feat_square_brackets():
    assert clean_title("Song [feat. Artist]") == "Song"

def test_clean_title_removes_feat_no_dot():
    assert clean_title("Song feat Artist") == "Song"

def test_clean_title_only_feat_content():
    # Edge case: title IS just "feat. X" — should return empty string, not crash
    result = clean_title("feat. Someone")
    assert isinstance(result, str)


# ── normalise ─────────────────────────────────────────────────────────────────

def test_normalise_lowercases():
    assert normalise("Eminem") == "eminem"

def test_normalise_strips_the():
    assert normalise("The Eminem Show") == "eminem show"

def test_normalise_strips_a():
    assert normalise("A Kind of Magic") == "kind of magic"

def test_normalise_strips_an():
    assert normalise("An Album") == "album"

def test_normalise_removes_punctuation():
    assert normalise("don't") == "dont"

def test_normalise_collapses_whitespace():
    assert normalise("  too   many   spaces  ") == "too many spaces"

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

def test_score_match_high_via_normalise():
    # "The Eminem" vs "Eminem" — normalise strips "the", should still match
    track = {"primary_artist": "The Eminem", "title": "Lose Yourself", "album": ""}
    result = {"artists": [{"name": "Eminem"}], "name": "Lose Yourself", "album": {"name": ""}}
    assert score_match(track, result) in ("high", "exact")

def test_score_match_empty_artists_does_not_crash():
    # Spotify can return tracks with empty artists list
    track = {"primary_artist": "Eminem", "title": "Lose Yourself", "album": ""}
    result = {"artists": [], "name": "Lose Yourself", "album": {"name": ""}}
    score = score_match(track, result)
    assert score in ("exact", "high", "low", "none")

def test_score_match_missing_album_does_not_crash():
    track = {"primary_artist": "Eminem", "title": "Lose Yourself", "album": "8 Mile"}
    result = {"artists": [{"name": "Eminem"}], "name": "Lose Yourself", "album": {}}
    score = score_match(track, result)
    assert score in ("exact", "high", "low", "none")
