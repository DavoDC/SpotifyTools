# SpotifyTools

**Two tools in this repo:**
- `src/spotify_tools/main.py` - batch sync tool. Reads AudioMirror XML library, syncs to a Spotify playlist. Run via `scripts/run.bat`.
- `src/spotify_tools/open_playlist.py` - interactive browser. Opens Spotify playlist tracks in browser one by one for review/lookup.

Both share `src/spotify_tools/spotify_client.py` as the Spotify API client.

## Mandatory Rules

Read and follow `GUIDELINES.md` before making any changes. It defines engineering principles, architecture patterns, and prohibited practices.

## Tech Stack

- Python 3.x
- spotipy 2.24.0 (Spotify API wrapper)
- pytest 8.3.0

## Project Structure

```
src/spotify_tools/
  main.py               - CLI entrypoint, stage orchestration (sync tool)
  open_playlist.py      - Interactive playlist browser
  config.py             - Config loading/validation
  xml_parser.py         - AudioMirror XML reader
  matcher.py            - Track match scoring (EXACT/HIGH/LOW/NONE)
  spotify_interface.py  - ABC for Spotify clients
  spotify_client.py     - Real Spotify API client
  spotify_simulator.py  - Mock client for testing
  history_store.py      - Safe JSON persistence
  reconciler.py         - Deterministic sync algorithm
  report_generator.py   - Markdown reports
  lockfile.py           - Concurrent run protection
config/
  config.json           - Credentials + settings (gitignored)
  config.example.json
tests/
  unit/                 - Unit tests
  golden/               - End-to-end golden path tests
  fixtures/             - Test data
scripts/
  run.bat / run.sh      - Launchers
  diagnose.py           - Auth diagnostic
data/
  history.json          - Persistent track decision history (gitignored)
  logs/                 - Run logs
  reports/              - Match reports
```

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

## Next Session - Blocking Bugs

Two bugs block large-library (5000+ track) processing. Full details in `docs/IDEAS.md`.

**Bug #1 - 429 Rate Limit Hang (2026-03-28):** urllib3 has 429 in `status_forcelist`, retries silently with unbounded sleep. Fix: remove 429 from forcelist, cap retry sleep to 30s, increase SEARCH_DELAY_S from 0.1 to 0.5, add heartbeat logging before each API call.

**Bug #2 - Unicode Matching:** `normalise()` doesn't strip diacritics so "JAY-Z" (with diacritic) matches as LOW. Fix: add `unicodedata.normalize('NFKD', s)` to `normalise()` in `matcher.py`.

Review this log from the last rate-limit run before starting:
`C:\Users\David\GitHubRepos\SpotifyTools\data\logs\terminal_28_03_2026_2.txt`
