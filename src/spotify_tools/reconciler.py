"""Deterministic playlist reconciliation engine.

Computes the diff between desired state (XML library + history) and current state
(live Spotify playlist), then produces an ordered list of operations.

This is the core algorithm. It never calls Spotify directly — it only computes
what SHOULD happen. The caller (main.py) executes the plan.
"""

import logging
from dataclasses import dataclass, field

MAX_SEARCH_ATTEMPTS = 5


@dataclass
class ReconciliationPlan:
    """All operations needed to sync the playlist."""
    to_search: list[dict] = field(default_factory=list)    # tracks needing Spotify search
    to_add: list[str] = field(default_factory=list)         # URIs to add to playlist
    to_remove: list[str] = field(default_factory=list)      # URIs to remove from playlist
    to_recover: list[dict] = field(default_factory=list)    # history says added, playlist missing
    skipped_synced: int = 0                                  # already in sync
    skipped_custom: int = 0                                  # user-excluded
    skipped_exhausted: int = 0                               # gave up after MAX_SEARCH_ATTEMPTS

    @property
    def has_work(self) -> bool:
        return bool(self.to_search or self.to_add or self.to_remove or self.to_recover)


def reconcile(library_tracks: list[dict],
              history: dict,
              playlist_uris: set[str],
              track_key_fn) -> ReconciliationPlan:
    """Compute the reconciliation plan.

    Args:
        library_tracks: parsed XML tracks (each has primary_artist, title, album, etc.)
        history: loaded history dict (v2 format with "tracks" key)
        playlist_uris: set of spotify URIs currently in the playlist
        track_key_fn: function to compute "Artist|Title" key from a track dict

    Returns:
        ReconciliationPlan with all operations needed
    """
    plan = ReconciliationPlan()
    tracks_data = history.get("tracks", {})

    # Track which history URIs are accounted for by library tracks
    desired_uris = set()

    for track in library_tracks:
        key = track_key_fn(track)
        entry = tracks_data.get(key)

        if entry is None:
            # Brand new track — needs search
            plan.to_search.append(track)
            continue

        state = entry.get("state")

        if state == "custom":
            plan.skipped_custom += 1
            continue

        if state == "exhausted":
            plan.skipped_exhausted += 1
            continue

        if state == "added" and entry.get("spotify_uri"):
            uri = entry["spotify_uri"]
            desired_uris.add(uri)

            if uri in playlist_uris:
                plan.skipped_synced += 1
            else:
                # In history but missing from playlist — recovery
                plan.to_recover.append({
                    "key": key,
                    "uri": uri,
                    "display": entry.get("display", key),
                })
            continue

        if state == "unmatched":
            attempts = entry.get("search_attempts", 0)
            if attempts >= MAX_SEARCH_ATTEMPTS:
                # Mark as exhausted — will be updated by caller
                plan.skipped_exhausted += 1
                continue
            # Retry search
            plan.to_search.append(track)
            continue

        # Unknown state — treat as needing search
        plan.to_search.append(track)

    # Tracks in playlist that are NOT in the desired set — should be removed.
    # "desired set" = all URIs from history-added tracks that are still in the XML library.
    # If a track was removed from XML, its URI won't be in desired_uris → removal candidate.
    # Also catches accidental additions.
    for uri in playlist_uris:
        if uri not in desired_uris:
            # Check if this URI belongs to ANY history entry (could be from a track
            # removed from XML but still in history)
            plan.to_remove.append(uri)

    logging.info(
        f"Reconciliation plan: search={len(plan.to_search)} add={len(plan.to_add)} "
        f"remove={len(plan.to_remove)} recover={len(plan.to_recover)} "
        f"synced={plan.skipped_synced} custom={plan.skipped_custom} "
        f"exhausted={plan.skipped_exhausted}"
    )

    return plan
