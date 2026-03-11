"""Tests for src/report_generator.py — markdown report generation."""

import os
import tempfile

from src.report_generator import generate_report


def _v2_history(added=2, unmatched=1, exhausted=0, custom=1):
    tracks = {}
    for i in range(added):
        tracks[f"Artist{i}|Track{i}"] = {
            "state": "added", "display": f"Artist{i} — Track{i}",
            "spotify_uri": f"spotify:track:id{i}", "spotify_id": f"id{i}",
            "match_confidence": "exact", "search_attempts": 1,
            "first_seen": "2026-01-01T00:00:00", "last_updated": "2026-01-01T00:00:00",
            "source_file": None,
        }
    for i in range(unmatched):
        tracks[f"Unknown{i}|Ghost{i}"] = {
            "state": "unmatched", "display": f"Unknown{i} — Ghost{i}",
            "spotify_uri": None, "spotify_id": None,
            "match_confidence": None, "search_attempts": 2,
            "first_seen": "2026-01-01T00:00:00", "last_updated": "2026-01-01T00:00:00",
            "source_file": None,
        }
    for i in range(exhausted):
        tracks[f"Exhaust{i}|Gone{i}"] = {
            "state": "exhausted", "display": f"Exhaust{i} — Gone{i}",
            "spotify_uri": None, "spotify_id": None,
            "match_confidence": None, "search_attempts": 5,
            "first_seen": "2026-01-01T00:00:00", "last_updated": "2026-01-01T00:00:00",
            "source_file": None,
        }
    for i in range(custom):
        tracks[f"Custom{i}|Rare{i}"] = {
            "state": "custom", "display": f"Custom{i} — Rare{i}",
            "spotify_uri": None, "spotify_id": None,
            "match_confidence": None, "search_attempts": 0,
            "first_seen": "2026-01-01T00:00:00", "last_updated": "2026-01-01T00:00:00",
            "source_file": None,
        }
    return {"version": 2, "tracks": tracks}


def test_report_creates_file():
    with tempfile.TemporaryDirectory() as d:
        path = generate_report(d, _v2_history(), [], [], [], total_tracks=4)
        assert os.path.exists(path)
        assert path.endswith(".md")


def test_report_contains_stats_table():
    with tempfile.TemporaryDirectory() as d:
        path = generate_report(d, _v2_history(added=3, unmatched=2), [], [], [], total_tracks=6)
        content = open(path, encoding="utf-8").read()
        assert "| 3 |" in content
        assert "| 2 |" in content


def test_report_contains_unmatched_tracks():
    with tempfile.TemporaryDirectory() as d:
        path = generate_report(d, _v2_history(unmatched=1), [], [], [], total_tracks=3)
        content = open(path, encoding="utf-8").read()
        assert "Unknown0" in content


def test_report_no_unmatched_shows_none_message():
    with tempfile.TemporaryDirectory() as d:
        path = generate_report(d, _v2_history(unmatched=0), [], [], [], total_tracks=3)
        content = open(path, encoding="utf-8").read()
        assert "all tracks matched" in content.lower() or "_None" in content


def test_report_contains_low_confidence():
    low = [{"track": "Me - Song", "matched": "Them - Other (Album)", "confidence": "low"}]
    with tempfile.TemporaryDirectory() as d:
        path = generate_report(d, _v2_history(), low, [], [], total_tracks=4)
        content = open(path, encoding="utf-8").read()
        assert "Me - Song" in content
        assert "Them - Other" in content


def test_report_contains_recovered_tracks():
    recovered = [{"key": "A|B", "uri": "spotify:track:x", "display": "A — B"}]
    with tempfile.TemporaryDirectory() as d:
        path = generate_report(d, _v2_history(), [], recovered, [], total_tracks=4)
        content = open(path, encoding="utf-8").read()
        assert "Recovered" in content
        assert "A — B" in content


def test_report_contains_removed_uris():
    removed = ["spotify:track:orphan1", "spotify:track:orphan2"]
    with tempfile.TemporaryDirectory() as d:
        path = generate_report(d, _v2_history(), [], [], removed, total_tracks=4)
        content = open(path, encoding="utf-8").read()
        assert "Removed" in content
        assert "orphan1" in content


def test_report_contains_exhausted_tracks():
    with tempfile.TemporaryDirectory() as d:
        path = generate_report(d, _v2_history(exhausted=2), [], [], [], total_tracks=4)
        content = open(path, encoding="utf-8").read()
        assert "Exhausted" in content
        assert "Exhaust0" in content


def test_report_no_recovered_no_removed_no_section():
    with tempfile.TemporaryDirectory() as d:
        path = generate_report(d, _v2_history(), [], [], [], total_tracks=4)
        content = open(path, encoding="utf-8").read()
        assert "Recovered" not in content
        assert "Removed" not in content
