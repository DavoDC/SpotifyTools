@echo off
for %%I in ("%~dp0..") do set "REPO=%%~fI"
wt.exe -p "Git Bash" -d "%REPO%" "C:\Program Files\Git\bin\bash.exe" --login -i "%REPO:\=/%/scripts/run.sh"
