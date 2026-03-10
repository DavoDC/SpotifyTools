#!/bin/bash
cd <home>/GitHubRepos/SpotifyTools
python scripts/diagnose.py --silent &
python -m src.main
exec bash
