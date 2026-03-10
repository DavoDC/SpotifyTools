"""
Quick Spotify auth diagnostic. Run with: python scripts/diagnose.py
"""
import json, os, sys
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
from src.spotify import create_client

CONFIG_PATH = os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))), "config", "config.json")
with open(CONFIG_PATH) as f:
    config = json.load(f)

sp = create_client(config)
playlist_id = config["spotify_playlist_id"]

print("\n=== Spotify Diagnostics ===\n")

# 1. Current user
user = sp.current_user()
print(f"[1] Authenticated as: {user['display_name']} ({user['id']})")

# 2. List user's playlists — is our target in there?
print(f"\n[2] Your playlists (first 20):")
playlists = sp.current_user_playlists(limit=20)
found = False
for p in playlists["items"]:
    marker = " <-- TARGET" if p["id"] == playlist_id else ""
    print(f"     {p['id']}  {p['name']}{marker}")
    if p["id"] == playlist_id:
        found = True
if not found:
    print(f"     !! Playlist {playlist_id} NOT found in your playlists !!")

# 3. Get playlist metadata
print(f"\n[3] Fetching playlist metadata for {playlist_id}...")
try:
    p = sp.playlist(playlist_id, fields="id,name,owner,public")
    print(f"     Name:   {p['name']}")
    print(f"     Owner:  {p['owner']['display_name']} ({p['owner']['id']})")
    print(f"     Public: {p['public']}")
except Exception as e:
    print(f"     ERROR: {e}")

# 4. Fetch tracks via sp.playlist() (the fix)
print(f"\n[4] Fetching tracks via sp.playlist() (main playlist)...")
try:
    tracks = sp.playlist(playlist_id)["tracks"]
    print(f"     OK — total tracks: {tracks['total']}, first page: {len(tracks['items'])} items")
    for item in tracks["items"][:3]:
        t = item.get("track")
        if t:
            print(f"       - {t['artists'][0]['name']} - {t['name']}")
except Exception as e:
    print(f"     ERROR: {e}")

# 5. Test on a different playlist to confirm it's not playlist-specific
OTHER_PLAYLIST = "321LEomVmFIYZR0GZgpz1z"  # Best Akira Musivation (owned by user)
print(f"\n[5] Fetching tracks from a different playlist ({OTHER_PLAYLIST})...")
try:
    tracks2 = sp.playlist(OTHER_PLAYLIST)["tracks"]
    print(f"     OK — total tracks: {tracks2['total']}, first page: {len(tracks2['items'])} items")
    for item in tracks2["items"][:3]:
        t = item.get("track")
        if t:
            print(f"       - {t['artists'][0]['name']} - {t['name']}")
except Exception as e:
    print(f"     ERROR: {e}")

print("\nDone.")
input("\nPress Enter to exit...")
