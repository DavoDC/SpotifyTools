#!/bin/bash
cd <home>/GitHubRepos/SpotifyTools
python scripts/diagnose.py --silent &
winpty python -m src.main
exec bash
