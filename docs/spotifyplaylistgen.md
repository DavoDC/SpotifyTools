# Spotify Playlist Generator

**Status:** Stabilization pass complete — 170 tests passing, 4 critical defects fixed
**Repo:** `C:\Users\David\GitHubRepos\SpotifyPlaylistGen` (https://github.com/DavoDC/SpotifyPlaylistGen)
**Playlist:** https://open.spotify.com/playlist/50W1xpWQPLVDSFeeBqpjSp
**Playlist ID:** `50W1xpWQPLVDSFeeBqpjSp`
**Stack:** Python 3.x CLI, spotipy 2.24.0, pytest 8.3.0

## Purpose

Convert David's offline music library (AudioMirror XML) into a Spotify playlist he can use at work.

## Architecture (v2 — refactored 2026-03-11)

### Module Structure

```
src/
  config.py            — Config loading/validation
  xml_parser.py        — AudioMirror XML reader
  matcher.py           — Match scoring (EXACT/HIGH/LOW/NONE) + title cleaning
  spotify_interface.py — ABC for swappable API clients
  spotify_client.py    — RealSpotifyClient (wraps spotipy)
  spotify_simulator.py — SimulatedSpotifyClient (deterministic testing)
  history_store.py     — Atomic JSON, backup, v1->v2 migration
  reconciler.py        — Deterministic state diff algorithm
  report_generator.py  — Markdown reports
  lockfile.py          — Concurrent run protection
  main.py              — CLI entrypoint + pipeline orchestration
```

### Pipeline (4 stages)

1. **Parse XML** — read AudioMirror files
2. **Reconcile** — compute diff: desired (XML+history) vs current (playlist)
3. **Search & Match** — Spotify search for unmatched tracks
4. **Apply** — add/remove/recover, save history, generate report

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
  unit/     — matcher, reconciler, history, config, xml_parser, spotify, main
  golden/   — 10-track golden path, 3-run idempotency, dedup, partial matches
  fixtures/ — golden library XML, mock Spotify responses
```

## Defects Fixed (2026-03-12 stabilization)

| # | Bug | Symptom | Root Cause | Fix |
|---|-----|---------|------------|-----|
| 1 | `_wait_for_exit()` recursion | Crashed at end of every interactive run | Called itself instead of `input()` | Fixed to call `input()` |
| 2 | NONE match crisis | Popular tracks (Calvin Harris, DJ Khaled, Drake) all NONE | `score_match()` only cleaned local title, not Spotify result; `clean_title()` didn't strip metadata tags | Apply `clean_title()` to both sides; strip (Album Version Explicit), (Edit), (Remastered), (with Artist) etc. |
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

> Full reference: `docs/spotify-api-reference.md`. ALWAYS read it first.

- ALL `/tracks` endpoints deprecated -> use `/items`
- GET: track under `item["item"]` (NOT `item["track"]`)
- POST /items: `{"uris": [...]}` — bare list fails silently
- DELETE /items: `{"items": [{"uri": "..."}]}` — no positions support
- First page may return `items=[]` with `total>0` — must paginate
- DO NOT retry DELETEs on 502
- `spotipy` internal methods (`sp._post()`, `sp._delete()`, `sp._get_id()`) used because built-in methods use deprecated endpoints

## Key Rules

- TDD always — tests first
- ALWAYS read `docs/spotify-api-reference.md` before API work
- Run with `scripts\run.bat` — never tell user to run python directly
- NEVER make API calls from Claude — let run.bat handle it

## Session 2 Run Results (2026-03-12 21:31)

- 5471 tracks in library, 1103 already synced, 4368 to search
- Got to track 649/4368 before hanging (~15%)
- 500 tracks successfully uploaded in 5 batches of 100
- Match rate ~78% (500 matched / 637 searched) — MUCH better than pre-stabilization
- No report generated (run didn't complete)
- 22 instances of HTTP 429 in log

### Fixes applied before this run

- `setup_logging()` split: DEBUG to file, INFO to terminal
- All per-track logs ([SEARCH], [MATCH], [RESULT], [DECISION]) → `logging.debug()`
- Added [API] debug logging to `_retry_call`
- Terminal output: each track on its own line (no more `\r` overwrite)
- TODO.md merged into this file

## Known Issues

### 429 Rate Limit Hang (critical)

- Log ends at track 649 with HTTP 429 on search
- spotipy's urllib3 Retry has 429 in `status_forcelist` — it auto-retries with Retry-After header
- Retry-After can be huge (minutes/hours), causing program to freeze
- Our `_retry_call` wrapper ALSO handles 429 — double retry!
- **Fix**: Remove 429 from `status_forcelist`, let `_retry_call` handle it with capped sleep + logging
- Also increase `SEARCH_DELAY_S` from 0.1 to 0.5 to reduce rate limit hits

### JAY-Z Unicode Bug (critical)

- Spotify returns artist as `JAŸ-Z` (with `Ÿ` = U+0178) not `JAY-Z`
- `score_match` compares `jay-z` vs `jaÿ-z` → NONE for ALL Jay-Z tracks
- Same issue likely affects other artists with special chars
- `normalise()` needs to strip diacritics/accents (unicodedata.normalize NFKD + strip combining chars)
- Explains Jay-Z Song Cry, Renegade, Young Forever, Empire State of Mind ALL returning NONE despite being found by search

### Other NONE Patterns Observed

- Joey Bada$$ — `$` in name may cause search/match issues
- Justin Bieber collab tracks (2U, Cold Water, Let Me Love You) — primary artist in XML is Bieber but on Spotify it's the other artist (David Guetta, Major Lazer, DJ Snake)
- Kanye VULTURES album tracks — may genuinely not be on Spotify
- Jersey Boys — likely soundtrack not on Spotify

## TODO

### Next
- [ ] Apply Critical Fix 1 — 429 Rate Limit Hang: Remove 429 from status_forcelist so urllib3 doesn't silently block. Cap _retry_call's 429 sleep to 30s. Increase SEARCH_DELAY_S from 0.1 to 0.5 (already partially applied)
- [ ] Apply Critical Fix 2 — Unicode Bug: Add NFKD normalizatBoth preserve ion to normalise() to strip diacritics (JAŸ-Z → JAY-Z).
- [ ] Primary Goal is to handle 5000 songs in one script run without hanging!
- [ ] Fix 429 hang: remove from `status_forcelist`, cap retry sleep, increase `SEARCH_DELAY_S`
- [ ] Fix unicode artist matching (JAŸ-Z bug): add NFKD normalization to `normalise()`
- [ ] Re-run and verify match rate + completion
- [ ] Review match report in `data/reports/` — confirm match rate improved

### Polish

- [ ] Optimize logs for Claude token usage, reduce size
- [ ] Rename "NONE" to "NOT FOUND" — clearer CLI output
- [ ] Heartbeat — print track name BEFORE API call starts (prevents "stuck" feeling)
- [ ] Stricter types — Pylance reports 900+ errors, add type hints gradually
- [ ] Rename project — consider "MusicLibPlaylistSyncer" across files/imports/READMEs
- [x] Terminal output: each track on its own line (fixed in 186be2b)
- [ ] Log file results section is huge, format nicer for humans
- [ ] `--reset-exhausted` CLI flag — retry all exhausted tracks after search logic improvements
- [ ] Run AudioManager before running this program so Audio Mirror is up to date

## Research Archive

The initial tool assessment (`docs/archive/SpotifyImport-tool-assessment.md`) evaluated 4 existing import tools. All were rejected in favour of a custom solution. Kept for reference only.
