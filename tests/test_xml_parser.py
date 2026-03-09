import pytest
from src.xml_parser import parse_track, parse_library
import xml.etree.ElementTree as ET
import os


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
