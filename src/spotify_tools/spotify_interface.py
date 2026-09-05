"""Abstract interface for Spotify API access.

All playlist operations go through this interface. Two implementations:
- RealSpotifyClient: wraps spotipy for live API access
- SimulatedSpotifyClient: deterministic mock for testing and --simulate mode
"""

from abc import ABC, abstractmethod
from dataclasses import dataclass, field


@dataclass
class AddResult:
    """Result of a batch add operation."""
    succeeded: list[str] = field(default_factory=list)
    failed: list[str] = field(default_factory=list)


@dataclass
class RemoveResult:
    """Result of a batch remove operation."""
    removed_count: int = 0
    failed: bool = False


class SpotifyInterface(ABC):
    """Abstract interface for all Spotify operations.

    No module except implementations of this interface may call the Spotify API directly.
    """

    @abstractmethod
    def search_track(self, track: dict) -> list[dict]:
        """Search Spotify for a track. Returns scored results sorted best-first.

        Each result dict has keys: spotify_id, name, artist, album, confidence, uri
        """
        ...

    @abstractmethod
    def get_playlist_uris(self, playlist_id: str) -> set[str]:
        """Read all track URIs from a playlist.

        Returns set of spotify URIs (e.g. {"spotify:track:abc", ...}).
        Raises RuntimeError if API reports non-zero total but we read 0 URIs.
        """
        ...

    @abstractmethod
    def add_tracks(self, playlist_id: str, uris: list[str]) -> AddResult:
        """Add tracks to playlist in batches. Returns result with success/failure info."""
        ...

    @abstractmethod
    def remove_tracks(self, playlist_id: str, uris: list[str]) -> RemoveResult:
        """Remove tracks from playlist in batches."""
        ...

    @abstractmethod
    def find_duplicates(self, playlist_id: str) -> dict[str, int]:
        """Find duplicate URIs in playlist. Returns {uri: extra_count}."""
        ...

    @abstractmethod
    def current_user(self) -> dict:
        """Return current authenticated user info."""
        ...

    @abstractmethod
    def get_liked_track_uris(self) -> set[str]:
        """Read all track URIs from the current user's Liked Songs."""
        ...

    @abstractmethod
    def remove_liked_tracks(self, uris: list[str]) -> RemoveResult:
        """Remove tracks from the current user's Liked Songs, in batches."""
        ...

    @abstractmethod
    def get_or_create_playlist(self, name: str) -> str:
        """Return the id of the current user's playlist with this name,
        creating a new private playlist if none exists yet."""
        ...

    # ---------------------------------------------------------------- read/browse
    #
    # These four are the read side consumed by AudioManager's Acquire tab.
    # They lived on RealSpotifyClient only until 2026-09-05, which meant a
    # caller holding a SpotifyInterface was really depending on the concrete
    # class and could not be run against the simulator. Any new method that
    # a consumer calls belongs HERE, on the ABC, with a simulator
    # implementation alongside it - the class docstring's "no module except
    # implementations of this interface may call the Spotify API directly"
    # is only true if the interface actually declares everything they call.

    @abstractmethod
    def get_playlist_tracks(self, playlist_id: str) -> list[tuple[str, str]]:
        """Return (artist, title) for every track in a playlist."""
        ...

    @abstractmethod
    def get_playlist_name(self, playlist_id: str) -> str:
        """Return a playlist's display name (empty string if unknown)."""
        ...

    @abstractmethod
    def get_playlist_tracks_detailed(self, playlist_id: str) -> list[dict]:
        """Return {artist, title, album, year, duration_ms} per playlist track."""
        ...

    @abstractmethod
    def get_liked_tracks_detailed(self, limit: int | None = None) -> list[dict]:
        """Return {artist, title, album, year, duration_ms} for Liked Songs,
        most-recently-added first. limit caps the read (and the pagination)."""
        ...
