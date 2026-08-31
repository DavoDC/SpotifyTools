"""Simulated Spotify client for deterministic testing.

Implements SpotifyInterface using in-memory playlist state and JSON fixture responses.
Used by --simulate CLI flag and all golden path tests.
"""

import json
import logging
from typing import Optional

from src.spotify_interface import SpotifyInterface, AddResult, RemoveResult


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
        "error_scenarios": {
            "Artist|ErrorTrack": "timeout"
        }
    }
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
