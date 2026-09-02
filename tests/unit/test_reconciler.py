"""Tests for src/reconciler.py — deterministic playlist reconciliation."""

from spotify_tools.reconciler import reconcile, ReconciliationPlan, MAX_SEARCH_ATTEMPTS


def _key(track):
    """Simple track_key function for tests."""
    return f"{track['primary_artist']}|{track['title']}"


def _track(artist="Artist", title="Song", album="Album"):
    return {"primary_artist": artist, "title": title, "album": album}


def _history_entry(state="added", uri="spotify:track:abc", attempts=1, confidence="exact"):
    return {
        "state": state,
        "display": "Artist — Song",
        "spotify_uri": uri,
        "spotify_id": uri.split(":")[-1] if uri else None,
        "match_confidence": confidence,
        "search_attempts": attempts,
        "first_seen": "2026-01-01T00:00:00",
        "last_updated": "2026-01-01T00:00:00",
        "source_file": None,
    }


def _history(entries: dict):
    return {"version": 2, "tracks": entries}


# ── Basic scenarios ──────────────────────────────────────────────────────────

def test_empty_library_empty_playlist():
    plan = reconcile([], _history({}), set(), _key)
    assert not plan.has_work


def test_new_track_needs_search():
    tracks = [_track("Eminem", "Lose Yourself")]
    plan = reconcile(tracks, _history({}), set(), _key)

    assert len(plan.to_search) == 1
    assert plan.to_search[0]["title"] == "Lose Yourself"


def test_already_synced_track_is_skipped():
    tracks = [_track("Eminem", "Lose Yourself")]
    history = _history({
        "Eminem|Lose Yourself": _history_entry(state="added", uri="spotify:track:abc")
    })
    playlist = {"spotify:track:abc"}

    plan = reconcile(tracks, history, playlist, _key)

    assert plan.skipped_synced == 1
    assert not plan.has_work


def test_custom_track_is_skipped():
    tracks = [_track("Rare", "NotOnSpotify")]
    history = _history({
        "Rare|NotOnSpotify": _history_entry(state="custom", uri=None)
    })

    plan = reconcile(tracks, history, set(), _key)

    assert plan.skipped_custom == 1
    assert not plan.has_work


# ── Recovery ─────────────────────────────────────────────────────────────────

def test_history_added_but_missing_from_playlist_triggers_recovery():
    tracks = [_track("Eminem", "Lose Yourself")]
    history = _history({
        "Eminem|Lose Yourself": _history_entry(state="added", uri="spotify:track:abc")
    })
    playlist = set()  # empty — track missing

    plan = reconcile(tracks, history, playlist, _key)

    assert len(plan.to_recover) == 1
    assert plan.to_recover[0]["uri"] == "spotify:track:abc"


# ── Unmatched retry ──────────────────────────────────────────────────────────

def test_unmatched_track_retried():
    tracks = [_track("Unknown", "Ghost")]
    history = _history({
        "Unknown|Ghost": _history_entry(state="unmatched", uri=None, attempts=2)
    })

    plan = reconcile(tracks, history, set(), _key)

    assert len(plan.to_search) == 1


def test_unmatched_track_exhausted_after_max_attempts():
    tracks = [_track("Unknown", "Ghost")]
    history = _history({
        "Unknown|Ghost": _history_entry(state="unmatched", uri=None, attempts=MAX_SEARCH_ATTEMPTS)
    })

    plan = reconcile(tracks, history, set(), _key)

    assert plan.skipped_exhausted == 1
    assert len(plan.to_search) == 0


def test_exhausted_state_is_skipped():
    tracks = [_track("Unknown", "Ghost")]
    history = _history({
        "Unknown|Ghost": _history_entry(state="exhausted", uri=None, attempts=5)
    })

    plan = reconcile(tracks, history, set(), _key)

    assert plan.skipped_exhausted == 1
    assert len(plan.to_search) == 0


# ── Removal ──────────────────────────────────────────────────────────────────

