#!/bin/bash
cd /c/Users/David/GitHubRepos/SpotifyPlaylistGen
python scripts/diagnose.py --silent &
winpty python -m src.main
exec bash
