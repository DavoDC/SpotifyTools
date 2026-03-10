"""
Spotify auth diagnostic.
Interactive: python scripts/diagnose.py
Silent (background, log only): python scripts/diagnose.py --silent
"""
import json
import os
import sys
from datetime import datetime

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
from src.spotify import create_client

SILENT = "--silent" in sys.argv

BASE_DIR = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
CONFIG_PATH = os.path.join(BASE_DIR, "config", "config.json")
LOG_DIR = os.path.join(BASE_DIR, "data", "logs")
os.makedirs(LOG_DIR, exist_ok=True)
LOG_FILE = os.path.join(LOG_DIR, f"diagnose_{datetime.now().strftime('%Y%m%d_%H%M%S')}.log")


def out(msg):
    with open(LOG_FILE, "a", encoding="utf-8") as f:
        f.write(msg + "\n")
    if not SILENT:
        print(msg)


with open(CONFIG_PATH) as f:
    config = json.load(f)

sp = create_client(config)
playlist_id = config["spotify_playlist_id"]

out(f"\n=== Spotify Diagnostics ({datetime.now().strftime('%Y-%m-%d %H:%M:%S')}) ===\n")

# 1. Current user
user = sp.current_user()
out(f"[1] Authenticated as: {user['display_name']} ({user['id']})")

# 2. Is target playlist in user's playlists?
out(f"\n[2] Checking target playlist ({playlist_id})...")
playlists = sp.current_user_playlists(limit=50)
found = any(p["id"] == playlist_id for p in playlists["items"])
out(f"     Found in your playlists: {found}")

# 3. Playlist metadata
out(f"\n[3] Fetching playlist metadata...")
try:
    p = sp.playlist(playlist_id, fields="id,name,owner,public")
    out(f"     Name:   {p['name']}")
    out(f"     Owner:  {p['owner']['display_name']} ({p['owner']['id']})")
    out(f"     Public: {p['public']}")
except Exception as e:
    out(f"     ERROR: {e}")

# 4. Fetch tracks via sp.playlist() (main method used by app)
out(f"\n[4] Fetching tracks via sp.playlist()...")
try:
    tracks = sp.playlist(playlist_id)["tracks"]
    out(f"     OK - total: {tracks['total']}, first page: {len(tracks['items'])} items")
    for item in tracks["items"][:3]:
        t = item.get("track")
        if t:
            out(f"       - {t['artists'][0]['name']} - {t['name']}")
except Exception as e:
    out(f"     ERROR: {e}")

# 5. Test on a second owned playlist
OTHER_PLAYLIST = "321LEomVmFIYZR0GZgpz1z"  # Best Akira Musivation
out(f"\n[5] Fetching tracks from second playlist ({OTHER_PLAYLIST})...")
try:
    tracks2 = sp.playlist(OTHER_PLAYLIST)["tracks"]
    out(f"     OK - total: {tracks2['total']}, first page: {len(tracks2['items'])} items")
    for item in tracks2["items"][:3]:
        t = item.get("track")
        if t:
            out(f"       - {t['artists'][0]['name']} - {t['name']}")
except Exception as e:
    out(f"     ERROR: {e}")

out(f"\nLog saved to: {LOG_FILE}")

if not SILENT:
    input("\nPress Enter to exit...")