def test_playlist_track_not_in_library_marked_for_removal():
    """Track in playlist but not in XML library → should be removed."""
    tracks = []  # empty library
    history = _history({})
    playlist = {"spotify:track:orphan"}

    plan = reconcile(tracks, history, playlist, _key)

    assert "spotify:track:orphan" in plan.to_remove


def test_track_in_library_and_playlist_not_removed():
    tracks = [_track("Eminem", "Lose Yourself")]
    history = _history({
        "Eminem|Lose Yourself": _history_entry(state="added", uri="spotify:track:abc")
    })
    playlist = {"spotify:track:abc"}

    plan = reconcile(tracks, history, playlist, _key)

    assert len(plan.to_remove) == 0


def test_track_removed_from_xml_gets_removed_from_playlist():
    """If a track was in library+playlist but user deletes XML, it should be removed."""
    # Library no longer has the track
    tracks = [_track("Other", "Song")]
    history = _history({
        "Other|Song": _history_entry(state="added", uri="spotify:track:keep"),
        "Deleted|Track": _history_entry(state="added", uri="spotify:track:remove_me"),
    })
    playlist = {"spotify:track:keep", "spotify:track:remove_me"}

    plan = reconcile(tracks, history, playlist, _key)

    assert "spotify:track:remove_me" in plan.to_remove
    assert "spotify:track:keep" not in plan.to_remove


# ── Mixed scenarios ──────────────────────────────────────────────────────────

def test_mixed_scenario():
    """Multiple tracks in different states."""
    tracks = [
        _track("Synced", "Already"),
        _track("New", "Track"),
        _track("Retry", "Unmatched"),
        _track("Custom", "Skipped"),
    ]
    history = _history({
        "Synced|Already": _history_entry(state="added", uri="spotify:track:synced"),
        "Retry|Unmatched": _history_entry(state="unmatched", uri=None, attempts=2),
        "Custom|Skipped": _history_entry(state="custom", uri=None),
    })
    playlist = {"spotify:track:synced", "spotify:track:orphan"}

    plan = reconcile(tracks, history, playlist, _key)

    assert plan.skipped_synced == 1
    assert plan.skipped_custom == 1
    assert len(plan.to_search) == 2  # New + Retry
    assert "spotify:track:orphan" in plan.to_remove


def test_has_work_true_when_searches_needed():
    plan = ReconciliationPlan()
    plan.to_search = [_track()]
    assert plan.has_work


def test_has_work_true_when_removals_needed():
    plan = ReconciliationPlan()
    plan.to_remove = ["spotify:track:x"]
    assert plan.has_work


def test_has_work_false_when_only_skips():
    plan = ReconciliationPlan()
    plan.skipped_synced = 100
    assert not plan.has_work


# ── Idempotency ──────────────────────────────────────────────────────────────

def test_reconcile_is_deterministic():
    """Running reconcile twice with same inputs produces same plan."""
    tracks = [_track("A", "B"), _track("C", "D")]
    history = _history({
        "A|B": _history_entry(state="added", uri="spotify:track:ab"),
    })
    playlist = {"spotify:track:ab"}

    plan1 = reconcile(tracks, history, playlist, _key)
    plan2 = reconcile(tracks, history, playlist, _key)

    assert len(plan1.to_search) == len(plan2.to_search)
    assert len(plan1.to_remove) == len(plan2.to_remove)
    assert plan1.skipped_synced == plan2.skipped_synced


def test_synced_playlist_produces_no_work():
    """Perfectly synced state → zero operations."""
    tracks = [_track("A", "B"), _track("C", "D")]
    history = _history({
        "A|B": _history_entry(state="added", uri="spotify:track:ab"),
        "C|D": _history_entry(state="added", uri="spotify:track:cd"),
    })
    playlist = {"spotify:track:ab", "spotify:track:cd"}

    plan = reconcile(tracks, history, playlist, _key)

    assert not plan.has_work
    assert plan.skipped_synced == 2
