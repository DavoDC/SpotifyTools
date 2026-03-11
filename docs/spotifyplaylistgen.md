# Spotify Playlist Generator

**Status:** Major refactor complete — deterministic reconciler, 126 tests passing
**Repo:** `C:\Users\David\GitHubRepos\SpotifyPlaylistGen` (https://github.com/DavoDC/SpotifyPlaylistGen)
**Playlist ID:** `50W1xpWQPLVDSFeeBqpjSp`
**Stack:** Python CLI

## Purpose
Convert David's offline music library (AudioMirror XML) into a Spotify playlist he can use at work.

## Architecture (v2 — refactored 2026-03-11)

### Module Structure
```
src/
  config.py            — Config loading/validation
  xml_parser.py        — AudioMirror XML reader
  matcher.py           — Match scoring (EXACT/HIGH/LOW/NONE)
  spotify_interface.py — ABC for swappable API clients
  spotify_client.py    — RealSpotifyClient (wraps spotipy)
  spotify_simulator.py — SimulatedSpotifyClient (deterministic testing)
  history_store.py     — Atomic JSON, backup, v1→v2 migration
  reconciler.py        — Deterministic state diff algorithm
  report_generator.py  — Markdown reports
  main.py              — CLI entrypoint + pipeline orchestration
```

### Pipeline (4 stages)
1. **Parse XML** — read AudioMirror files
2. **Reconcile** — compute diff: desired (XML+history) vs current (playlist)
3. **Search & Match** — Spotify search for unmatched tracks
4. **Apply** — add/remove/recover, save history, generate report

### Key Design Decisions (confirmed 2026-03-11)
- **Deterministic reconciliation**: desired_state vs current_state diff
- **LOW confidence → NOT added** (saved for manual review)
- **Unmatched retry limit**: 5 attempts, then "exhausted"
- **Full bidirectional sync**: adds AND removes to match XML library
- **History v2**: atomic writes, backup recovery, search_attempts, match_confidence
- **--simulate flag**: uses SimulatedSpotifyClient for testing
- **History saved AFTER playlist writes** (fixes the ordering bug)

### Test Structure
```
tests/
  unit/     — 111 tests (config, history, reconciler, matcher, xml_parser, spotify, main)
  golden/   — 15 tests (10-track golden path, 3-run idempotency)
  fixtures/ — golden library XML, mock Spotify responses, original AUDIO_MIRROR
```

### Repo Structure
```
repo/
├── CLAUDE.md / GUIDELINES.md  # Engineering constitution
├── config/                    # config.json (gitignored), requirements.txt
├── data/                      # gitignored: history.json, logs/, reports/
├── docs/                      # spotify-api-reference.md
├── src/                       # all source
├── tests/                     # unit/ + golden/ + fixtures/
└── scripts/                   # run.bat, run.sh, diagnose.py
```

## Key Spotify API Facts (HARD-WON)

> Full reference: `docs/spotify-api-reference.md`. **ALWAYS read it first.**

- ALL `/tracks` endpoints deprecated → use `/items`
- GET: track under `item["item"]` (NOT `item["track"]`)
- POST /items: `{"uris": [...]}` — bare list fails silently
- DELETE /items: `{"items": [{"uri": "..."}]}` — no positions support
- First page may return `items=[]` with `total>0` — must paginate
- DO NOT retry DELETEs on 502

## Rename Idea
Consider renaming to "MusicLibPlaylistSyncer" or similar — better describes what it does.

## Key Rules
- TDD always — tests first
- ALWAYS read `docs/spotify-api-reference.md` before API work
- Run with `scripts\run.bat` — never tell user to run python directly
- NEVER make API calls from Claude — let run.bat handle it
