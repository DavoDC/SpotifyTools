#!/bin/bash
cd /c/Users/David/GitHubRepos/SpotifyTools/src
python -m spotify_tools.diagnose --silent &
winpty python -m spotify_tools.main
exec bash
