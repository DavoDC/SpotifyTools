# SpotifyTools

Python CLI tool that reads your offline music library (AudioMirror XML) and syncs it to a Spotify playlist.

**Use case:** Offline music library at home → listen to the same tracks on Spotify at work.

---

## How it works

1. Reads XML files from your AudioMirror library
2. Searches Spotify for each track using artist + title + album
3. Shows matches with confidence scores — you review and confirm before anything is added
4. Adds confirmed matches to your Spotify playlist
5. Saves decision history — re-runs only process new/unmatched tracks

---

## Setup

### 1. Create a Spotify Developer app

1. Go to [Spotify Developer Dashboard](https://developer.spotify.com/dashboard)
2. Create a new app with these settings:
   - **Redirect URI:** `http://127.0.0.1:8888/callback`
   - **API/SDKs:** Web API
3. Copy your **Client ID** and **Client Secret**

### 2. Configure

Copy and fill in the config file:

```bash
cp config.example.json config.json
```

Edit `config.json`:

```json
{
  "spotify_client_id": "your_client_id",
  "spotify_client_secret": "your_client_secret",
  "spotify_redirect_uri": "http://127.0.0.1:8888/callback",
  "spotify_playlist_id": "your_playlist_id",
  "audiomirror_path": "<home>/GitHubRepos/AudioMirror/AUDIO_MIRROR"
}
```

**To get your playlist ID:** open the playlist in Spotify → Share → Copy link → the ID is the part after `/playlist/` and before `?`

### 3. Install dependencies

```bash
pip install -r requirements.txt
```

### 4. Run

```bash
python main.py
```

On first run, a browser window will open for Spotify login. After that, auth is cached.

---

## Files

```
SpotifyTools/
├── main.py              # Entry point
├── config.json          # Your credentials (gitignored)
├── config.example.json  # Template
├── history.json         # Decision history (auto-created)
├── src/
│   ├── xml_parser.py    # Reads AudioMirror XML files
│   ├── spotify.py       # Spotify API calls + auth
│   └── matcher.py       # Match logic + confidence scoring
├── tests/
└── logs/
```

---

## Track states (history.json)

| State | Meaning |
|-------|---------|
| `added` | Matched and added to playlist — skipped on re-run |
| `custom` | Your custom track, won't exist on Spotify — skipped on re-run |
| `rejected` | Bad match, rejected by you — retried on re-run |
| `unmatched` | No match found — retried on re-run |

---

## Running tests

```bash
pytest
```
