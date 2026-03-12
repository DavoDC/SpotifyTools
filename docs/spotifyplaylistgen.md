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

## TODO

### Next: Live Verification

- [ ] Run live via `scripts/run.bat` — verify matcher fixes resolve NONE crisis for ~4868 unmatched tracks
- [ ] Review match report in `data/reports/` — confirm match rate improved

### Low Priority: Polish

- [ ] Rename "NONE" to "NOT FOUND" — clearer CLI output
- [ ] Heartbeat — print track name BEFORE API call starts (prevents "stuck" feeling)
- [ ] Stricter types — Pylance reports 900+ errors, add type hints gradually
- [ ] Rename project — consider "MusicLibPlaylistSyncer" across files/imports/READMEs

### Stretch

- [ ] Rate limit verification — confirm exponential backoff works for 5000+ track runs
- [ ] `--reset-exhausted` CLI flag — retry all exhausted tracks after search logic improvements

## Research Archive

The initial tool assessment (`docs/archive/SpotifyImport-tool-assessment.md`) evaluated 4 existing import tools. All were rejected in favour of a custom solution. Kept for reference only.
