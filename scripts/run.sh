#!/bin/bash
cd <home>/GitHubRepos/SpotifyTools
python src/diagnose.py --silent &
winpty python -m src.main
exec bash
