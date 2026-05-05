@echo off
echo [%date% %time%] open_playlist start
echo.
cd /d C:\Users\David\GitHubRepos\SpotifyPlaylistGen
python src\open_playlist.py
echo.
echo [%date% %time%] open_playlist done
cmd /k
