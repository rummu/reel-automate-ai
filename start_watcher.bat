@echo off
title Reel Automate AI - Background Drive Watcher
cd /d "%~dp0"
echo Starting Background Google Drive Watcher...
echo Watches your Google Drive input folder and automatically generates reels for days with 30+ items.
if exist venv\Scripts\activate.bat (
    call venv\Scripts\activate.bat
    python drive_watcher.py --watch
) else (
    python drive_watcher.py --watch
)
pause
