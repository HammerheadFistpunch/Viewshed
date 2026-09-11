@echo off
setlocal
cd /d "%~dp0"
python dem_bulk_launcher.py
if errorlevel 1 (
    echo.
    echo DEM bulk downloader exited with an error.
)
echo.
pause
