#!/bin/bash
cd /c/Users/David/GitHubRepos/SpotifyPlaylistGen
python src/diagnose.py --silent &
winpty python -m spotify_tools.main
exec bash
