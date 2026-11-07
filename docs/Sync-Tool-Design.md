# Sync tool design

**Status:** Stabilization pass complete (2026-03-12): four critical defects fixed. The sync CLI's current behaviour is described in README.md.
**Repo:** `<repo-root>` (https://github.com/DavoDC/SpotifyTools)
**Playlist:** the target playlist id comes from `spotify_playlist_id` in `config/config.json` (see README setup). No playlist id is hardcoded in the code or in these docs.
**Stack:** Python 3.x CLI, spotipy 2.24.0, pytest 8.3.0

## Purpose

Convert an offline music library (AudioMirror XML) into a Spotify playlist. The XML reader is one input adapter; the sync core works on a generic track list.

## Architecture (v2, refactored 2026-03-11)

### Module Structure

```
src/spotify_tools/
  __init__.py          - Public surface (API_VERSION, build_client)
  paths.py             - Single source of truth for REPO_ROOT
  main.py              - CLI entrypoint + pipeline orchestration
  config.py            - Config loading/validation
  xml_parser.py        - AudioMirror XML reader
  matcher.py           - Match scoring (EXACT/HIGH/LOW/NONE) + title cleaning
  spotify_interface.py - ABC for swappable API clients
  spotify_client.py    - RealSpotifyClient (wraps spotipy)
  spotify_simulator.py - SimulatedSpotifyClient (deterministic testing)
  history_store.py     - Atomic JSON, backup, v1->v2 migration
  reconciler.py        - Deterministic state diff algorithm
  report_generator.py  - Markdown reports
  lockfile.py          - Concurrent run protection
  acquire.py           - Liked Songs -> playlist orchestration (library use)
  open_playlist.py     - Playlist helpers (ID parsing, search links, track listing)
  diagnose.py          - Auth diagnostic
```

### Pipeline (4 stages)

1. **Parse XML** - read AudioMirror files
2. **Reconcile** - compute diff: desired (XML+history) vs current (playlist)
3. **Search & Match** - Spotify search for unmatched tracks
4. **Apply** - add/remove/recover, save history, generate report

### Key Design Decisions (confirmed 2026-03-11)

- **Deterministic reconciliation**: desired_state vs current_state diff
- **LOW confidence -> NOT added** (saved for manual review)
- **Unmatched retry limit**: 5 attempts, then "exhausted"
- **Full bidirectional sync**: adds AND removes to match XML library
- **History v2**: atomic writes, backup recovery, search_attempts, match_confidence
- **--simulate flag**: uses SimulatedSpotifyClient for testing
- **History saved AFTER playlist writes** (fixes ordering bug)
- **"added" state deferred until Spotify confirms** (fixed 2026-03-12)

### Test Structure

```
tests/
  unit/     - matcher, reconciler, history, config, xml_parser, spotify, main
  golden/   - golden path (small library), 3-run idempotency, dedup, partial matches
  fixtures/ - golden library XML, mock Spotify responses
```

## Defects Fixed (2026-03-12 stabilization)

| # | Bug | Symptom | Root Cause | Fix |
|---|-----|---------|------------|-----|
| 1 | `_wait_for_exit()` recursion | Crashed at end of every interactive run | Called itself instead of `input()` | Fixed to call `input()` |
| 2 | NONE match crisis | Popular tracks across several artists all NONE | `score_match()` only cleaned local title, not Spotify result; `clean_title()` didn't strip metadata tags | Apply `clean_title()` to both sides; strip (Album Version Explicit), (Edit), (Remastered), (with Artist) etc. |
| 3 | Premature "added" state | Failed uploads left history saying "added" | `set_track(state=ADDED)` called before API call | Defer to after `add_tracks()` succeeds; failed URIs -> unmatched |
| 4 | LOW exhaustion gap | LOW matches retried infinitely | Only NONE path had exhaustion check | Added exhaustion check to LOW path; fixed search_attempts increment |

### Why Tests Missed These

| Bug | Reason |
|-----|--------|
| `_wait_for_exit()` recursion | All tests use `interactive=False` |
| NONE crisis | Golden tests use pre-scored simulator fixtures; `score_match` never runs in golden path |
| Premature "added" state | Simulator's `add_tracks` never fails |
| LOW exhaustion gap | Reconciler's backup `search_attempts >= MAX` check masked the state inconsistency |

## Spotify API Facts (HARD-WON)

> Full reference: `docs/SpotifyAPI_Reference.md`. ALWAYS read it first.

- ALL `/tracks` endpoints deprecated -> use `/items`
- GET: track under `item["item"]` (NOT `item["track"]`)
- POST /items: `{"uris": [...]}` - bare list fails silently
- DELETE /items: `{"items": [{"uri": "..."}]}` - no positions support
- First page may return `items=[]` with `total>0` - must paginate
- DO NOT retry DELETEs on 502
- `spotipy` internal methods (`sp._post()`, `sp._delete()`, `sp._get_id()`) used because built-in methods use deprecated endpoints

## Key Rules

- TDD always - tests first
- ALWAYS read `docs/SpotifyAPI_Reference.md` before API work
- Run with `scripts\run.bat` - never tell user to run python directly
- NEVER make API calls from Claude - let run.bat handle it

## Run Notes (2026-03-12)

- A full run stalled at a 429 rate-limit hang partway through the search stage; the fix is listed under Known Issues (now resolved).
- Several per-track log lines were moved to debug level and the terminal output now prints one line per track, so the log is readable during a long run.
- The TODO list was merged into this file.

## Known Issues

Both issues below were fixed; see the "Resolved" section of CLAUDE.md. They are kept for history.

### 429 Rate Limit Hang (resolved)

- Log ended partway through a search stage with HTTP 429 on search
- spotipy's urllib3 Retry had 429 in `status_forcelist`, so it auto-retried using the Retry-After header
- Retry-After can be huge (minutes/hours), causing the program to freeze
- The `_retry_call` wrapper ALSO handled 429, which was a double retry
- **Fix**: 429 removed from `status_forcelist`; `_retry_call` handles it with a capped sleep and logging; `SEARCH_DELAY_S` raised from 0.1 to 0.5

### Unicode Artist Name Bug (resolved)

- Spotify can return an artist name with a non-ASCII letter (for example U+0178 `Ÿ`) where the library has the plain ASCII letter
- `score_match` compared the two strings and returned NONE, even when the search found the track
- `normalise()` now strips diacritics (unicodedata NFKD, then combining characters are removed)

### Other NONE Patterns Observed

- Artist names with punctuation such as `$` may cause search/match issues
- Collaboration tracks where the library's primary artist is not the Spotify primary artist will not match on the primary artist alone
- Some album tracks may genuinely not be on Spotify, and some soundtracks are not on Spotify; these stay unmatched

## Research Archive

The initial third-party tool assessment (`docs/Third-party-tool-assessment.md`) evaluated four existing import tools. All were rejected in favour of a custom solution. Kept for reference only; its recommendation is historical and is not the current design.
