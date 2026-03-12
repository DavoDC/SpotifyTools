"""Safe persistent history system with atomic writes and corruption recovery.

History format (v2):
{
    "version": 2,
    "tracks": {
        "Artist|Title": {
            "state": "added" | "unmatched" | "custom" | "exhausted",
            "display": "Artist — Title",
            "spotify_uri": "spotify:track:xxx" | null,
            "spotify_id": "xxx" | null,
            "match_confidence": "exact" | "high" | null,
            "search_attempts": 1,
            "first_seen": "ISO timestamp",
            "last_updated": "ISO timestamp",
            "source_file": "filename.xml" | null
        }
    }
}
"""

import json
import logging
import os
import shutil
from datetime import datetime

CURRENT_VERSION = 2


class HistoryStore:
    """Thread-safe history manager with atomic writes and backup recovery."""

    def __init__(self, path: str):
        self.path = path
        self._backup_path = path + ".bak"
        self._temp_path = path + ".tmp"

    def load(self) -> dict:
        """Load history with fallback to backup on corruption."""
        data = self._try_load(self.path)
        if data is None:
            data = self._try_load(self._backup_path)
            if data is not None:
                logging.warning("Primary history corrupt/missing, loaded backup")
            else:
                logging.info("No history found, starting fresh")
                return {"version": CURRENT_VERSION, "tracks": {}}

        # Migrate v1 → v2 if needed
        if "version" not in data:
            data = self._migrate_v1(data)

        return data

    def save(self, history: dict):
        """Atomic save: write to temp, validate, rename."""
        os.makedirs(os.path.dirname(self.path) or ".", exist_ok=True)

        # Write to temp file
        raw = json.dumps(history, indent=2, ensure_ascii=False)

        # Validate JSON is well-formed before writing
        json.loads(raw)

        with open(self._temp_path, "w", encoding="utf-8") as f:
            f.write(raw)
            f.flush()
            os.fsync(f.fileno())

        # Atomic rename
        os.replace(self._temp_path, self.path)

    def create_backup(self):
        """Copy current history to .bak before a run. Call once at start."""
        if os.path.exists(self.path):
            shutil.copy2(self.path, self._backup_path)
            logging.info(f"History backup created: {self._backup_path}")

    def get(self, key: str) -> dict | None:
        """Get a single track entry. Convenience for reconciler."""
        # Note: caller should load() once and work with the dict directly.
        # This is for one-off lookups only.
        raise NotImplementedError("Use load() and access tracks dict directly")

    def set_track(self, history: dict, key: str, *,
                  state: str,
                  display: str,
                  spotify_uri: str | None = None,
                  match_confidence: str | None = None,
                  source_file: str | None = None):
        """Update or create a track entry with proper field management."""
        tracks = history.setdefault("tracks", {})
        now = datetime.now().isoformat()

        existing = tracks.get(key, {})
        prev_attempts = existing.get("search_attempts", 0)

        spotify_id = None
        if spotify_uri:
            spotify_id = spotify_uri.split(":")[-1]

        tracks[key] = {
            "state": state,
            "display": display,
            "spotify_uri": spotify_uri,
            "spotify_id": spotify_id,
            "match_confidence": match_confidence,
            "search_attempts": prev_attempts + (1 if state in ("unmatched", "added", "exhausted") else 0),
            "first_seen": existing.get("first_seen", now),
            "last_updated": now,
            "source_file": source_file or existing.get("source_file"),
        }

    def _try_load(self, path: str) -> dict | None:
        """Try to load and parse JSON from path. Returns None on failure."""
        if not os.path.exists(path):
            return None
        try:
            with open(path, "r", encoding="utf-8") as f:
                data = json.load(f)
            if not isinstance(data, dict):
                logging.warning(f"History file is not a dict: {path}")
                return None
            return data
        except (json.JSONDecodeError, OSError) as e:
            logging.warning(f"Failed to load {path}: {e}")
            return None

    def _migrate_v1(self, old_data: dict) -> dict:
        """Migrate v1 flat format to v2 nested format.

        v1: {"Artist|Title": {"state": ..., "track": ..., "spotify_uri": ..., "decided_at": ...}}
        v2: {"version": 2, "tracks": {"Artist|Title": {full schema}}}
        """
        logging.info(f"Migrating history from v1 to v2 ({len(old_data)} entries)")
        tracks = {}

        for key, entry in old_data.items():
            if not isinstance(entry, dict):
                continue

            decided_at = entry.get("decided_at", datetime.now().isoformat())
            spotify_uri = entry.get("spotify_uri")
            spotify_id = spotify_uri.split(":")[-1] if spotify_uri else None
            state = entry.get("state", "unmatched")

            tracks[key] = {
                "state": state,
                "display": entry.get("track", key.replace("|", " — ")),
                "spotify_uri": spotify_uri,
                "spotify_id": spotify_id,
                "match_confidence": None,  # unknown for migrated entries
                "search_attempts": 1,
                "first_seen": decided_at,
                "last_updated": decided_at,
                "source_file": None,
            }

        migrated = {"version": CURRENT_VERSION, "tracks": tracks}
        logging.info(f"Migration complete: {len(tracks)} tracks migrated")
        return migrated
