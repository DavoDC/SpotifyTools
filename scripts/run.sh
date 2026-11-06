#!/bin/bash
cd "$(dirname "$0")/../src"
python -m spotify_tools.diagnose --silent &
winpty python -m spotify_tools.main
exec bash
