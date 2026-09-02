#!/bin/bash
cd <home>/GitHubRepos/SpotifyTools
python src/diagnose.py --silent &
winpty python -m spotify_tools.main
exec bash
