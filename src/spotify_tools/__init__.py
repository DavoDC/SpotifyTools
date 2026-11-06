"""SpotifyTools public surface.

Consumers must import only: API_VERSION, build_client, and the public names
in config (CONFIG_PATH, load_config), matcher, open_playlist
(extract_playlist_id, build_search_url), acquire and spotify_simulator.
"""

API_VERSION = 1

# The names a consumer may import. README.md and CLAUDE.md must list the same names.
PUBLIC_API = (
    "API_VERSION",
    "build_client",
    "CONFIG_PATH",
    "load_config",
    "clean_artist",
    "clean_title",
    "normalise",
    "score_match",
    "primary_artist",
    "title_key",
    "content_key",
    "extract_playlist_id",
    "build_search_url",
)


def build_client(config=None):
    """Return an authenticated RealSpotifyClient.

    config=None loads the default config file (config.CONFIG_PATH).
    Imports are lazy so importing the package stays cheap and offline.
    """
    from spotify_tools import config as _config_module
    from spotify_tools import spotify_client as _client_module

    if config is None:
        config = _config_module.load_config()
    return _client_module.RealSpotifyClient(config)
