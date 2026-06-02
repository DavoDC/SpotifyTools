# SpotifyPlaylistGen

[![ko-fi](https://ko-fi.com/img/githubbutton_sm.svg)](https://ko-fi.com/G2G31WKOCN)



Python CLI tool that syncs your offline music library (AudioMirror XML) to a Spotify playlist.

**Use case:** Offline music library at home → listen to the same tracks on Spotify at work.

---

## How it works

1. Reads XML files from your AudioMirror library
2. Computes a sync plan: what to add, remove, recover, or search
3. Searches Spotify for unmatched tracks (artist + title + album)
4. Adds EXACT and HIGH confidence matches to your playlist automatically
5. LOW confidence matches are saved for manual review (not added)
6. Saves decision history - re-runs only process new/changed tracks
7. Removes tracks from playlist if they're deleted from your library

The tool is **deterministic and idempotent** - running it multiple times always converges to the same playlist state.

---

## Setup

### 1. Create a Spotify Developer app

1. Go to [Spotify Developer Dashboard](https://developer.spotify.com/dashboard)
2. Create a new app with these settings:
   - **Redirect URI:** `http://127.0.0.1:8888/callback`
   - **API/SDKs:** Web API
3. Copy your **Client ID** and **Client Secret**

### 2. Configure

```bash
cp config/config.example.json config/config.json
```

Edit `config/config.json`:

```json
{
  "spotify_client_id": "your_client_id",
  "spotify_client_secret": "your_client_secret",
  "spotify_redirect_uri": "http://127.0.0.1:8888/callback",
  "spotify_playlist_id": "your_playlist_id",
  "audiomirror_path": "C:/path/to/AudioMirror/AUDIO_MIRROR"
}
```

**To get your playlist ID:** open the playlist in Spotify → Share → Copy link → the ID is the part after `/playlist/` and before `?`

### 3. Install dependencies

```bash
pip install -r config/requirements.txt
```

### 4. Run

Double-click `scripts/run.bat` (Windows) or:

```bash
python -m src.main
```

On first run, a browser window will open for Spotify login. After that, auth is cached.

Use `--simulate` to run against mock data without touching the real API.

Use `--reset-exhausted` to retry tracks that gave up after 5 failed searches (e.g. after improving search logic).

---

## Project structure

```
SpotifyPlaylistGen/
├── CLAUDE.md / GUIDELINES.md   # Engineering rules
├── config/
│   ├── config.json             # Credentials (gitignored)
│   ├── config.example.json     # Template
│   └── requirements.txt
├── src/
│   ├── main.py                 # CLI entrypoint + pipeline
│   ├── config.py               # Config loading/validation
│   ├── xml_parser.py           # AudioMirror XML reader
│   ├── matcher.py              # Match scoring
│   ├── spotify_interface.py    # ABC for API clients
│   ├── spotify_client.py       # Real Spotify client
│   ├── spotify_simulator.py    # Mock client for testing
│   ├── history_store.py        # Safe JSON persistence
│   ├── reconciler.py           # Deterministic sync algorithm
│   ├── report_generator.py     # Markdown reports
│   └── lockfile.py             # Concurrent run protection
├── tests/
│   ├── unit/                   # Unit tests
│   ├── golden/                 # End-to-end golden path tests
│   └── fixtures/               # Test data
├── scripts/
│   ├── run.bat / run.sh        # Launchers
│   └── diagnose.py             # Auth diagnostic
├── docs/
│   └── spotify-api-reference.md
└── data/                       # Gitignored runtime data
    ├── history.json            # Decision history
    ├── logs/                   # Run logs
    └── reports/                # Match reports
```

---

## Track states (history.json)

| State | Meaning |
|-------|---------|
| `added` | Matched and in playlist - skipped on re-run |
| `unmatched` | No match found - retried on re-run |
| `exhausted` | Failed 5+ times - no longer retried |
| `custom` | Manually marked as not on Spotify - always skipped |

---

## Running tests

```bash
python -m pytest tests/ -v
```

---

## Development

**Developed:** March 2026 · **Status:** Actively developed · **Tests:** 88
