@echo off
title Reel Automate AI - Aesthetic Studio
cd /d "%~dp0"
if exist venv\Scripts\activate.bat (
    call venv\Scripts\activate.bat
    python dashboard.py
) else (
    python dashboard.py
)
pause
