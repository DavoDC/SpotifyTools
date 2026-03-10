#!/bin/bash
cd /c/Users/David/GitHubRepos/SpotifyPlaylistGen
python scripts/diagnose.py --silent &
python -m src.main
exec bash
