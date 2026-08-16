@echo off
setlocal
cd /d "%~dp0"

REM Development launcher. End users should normally run Viewshed.exe.
where python >nul 2>&1
if errorlevel 1 (
    echo.
    echo Python was not found on PATH.
    echo Download the packaged Viewshed.exe build from the GitHub Actions artifact,
    echo or install Python 3.12 for development use.
    echo.
    pause
    exit /b 1
)

python viewshed_app.py
if errorlevel 1 pause
