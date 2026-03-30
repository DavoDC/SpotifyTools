# SpotifyPlaylistGen

Python CLI tool that syncs a local AudioMirror XML music library to a Spotify playlist.

## Mandatory Rules

Read and follow `GUIDELINES.md` before making any changes. It defines engineering principles, architecture patterns, and prohibited practices.

## Tech Stack

- Python 3.x
- spotipy 2.24.0 (Spotify API wrapper)
- pytest 8.3.0

## Project Structure

```
src/
  main.py          — CLI entrypoint, stage orchestration
  spotify.py       — Spotify API client wrapper
  matcher.py       — Track match scoring (EXACT/HIGH/LOW/NONE)
  xml_parser.py    — AudioMirror XML reader
config/
  config.json      — Credentials + settings (gitignored)
  config.example.json
tests/
  test_main.py, test_spotify.py, test_matcher.py, test_xml_parser.py
  fixtures/        — Sample XML files
scripts/
  run.bat          — Windows launcher
  run.sh           — Unix launcher
  diagnose.py      — Pre-flight auth check
data/
  history.json     — Persistent track decision history (gitignored)
  logs/            — Run logs
  reports/         — Match reports
docs/
  spotify-api-reference.md — Hard-won API quirks
```

## Running

```bash
# Run tests
cd C:\Users\David\GitHubRepos\SpotifyPlaylistGen
python -m pytest tests/ -v

# Run the tool
scripts/run.bat
```

## Spotify API Gotchas

- POST `/playlists/{id}/items` requires `{"uris": [...]}` — bare list fails silently
- GET `/playlists/{id}/tracks` is deprecated (403) — use `sp.playlist(id)["items"]`
- First page may return `items=[]` with `total>0` — must paginate via `next` URL
- Response uses `item["item"]` (current) or `item["track"]` (old) — check both
- DELETE dedup: `{"items": [{"uri": "..."}], "snapshot_id": "..."}`

## Next Session - Action Required

Hit Spotify API rate limit on 2026-03-28. Review log before continuing:

`C:\Users\David\GitHubRepos\SpotifyPlaylistGen\data\logs\terminal_28_03_2026_2.txt`
