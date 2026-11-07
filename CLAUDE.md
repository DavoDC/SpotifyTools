# SpotifyTools

## Role and boundary (read first)

This repo is the **Spotify gateway module**, a reusable helper like ytkit (YouTube) and ffkit (FFmpeg). All Spotify logic lives here and nowhere else: auth, API client, search, match scoring, playlist and Liked Songs operations, simulator, plus the library-to-playlist sync CLI. Consumers import it; they never call Spotify themselves.

Scope: this repo owns everything that talks to or reasons about Spotify. No UI, no file tagging, no library routing; those belong to the consuming apps.
Scope rule: never in this repo: UI, file tagging or routing, integrations with other apps, consumer-specific defaults (the inbox playlist default is the neutral "Inbox"; consumers pass their own name), consumer names. Done additions: `matcher.primary_artist`, `matcher.title_key`, `matcher.content_key`, `PUBLIC_API`, `open_playlist.build_search_url(artist, title)`. Planned additions, all additive so `API_VERSION` stays 1: `matcher.search_query`, `open_playlist.parse_playlist_id`, one `PUBLIC_API` tuple that README, `__init__` docstring and the list below must match. The former alias is removed; its removal is a breaking change, so `API_VERSION` bump to 2 is still undecided. The sync CLI input becomes a generic track list (`library_path` setting, `audiomirror_path` kept as legacy alias) with the AudioMirror XML reader as one adapter. `tests/unit/test_public_naming.py` guards the naming rule; keep it green.

Rules that follow: a Spotify feature needed by a consumer is added HERE with a stable public name, never duplicated in the consumer. Library-file logic (tags, routing, analysis) never goes into this repo. Public docs (README, code, commits) never name unreleased repos, private paths or other consumers; consumers are described generically ("other projects"). A breaking change to the public surface bumps `API_VERSION`.

**Tools in this repo:**
- `src/spotify_tools/main.py` - batch sync tool. Reads AudioMirror XML library, syncs to a Spotify playlist. Run via `scripts/run.bat`.
- `src/spotify_tools/open_playlist.py` - playlist helpers. Prints a Spotify playlist's tracks as "artist - title" for review/lookup.
- `src/spotify_tools/acquire.py` - shared orchestration (Liked Songs -> inbox playlist). No CLI entrypoint of its own; imported by consumers as a sibling-directory Python import (public surface below).
- `src/spotify_tools/diagnose.py` - auth diagnostic, run via `python -m spotify_tools.diagnose` (also invoked silently on every `scripts/run.sh` launch).

All share `src/spotify_tools/spotify_client.py` as the Spotify API client, built behind the `SpotifyInterface` ABC (`spotify_interface.py`) so `spotify_simulator.py`'s `SimulatedSpotifyClient` can stand in for tests.

## Mandatory Rules

Read and follow `docs/References/Engineering-Guidelines.md` before making any changes. It defines engineering principles, architecture patterns, and prohibited practices.

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
  open_playlist.py       - Playlist helpers (ID parsing, search links, track listing)
  acquire.py             - Liked Songs -> inbox playlist orchestration (used by consumers)
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
cd <repo-root>
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
- Sort tracks by primary artist before printing (`format_track_lines` does this) - groups same-artist tracks for lookup.
- `logger.info` + `print` in same code block = double output on terminal (StreamHandler at INFO level). Use `logger.debug` for file-only, `print` for terminal-only.

## Resolved (kept for history - do not re-open without new evidence)

Both fixed; code confirmed 2026-09-04 (`matcher.py` calls `unicodedata.normalize`, `spotify_client.py` caps 429 retry sleep).
- **429 Rate Limit Hang (2026-03-28):** urllib3 retried 429 with unbounded sleep. Fixed: 429 removed from forcelist, retry sleep capped at 30s (`MAX_RETRY_AFTER_S` in `spotify_client.py`), `SEARCH_DELAY_S` raised to 0.5.
- **Unicode Matching:** `normalise()` didn't strip diacritics, so accented names could mismatch. Fixed: `matcher.py`'s `normalise()` runs `unicodedata.normalize('NFKD', s)` then strips combining characters.

## Claude instructions

Stable public surface for consumers: `spotify_tools.API_VERSION` (int, bump on breaking change), `spotify_tools.build_client(config=None)` (wraps `RealSpotifyClient`, `None` loads the default config). Plus the already-public `config.CONFIG_PATH`, `config.load_config`, `matcher.clean_artist/clean_title/normalise/primary_artist/title_key/content_key`, `open_playlist.extract_playlist_id`, `open_playlist.build_search_url(artist, title)`, `acquire.move_liked_to_playlist`, `spotify_simulator.SimulatedSpotifyClient`. Consumers must import only these, never underscore names.
