"""
Spotify auth diagnostic. Runs on every launch via run.sh (silent mode).
Interactive: python scripts/diagnose.py
Silent (log only): python scripts/diagnose.py --silent
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


def out(msg=""):
    with open(LOG_FILE, "a", encoding="utf-8") as f:
        f.write(msg + "\n")
    if not SILENT:
        print(msg)


def check(label, fn):
    """Run fn(), log result. Returns value on success, None on failure."""
    try:
        result = fn()
        out(f"     OK: {result}")
        return result
    except Exception as e:
        out(f"     FAIL: {e}")
        return None


out(f"=== Spotify Diagnostics ({datetime.now().strftime('%Y-%m-%d %H:%M:%S')}) ===")

try:
    with open(CONFIG_PATH) as f:
        config = json.load(f)
except Exception as e:
    out(f"FATAL: Could not load config: {e}")
    sys.exit(1)

try:
    sp = create_client(config)
except Exception as e:
    out(f"FATAL: Could not create Spotify client: {e}")
    sys.exit(1)

playlist_id = config.get("spotify_playlist_id", "MISSING")

# 1. Auth
out("\n[1] Auth check")
user = check("current_user", lambda: sp.current_user()["display_name"] + " (" + sp.current_user()["id"] + ")")

# 2. Playlist owned by user?
out("\n[2] Playlist ownership")
def check_ownership():
    playlists = sp.current_user_playlists(limit=50)
    found = next((p for p in playlists["items"] if p["id"] == playlist_id), None)
    if not found:
        raise Exception(f"Playlist {playlist_id} not found in your playlists")
    return f"Found: {found['name']}"
check("ownership", check_ownership)

# 3. Playlist metadata
out("\n[3] Playlist metadata (GET /playlists/{id})")
def check_metadata():
    p = sp.playlist(playlist_id)
    keys = list(p.keys())
    track_key = "items" if "items" in p else ("tracks" if "tracks" in p else "MISSING")
    return f"name='{p.get('name')}' public={p.get('public')} track_key='{track_key}' top_level_keys={keys}"
check("metadata", check_metadata)

# 4. Read tracks via sp.playlist()
out("\n[4] Read tracks via sp.playlist() (app method)")
def check_read_tracks():
    p = sp.playlist(playlist_id)
    results = p.get("items") or p.get("tracks")
    if results is None:
        raise Exception(f"No items/tracks key found. Keys: {list(p.keys())}")
    total = results.get("total", "?")
    page = results.get("items", [])
    sample = []
    for item in page[:2]:
        t = item.get("track")
        if t:
            sample.append(f"{t['artists'][0]['name']} - {t['name']}" if t.get("artists") else t.get("name", "?"))
    return f"total={total} sample={sample}"
check("read_tracks", check_read_tracks)

# 5. Add endpoint reachable? (dry run — don't actually add anything)
out("\n[5] Add endpoint check (GET playlist only, not writing)")
def check_add_endpoint():
    # Just verify the playlist object is writable by checking owner matches auth user
    p = sp.playlist(playlist_id, fields="owner")
    current = sp.current_user()["id"]
    owner = p["owner"]["id"]
    if owner != current:
        raise Exception(f"Playlist owner ({owner}) != authenticated user ({current})")
    return f"Owner matches authenticated user ({current})"
check("add_endpoint", check_add_endpoint)

out(f"\nLog: {LOG_FILE}")

if not SILENT:
    input("\nPress Enter to exit...")
