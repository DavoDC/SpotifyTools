"""Simulated Spotify client for deterministic testing.

Implements SpotifyInterface using in-memory playlist state and JSON fixture responses.
Used by --simulate CLI flag and all golden path tests.
"""

import json
import logging
from typing import Optional

from spotify_tools.spotify_interface import SpotifyInterface, AddResult, RemoveResult


class SimulatedSpotifyClient(SpotifyInterface):
    """Deterministic Spotify simulator that loads responses from fixtures.

    The simulator maintains an in-memory playlist (set of URIs) and returns
    pre-configured search responses from a fixture file.

    Fixture format (spotify_responses.json):
    {
        "search_responses": {
            "Artist|Title": [
                {
                    "spotify_id": "abc123",
                    "name": "Song Name",
                    "artist": "Artist Name",
                    "album": "Album Name",
                    "confidence": "exact",
                    "uri": "spotify:track:abc123"
                }
            ]
        },
        "initial_playlist": ["spotify:track:existing1"],
        "initial_liked": ["spotify:track:liked1"],
        "initial_playlists": {"AudioManager Inbox": "pl_existing"},
        "playlist_names": {"pl_existing": "AudioManager Inbox"},
        "track_details": {
            "spotify:track:existing1": {
                "artist": "Artist Name", "title": "Song Name",
                "album": "Album Name", "year": "2020", "duration_ms": 210000
            }
        },
        "error_scenarios": {
            "Artist|ErrorTrack": "timeout"
        }
    }

    track_details is optional: any URI without an entry gets an obviously
    synthetic row derived from the URI itself (see _detail_row_for).
    """

    def __init__(self, fixture_path: Optional[str] = None, fixture_data: Optional[dict] = None):
        """Initialize with either a fixture file path or inline fixture data."""
        if fixture_data is not None:
            self._fixture = fixture_data
        elif fixture_path is not None:
            with open(fixture_path, "r", encoding="utf-8") as f:
                self._fixture = json.load(f)
        else:
            self._fixture = {"search_responses": {}, "initial_playlist": []}

        # In-memory playlist state
        self._playlist: list[str] = list(self._fixture.get("initial_playlist", []))

        # In-memory liked-songs + named-playlist state (Acquire flow)
        self._liked: list[str] = list(self._fixture.get("initial_liked", []))
        self._playlists: dict[str, str] = dict(self._fixture.get("initial_playlists", {}))

        # Operation log for assertions in tests
        self.operations: list[dict] = []

    @property
    def playlist_contents(self) -> list[str]:
        """Current playlist contents (for test assertions)."""
        return list(self._playlist)

    @property
    def add_count(self) -> int:
        """Number of add operations performed."""
        return sum(1 for op in self.operations if op["type"] == "add")

    @property
    def remove_count(self) -> int:
        """Number of remove operations performed."""
        return sum(1 for op in self.operations if op["type"] == "remove")

    def current_user(self) -> dict:
        return {"display_name": "Test User", "id": "testuser123"}

    def search_track(self, track: dict) -> list[dict]:
        key = f"{track['primary_artist']}|{track['title']}"

        # Check for error simulation
        errors = self._fixture.get("error_scenarios", {})
        if key in errors:
            error_type = errors[key]
            if error_type == "timeout":
                raise RuntimeError(f"Simulated timeout for {key}")
            elif error_type == "rate_limit":
                raise RuntimeError(f"Simulated rate limit for {key}")
            elif error_type == "empty":
                return []

        responses = self._fixture.get("search_responses", {})
        results = responses.get(key, [])

        self.operations.append({"type": "search", "key": key, "results": len(results)})
        logging.info(f"[SIM] search_track({key}) -> {len(results)} results")
        return results

    def get_playlist_uris(self, playlist_id: str) -> set[str]:
        uris = set(self._playlist)
        self.operations.append({"type": "get_playlist", "count": len(uris)})
        logging.info(f"[SIM] get_playlist_uris() -> {len(uris)} URIs")
        return uris

    def add_tracks(self, playlist_id: str, uris: list[str]) -> AddResult:
        if not uris:
            return AddResult()

        for uri in uris:
            if uri not in self._playlist:
                self._playlist.append(uri)

        self.operations.append({"type": "add", "uris": list(uris), "count": len(uris)})
        logging.info(f"[SIM] add_tracks({len(uris)} URIs)")
        return AddResult(succeeded=list(uris), failed=[])

    def remove_tracks(self, playlist_id: str, uris: list[str]) -> RemoveResult:
        if not uris:
            return RemoveResult()

        removed = 0
        for uri in uris:
            if uri in self._playlist:
                self._playlist.remove(uri)
                removed += 1

        self.operations.append({"type": "remove", "uris": list(uris), "count": removed})
        logging.info(f"[SIM] remove_tracks({len(uris)} URIs, removed={removed})")
        return RemoveResult(removed_count=removed)

    def get_liked_track_uris(self) -> set[str]:
        uris = set(self._liked)
        self.operations.append({"type": "get_liked", "count": len(uris)})
        logging.info(f"[SIM] get_liked_track_uris() -> {len(uris)} URIs")
        return uris

    def remove_liked_tracks(self, uris: list[str]) -> RemoveResult:
        if not uris:
            return RemoveResult()

        removed = 0
        for uri in uris:
            if uri in self._liked:
                self._liked.remove(uri)
                removed += 1

        self.operations.append({"type": "remove_liked", "uris": list(uris), "count": removed})
        logging.info(f"[SIM] remove_liked_tracks({len(uris)} URIs, removed={removed})")
        return RemoveResult(removed_count=removed)

    def get_or_create_playlist(self, name: str) -> str:
        if name in self._playlists:
            self.operations.append({"type": "get_playlist_by_name", "name": name, "created": False})
            return self._playlists[name]

        playlist_id = f"sim_playlist_{len(self._playlists) + 1}"
        self._playlists[name] = playlist_id
        self.operations.append({"type": "get_playlist_by_name", "name": name, "created": True})
        logging.info(f"[SIM] get_or_create_playlist({name}) -> created {playlist_id}")
        return playlist_id

    # ---------------------------------------------------------------- read/browse
    #
    # Counterparts of RealSpotifyClient's read methods, so a consumer holding
    # a SpotifyInterface (AudioManager's Acquire tab) can run against the
    # simulator instead of a live account. Rows are derived from the in-memory
    # URI state so add_tracks/remove_tracks are reflected here too, and every
    # value is unmistakably synthetic ("Simulated Artist aaa") - nothing here
    # should ever be mistaken for real Spotify data in a screenshot or a log.
    # A fixture may override any row via "track_details": {uri: {...}}.

    def _detail_row_for(self, uri: str) -> dict:
        override = (self._fixture.get("track_details") or {}).get(uri)
        if override:
            return dict(override)
        suffix = uri.rsplit(":", 1)[-1] or "unknown"
        return {
            "artist": f"Simulated Artist {suffix}",
            "title": f"Simulated Track {suffix}",
            "album": f"Simulated Album {suffix}",
            "year": "2000",
            "duration_ms": 210000,
        }

    def get_playlist_tracks(self, playlist_id: str) -> list[tuple[str, str]]:
        rows = self.get_playlist_tracks_detailed(playlist_id)
        return [(r["artist"], r["title"]) for r in rows]

    def get_playlist_name(self, playlist_id: str) -> str:
        names = self._fixture.get("playlist_names") or {}
        if playlist_id in names:
            name = names[playlist_id]
        else:
            # get_or_create_playlist() records name -> id; reverse it so a
            # playlist the simulator itself created reports the name it was
            # created under.
            created = {pid: pname for pname, pid in self._playlists.items()}
            name = created.get(playlist_id, f"Simulated Playlist {playlist_id}")
        self.operations.append({"type": "get_playlist_name", "playlist_id": playlist_id, "name": name})
        logging.info(f"[SIM] get_playlist_name({playlist_id}) -> {name}")
        return name

    def get_playlist_tracks_detailed(self, playlist_id: str) -> list[dict]:
        rows = [self._detail_row_for(uri) for uri in self._playlist]
        self.operations.append({"type": "get_playlist_detailed", "count": len(rows)})
        logging.info(f"[SIM] get_playlist_tracks_detailed({playlist_id}) -> {len(rows)} rows")
        return rows

    def get_liked_tracks_detailed(self, limit: int | None = None) -> list[dict]:
        uris = self._liked if limit is None else self._liked[:max(limit, 0)]
        rows = [self._detail_row_for(uri) for uri in uris]
        self.operations.append({"type": "get_liked_detailed", "count": len(rows)})
        logging.info(f"[SIM] get_liked_tracks_detailed(limit={limit}) -> {len(rows)} rows")
        return rows

    def find_duplicates(self, playlist_id: str) -> dict[str, int]:
        seen: set[str] = set()
        dupes: dict[str, int] = {}
        for uri in self._playlist:
            if uri in seen:
                dupes[uri] = dupes.get(uri, 0) + 1
            else:
                seen.add(uri)

        self.operations.append({"type": "find_duplicates", "dupes": len(dupes)})
        return dupes
