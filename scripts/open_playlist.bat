@echo off
echo [%date% %time%] open_playlist start
echo.
cd /d C:\Users\David\GitHubRepos\SpotifyTools
python -m spotify_tools.open_playlist
echo.
echo [%date% %time%] open_playlist done
cmd /k
