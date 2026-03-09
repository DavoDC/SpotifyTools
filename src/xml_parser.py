import xml.etree.ElementTree as ET
import os
from typing import Optional


def parse_track(root: ET.Element) -> dict:
    def get(tag) -> Optional[str]:
        el = root.find(tag)
        return el.text.strip() if el is not None and el.text else None

    artists_raw = get("Artists") or ""
    all_artists = [a.strip() for a in artists_raw.split(";") if a.strip()]
    primary_artist = all_artists[0] if all_artists else ""

    return {
        "title": get("Title") or "",
        "primary_artist": primary_artist,
        "all_artists": all_artists,
        "album": get("Album") or "",
        "year": get("Year"),
    }


def parse_library(path: str) -> list[dict]:
    tracks = []
    for root_dir, _, files in os.walk(path):
        for filename in files:
            if not filename.endswith(".xml"):
                continue
            filepath = os.path.join(root_dir, filename)
            try:
                tree = ET.parse(filepath)
                track = parse_track(tree.getroot())
                track["source_file"] = filename
                tracks.append(track)
            except ET.ParseError as e:
                print(f"  [WARN] Failed to parse {filename}: {e}")
    return tracks
