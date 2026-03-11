# Engineering Guidelines

This document defines mandatory engineering rules for Claude when modifying this repository.

These rules exist because repeated runtime errors have occurred due to architectural mistakes and fragile fixes.

Claude must follow these rules strictly.

Correctness, determinism, and reliability are more important than speed or minimal code.

---

## Primary Goal

Build a deterministic, reliable Python CLI tool that converts a local AudioMirror XML music library into a Spotify playlist.

The program must be safe to run repeatedly and must always converge to the same playlist state.

---

## Core Engineering Principles

### 1. Determinism

Running the program multiple times must produce the same playlist state.

No operation should cause different results across runs unless the input XML changes.

### 2. Idempotency

All operations must be idempotent.

Running the program again must not:

- Add duplicate tracks
- Corrupt history
- Modify correct results
- Create inconsistent state

### 3. Defensive Programming

Assume all external systems are unreliable.

Spotify API responses may contain:

- Missing fields
- Empty arrays
- Partial data
- Unexpected schema changes

All API responses must be validated.

### 4. Clear Separation of Responsibilities

Each module must have a single clear responsibility.

Target structure:

```
src/
  xml_parser.py          — Parse AudioMirror XML
  matcher.py             — Normalize strings + match/score tracks
  spotify_interface.py   — ABC for swappable API clients
  spotify_client.py      — Real Spotify API wrapper (retries, pagination)
  spotify_simulator.py   — Deterministic mock for testing
  reconciler.py          — Deterministic playlist state reconciliation
  history_store.py       — Manage history.json safely (atomic writes)
  config.py              — Config loading and validation
  report_generator.py    — Produce human-readable results
  lockfile.py            — Concurrent run protection
  main.py                — CLI entrypoint + pipeline orchestration
```

No module should perform unrelated tasks.

---

## Mandatory Architecture Patterns

### 1. Deterministic Playlist Reconciliation

The playlist must be managed using a state reconciliation model.

```
desired_state = tracks_from_xml
current_state = tracks_in_playlist
operations = diff(desired_state, current_state)
```

Only perform required operations. Never add tracks blindly.

### 2. Spotify API Wrapper

All Spotify API access must go through `spotify_client.py`.

The wrapper must handle:

- Retries
- Rate limits
- Pagination
- Network errors
- Partial responses
- Logging

No other module may call Spotify directly.

### 3. Safe History System

`history.json` acts as persistent memory.

Each record must contain:

- `track_id`
- `search_query`
- `match_type`
- `spotify_track_id`
- `timestamp`

The history system must:

- Prevent duplicate processing
- Tolerate partial writes
- Validate schema on load

---

## Error Handling Rules

Never silently ignore errors.

Errors must be either:

- Logged clearly
- Retried safely
- Surfaced to the CLI

When retrying API requests:

- Use exponential backoff
- Limit retries
- Never retry indefinitely

---

## File Safety Rules

When writing `history.json`:

1. Write to temporary file
2. Validate JSON
3. Atomic rename to final file

Never risk corrupting history.

---

## Matching Rules

Matching must classify results into:

- `EXACT`
- `HIGH_CONFIDENCE`
- `LOW_CONFIDENCE`
- `NO_MATCH`

Only `EXACT` or `HIGH_CONFIDENCE` matches may be automatically added to playlists.

---

## Code Style Rules

The codebase must prioritize readability and reliability.

Prefer:

- Clear function names
- Small functions
- Explicit error handling
- Type hints where helpful

Avoid:

- Deep nesting
- Hidden side effects
- Global mutable state

---

## Testing Requirements

Critical logic must be testable.

Modules that must support unit tests:

- `xml_parser`
- `matcher`
- `reconciler`
- `history_store`

Spotify API calls must be mockable.

---

## Prohibited Practices

Claude must never:

- Mix API calls with business logic
- Modify multiple subsystems in a single change
- Introduce hidden state
- Bypass the `spotify_client` wrapper
- Write directly to `history.json` without safety checks
- Add tracks to playlists without reconciliation logic

---

## Change Policy

Before writing code, Claude must:

1. Explain the design change
2. Explain how it preserves determinism
3. Explain how it prevents duplicate tracks
4. Explain how it handles Spotify API instability

---

## Final Engineering Requirement

This project must implement these three reliability improvements:

1. Deterministic playlist reconciliation algorithm
2. A dedicated Spotify API wrapper isolating network behavior
3. A robust persistent history system

These three improvements together typically reduce AI-generated code error loops by approximately 90%.

The architecture must enforce these principles.

---

## Design Decisions (User-Confirmed 2026-03-11)

These decisions were made during architecture review and are final.

### 1. LOW Confidence Matches → Skip

LOW matches are NOT added to the playlist. They are saved to a review list in a readable format so the user can inspect and manually approve later. Only EXACT and HIGH are auto-added.

### 2. Intentional Playlist Removals → Re-add + Flag

If a track is in history as "added" but missing from the playlist, re-add it. This is treated as an unexpected gap, not an intentional removal. Additionally, flag these recoveries in the report as surprising — the user does not plan to manually remove tracks.

### 3. Unmatched Retry Limit → 5 Attempts

After 5 failed search attempts across separate runs, mark the track as "exhausted" and stop retrying. User can reset manually by editing history.

### 4. Track Removal from XML → Remove from Playlist

If a track is deleted from the local XML library, the reconciler must remove it from the Spotify playlist. The tool performs full bidirectional reconciliation: adds what's missing, removes what shouldn't be there.

### 5. History Migration → Enrich Existing

Migrate the current `history.json` to the new schema by adding missing fields (`search_attempts`, `match_confidence`, `spotify_id`, `version`) with sensible defaults. Verify the migration is correct before overwriting. Do not start fresh.

### 6. Playlist State → 603 Unique Tracks

The playlist currently has 603 unique tracks (duplicates were already cleaned). The reconciler should maintain this as baseline.

### 7. Concurrent Run Protection → Lockfile

Use a lockfile to prevent two instances from running simultaneously. Most reliable approach.

### 8. Removal Policy → Yes, Remove Tracks

The tool MUST remove tracks from the playlist when:
- Duplicates exist in the playlist
- A track was removed from the offline XML library
- A track was accidentally/incorrectly added

This makes the tool a true reconciler — the playlist always mirrors the XML library (for matched tracks).
