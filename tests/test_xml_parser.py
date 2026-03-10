import pytest
from src.xml_parser import parse_track, parse_library
import xml.etree.ElementTree as ET
import os

FIXTURES_DIR = os.path.join(os.path.dirname(__file__), "fixtures", "AUDIO_MIRROR")


SAMPLE_XML = """<Track>
  <Title>bbycakes</Title>
  <Artists>Mura Masa;Lil Uzi Vert;PinkPantheress;Shygirl</Artists>
  <Album>bbycakes</Album>
  <Year>2022</Year>
  <TrackNumber>1</TrackNumber>
  <Genres>Electro</Genres>
  <Length>00:02:53.5290000</Length>
  <AlbumCoverCount>1</AlbumCoverCount>
  <Compilation>True</Compilation>
</Track>"""


def test_parse_track_title():
    root = ET.fromstring(SAMPLE_XML)
    track = parse_track(root)
    assert track["title"] == "bbycakes"

def test_parse_track_primary_artist():
    root = ET.fromstring(SAMPLE_XML)
    track = parse_track(root)
    assert track["primary_artist"] == "Mura Masa"

def test_parse_track_all_artists():
    root = ET.fromstring(SAMPLE_XML)
    track = parse_track(root)
    assert track["all_artists"] == ["Mura Masa", "Lil Uzi Vert", "PinkPantheress", "Shygirl"]

def test_parse_track_album():
    root = ET.fromstring(SAMPLE_XML)
    track = parse_track(root)
    assert track["album"] == "bbycakes"

def test_parse_track_year():
    root = ET.fromstring(SAMPLE_XML)
    track = parse_track(root)
    assert track["year"] == "2022"

def test_parse_track_single_artist():
    xml = "<Track><Title>Lose Yourself</Title><Artists>Eminem</Artists><Album>8 Mile</Album><Year>2002</Year></Track>"
    root = ET.fromstring(xml)
    track = parse_track(root)
    assert track["primary_artist"] == "Eminem"
    assert track["all_artists"] == ["Eminem"]

def test_parse_track_missing_year():
    xml = "<Track><Title>Test</Title><Artists>Artist</Artists><Album>Album</Album></Track>"
    root = ET.fromstring(xml)
    track = parse_track(root)
    assert track["year"] is None

def test_parse_track_missing_title_returns_empty_string():
    xml = "<Track><Artists>Artist</Artists><Album>Album</Album></Track>"
    root = ET.fromstring(xml)
    track = parse_track(root)
    assert track["title"] == ""

def test_parse_track_empty_artists_returns_empty():
    xml = "<Track><Title>Test</Title><Artists></Artists><Album>Album</Album></Track>"
    root = ET.fromstring(xml)
    track = parse_track(root)
    assert track["primary_artist"] == ""
    assert track["all_artists"] == []

def test_parse_track_missing_artists_returns_empty():
    xml = "<Track><Title>Test</Title><Album>Album</Album></Track>"
    root = ET.fromstring(xml)
    track = parse_track(root)
    assert track["primary_artist"] == ""
    assert track["all_artists"] == []


# ── parse_library() — tests against real fixture files on disk ────────────────

def test_parse_library_track_count():
    # 4 valid XML files + 1 broken = 4 tracks returned
    tracks = parse_library(FIXTURES_DIR)
    assert len(tracks) == 4

def test_parse_library_finds_nested_artist_track():
    tracks = parse_library(FIXTURES_DIR)
    titles = [t["title"] for t in tracks]
    assert "My Name Is" in titles

def test_parse_library_finds_compilation_track():
    tracks = parse_library(FIXTURES_DIR)
    titles = [t["title"] for t in tracks]
    assert "Some Song" in titles

def test_parse_library_finds_miscellaneous_track():
    tracks = parse_library(FIXTURES_DIR)
    titles = [t["title"] for t in tracks]
    assert "No Year Track" in titles

def test_parse_library_multi_artist_track():
    tracks = parse_library(FIXTURES_DIR)
    bbycakes = next(t for t in tracks if t["title"] == "bbycakes")
    assert bbycakes["primary_artist"] == "Mura Masa"
    assert len(bbycakes["all_artists"]) == 4

def test_parse_library_missing_year_is_none():
    tracks = parse_library(FIXTURES_DIR)
    no_year = next(t for t in tracks if t["title"] == "No Year Track")
    assert no_year["year"] is None

def test_parse_library_skips_broken_xml():
    # broken.xml must not crash the run — should just be skipped
    tracks = parse_library(FIXTURES_DIR)
    source_files = [t["source_file"] for t in tracks]
    assert "broken.xml" not in source_files

def test_parse_library_includes_source_file():
    tracks = parse_library(FIXTURES_DIR)
    assert all("source_file" in t for t in tracks)
