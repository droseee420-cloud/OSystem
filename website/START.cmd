@echo off
setlocal
cd /d "%~dp0"
title ObogrevSistem - Local website
set "SITE_PYTHON="
if exist "%~dp0runtime\python.exe" set "SITE_PYTHON=%~dp0runtime\python.exe"
if not defined SITE_PYTHON if exist "%USERPROFILE%\.cache\codex-runtimes\codex-primary-runtime\dependencies\python\python.exe" set "SITE_PYTHON=%USERPROFILE%\.cache\codex-runtimes\codex-primary-runtime\dependencies\python\python.exe"
if defined SITE_PYTHON goto run
where python >nul 2>nul
if not errorlevel 1 (
  python --version >nul 2>nul
  if not errorlevel 1 set "SITE_PYTHON=python"
)
if defined SITE_PYTHON goto run
echo Python 3.11 or newer is required. Install from https://www.python.org/downloads/
echo Then open START.cmd again. No other packages are required for local preview.
pause
exit /b 1
:run
echo Starting local website. Keep this window open. Press Ctrl+C to stop.
"%SITE_PYTHON%" server.py --open
if errorlevel 1 (
 echo The server could not start. Check the message above.
 echo If port 8766 is busy, close the previous website window or change PORT and SITE_URL in .env.
 pause
)
