# SpotifyTools - Developer Context

Implementation invariants and code patterns. Demand-loaded when working in this codebase.

---

## Check git status before extending a other-repo consumer's target method

**Before adding to or relying on any method here, check `git status`/`git diff` first - a method can look like stable pre-existing code while actually being uncommitted work from an earlier session.** Found 2026-09-01: `get_playlist_tracks_detailed()` in `spotify_tools/spotify_client.py` (used by consumers) had been written in a prior session but never committed. Extending it without checking would have silently built on top of unlanded work. Grep for callers in other projects before trusting a cross-repo dependency's current state.
