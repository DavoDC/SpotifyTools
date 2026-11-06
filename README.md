# SpotifyTools

[![ko-fi](https://ko-fi.com/img/githubbutton_sm.svg)](https://ko-fi.com/G2G31WKOCN)



Python gateway to Spotify, built to be reused by other projects (the same idea as [ytkit](https://github.com/DavoDC/ytkit) for YouTube and [ffkit](https://github.com/DavoDC/ffkit) for FFmpeg).

All Spotify logic lives here: authentication, a rate-limit-safe API client, track search and match scoring, playlist read and write, Liked Songs handling, and an offline simulator for tests. Your own app imports it and never talks to Spotify directly.

It also ships one ready-made tool: a CLI that syncs an offline music library (AudioMirror XML) to a Spotify playlist.

**Scope:** this repo is the Spotify side only. It does not tag, route or analyse files, and it has no UI; a consuming app supplies those.

---

## Library use

```python
import spotify_tools

assert spotify_tools.API_VERSION == 1          # bumped on any breaking change
client = spotify_tools.build_client()          # authenticated client, loads config/config.json
```

Stable public surface (import only these, never underscore names):

| Name | What it gives you |
|------|-------------------|
| `spotify_tools.API_VERSION` | Integer, bumped on a breaking change |
| `spotify_tools.build_client(config=None)` | Authenticated Spotify client |
| `spotify_tools.spotify_simulator.SimulatedSpotifyClient` | Offline stand-in for tests |
| `spotify_tools.matcher.clean_artist / clean_title / normalise` | Name cleanup used for matching |
| `spotify_tools.acquire.move_liked_to_playlist` | Move Liked Songs into a playlist |
| `spotify_tools.open_playlist.extract_playlist_id / build_search_url` | Playlist URL helpers |
| `spotify_tools.config.CONFIG_PATH / load_config` | Config location and loader |

Clone it next to your project and put `src/` on `sys.path` (or set `SPOTIFY_TOOLS_ROOT`); it is not published to PyPI.

---

## Sync tool: how it works

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
cd src
python -m spotify_tools.main
```

On first run, a browser window will open for Spotify login. After that, auth is cached.

Use `--simulate` to run against mock data without touching the real API.

Use `--reset-exhausted` to retry tracks that gave up after 5 failed searches (e.g. after improving search logic).

---

## Project structure

```
SpotifyTools/
├── CLAUDE.md / GUIDELINES.md   # Engineering rules
├── config/
│   ├── config.json             # Credentials (gitignored)
│   ├── config.example.json     # Template
│   └── requirements.txt
├── src/
│   └── spotify_tools/
│       ├── __init__.py
│       ├── paths.py            # Single source of truth for REPO_ROOT
│       ├── main.py             # CLI entrypoint + pipeline
│       ├── config.py           # Config loading/validation
│       ├── xml_parser.py       # AudioMirror XML reader
│       ├── matcher.py          # Match scoring
│       ├── spotify_interface.py    # ABC for API clients
│       ├── spotify_client.py   # Real Spotify client
│       ├── spotify_simulator.py    # Mock client for testing
│       ├── acquire.py          # Liked Songs -> playlist orchestration (library use)
│       ├── open_playlist.py    # Open playlist tracks in local external app
│       ├── diagnose.py         # Auth diagnostic (python -m spotify_tools.diagnose)
│       ├── history_store.py    # Safe JSON persistence
│       ├── reconciler.py       # Deterministic sync algorithm
│       ├── report_generator.py # Markdown reports
│       └── lockfile.py         # Concurrent run protection
├── tests/
│   ├── unit/                   # Unit tests
│   ├── golden/                 # End-to-end golden path tests
│   └── fixtures/               # Test data
├── scripts/
│   └── run.bat / run.sh        # Launchers
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

**Developed:** March 2026 · **Status:** Actively developed · **Tests:** comprehensive as of 2026-09-04 (`python -m pytest tests/ -v`)
