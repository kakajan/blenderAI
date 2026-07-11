@echo off
setlocal
cd /d "%~dp0"
title BlenderAI Installer
where python >nul 2>nul
if errorlevel 1 (
  echo Python 3.11+ not found. Install from https://www.python.org/downloads/
  pause
  exit /b 1
)
python -m pip install -q -r requirements.txt
python install.py %*
if errorlevel 1 pause
endlocal
