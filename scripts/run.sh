#!/bin/bash
cd <home>/GitHubRepos/SpotifyTools
python -m spotify_tools.diagnose --silent &
winpty python -m spotify_tools.main
exec bash
