"""Stage 2A (Acquiring) orchestration: move Liked Songs into an inbox playlist.

Pure orchestration over SpotifyInterface - no network/API code of its own.
Used by AudioManager's GUI "Acquire" tab and available for CLI/test use here.
"""

from dataclasses import dataclass, field

from spotify_tools.spotify_interface import SpotifyInterface

INBOX_PLAYLIST_NAME = "AudioManager Inbox"


@dataclass
class AcquireResult:
    playlist_id: str
    playlist_name: str
    moved_count: int = 0
    errors: list[str] = field(default_factory=list)


def move_liked_to_playlist(client: SpotifyInterface, playlist_name: str = INBOX_PLAYLIST_NAME) -> AcquireResult:
    """Add every Liked Songs track to `playlist_name` (creating it if needed),
    then clear only the tracks that were confirmed added. A track that fails
    to add is left in Liked Songs rather than risk losing it."""
    playlist_id = client.get_or_create_playlist(playlist_name)

    liked = client.get_liked_track_uris()
    if not liked:
        return AcquireResult(playlist_id=playlist_id, playlist_name=playlist_name)

    add_result = client.add_tracks(playlist_id, list(liked))
    errors = [f"failed to add {uri}" for uri in add_result.failed]

    remove_result = client.remove_liked_tracks(add_result.succeeded)
    if remove_result.failed:
        errors.append("remove_liked_tracks reported a batch failure - some tracks may remain in Liked Songs")

    return AcquireResult(
        playlist_id=playlist_id,
        playlist_name=playlist_name,
        moved_count=remove_result.removed_count,
        errors=errors,
    )
