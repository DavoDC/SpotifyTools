# SpotifyTools

**Tools in this repo:**
- `src/spotify_tools/main.py` - batch sync tool. Reads AudioMirror XML library, syncs to a Spotify playlist. Run via `scripts/run.bat`.
- `src/spotify_tools/open_playlist.py` - interactive browser. Opens Spotify playlist tracks in browser one by one for review/lookup.
- `src/spotify_tools/acquire.py` - shared orchestration (Liked Songs -> inbox playlist). No CLI entrypoint of its own; imported directly by AudioManager's GUI ("Acquire" tab) as a sibling-directory Python import - see `docs/References/GUI-Architecture.md` in AudioManager for the boundary contract.
- `src/spotify_tools/diagnose.py` - auth diagnostic, run via `python -m spotify_tools.diagnose` (also invoked silently on every `scripts/run.sh` launch).

All share `src/spotify_tools/spotify_client.py` as the Spotify API client, built behind the `SpotifyInterface` ABC (`spotify_interface.py`) so `spotify_simulator.py`'s `SimulatedSpotifyClient` can stand in for tests.

## Mandatory Rules

Read and follow `GUIDELINES.md` before making any changes. It defines engineering principles, architecture patterns, and prohibited practices.

## Tech Stack

- Python 3.x
- spotipy 2.24.0 (Spotify API wrapper)
- pytest 8.3.0

## Project Structure

```
src/spotify_tools/
  __init__.py
  paths.py               - Single source of truth for REPO_ROOT (env var SPOTIFY_TOOLS_ROOT, else derived)
  main.py                - CLI entrypoint, stage orchestration (sync tool)
  open_playlist.py       - Interactive playlist browser
  acquire.py             - Liked Songs -> inbox playlist orchestration (used by AudioManager GUI)
  diagnose.py            - Auth diagnostic (python -m spotify_tools.diagnose)
  config.py              - Config loading/validation
  xml_parser.py          - AudioMirror XML reader
  matcher.py             - Track match scoring (EXACT/HIGH/LOW/NONE)
  spotify_interface.py   - ABC for Spotify clients
  spotify_client.py      - Real Spotify API client
  spotify_simulator.py   - Mock client for testing
  history_store.py       - Safe JSON persistence
  reconciler.py          - Deterministic sync algorithm
  report_generator.py    - Markdown reports
  lockfile.py            - Concurrent run protection
config/
  config.json           - Credentials + settings (gitignored)
  config.example.json
tests/
  unit/                 - Unit tests
  golden/               - End-to-end golden path tests
  fixtures/             - Test data
scripts/
  run.bat / run.sh      - Launchers
data/
  history.json          - Persistent track decision history (gitignored)
  logs/                 - Run logs
  reports/              - Match reports
```

All data/config paths (`CONFIG_PATH`, `CACHE_PATH`, `HISTORY_PATH`, etc.) resolve via `paths.REPO_ROOT` - never recompute a `BASE_DIR`/dirname chain in a new file; import `REPO_ROOT` from `paths.py` instead (see `paths.py`'s docstring for the 2026-09-04 off-by-one regression this prevents).

## Running

```bash
# Run tests
cd C:\Users\David\GitHubRepos\SpotifyTools
python -m pytest tests/ -v

# Run the tool
scripts/run.bat
```

## Spotify API Gotchas

- POST `/playlists/{id}/items` requires `{"uris": [...]}` - bare list fails silently
- GET `/playlists/{id}/tracks` is deprecated (403) - use `sp.playlist(id)["items"]`
- First page may return `items=[]` with `total>0` - must paginate via `next` URL
- Response uses `item["item"]` (current) or `item["track"]` (old) - check both
- DELETE dedup: `{"items": [{"uri": "..."}], "snapshot_id": "..."}`

## open_playlist.py Patterns

- `get_playlist_tracks` joins all Spotify artists with ` & `. For search URL building: split on ` & `, take `[0]` (primary). For display: use full joined string.
- Spotify official titles include `(feat. X)` in the title string itself - must be stripped with `_FEAT_RE` before URL encoding, separately from artist extraction.
- Sort tracks by primary artist before sequential opening (`_open_interactively` does this) - groups same-artist tracks for efficient lookup workflow.
- `logger.info` + `print` in same code block = double output on terminal (StreamHandler at INFO level). Use `logger.debug` for file-only, `print` for terminal-only.

## Resolved (kept for history - do not re-open without new evidence)

Both fixed; code confirmed 2026-09-04 (`matcher.py` calls `unicodedata.normalize`, `spotify_client.py` caps 429 retry sleep). See `docs/IDEAS.md` history for anything still open.

- **429 Rate Limit Hang (2026-03-28):** urllib3 retried 429 with unbounded sleep. Fixed: 429 removed from forcelist, retry sleep capped at 30s (`MAX_RETRY_AFTER_S` in `spotify_client.py`), `SEARCH_DELAY_S` raised to 0.5.
- **Unicode Matching:** `normalise()` didn't strip diacritics, so accented names could mismatch. Fixed: `matcher.py`'s `normalise()` runs `unicodedata.normalize('NFKD', s)` then strips combining characters.
