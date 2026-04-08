@echo off
REM ─────────────────────────────────────────────────────────────────────────
REM  run_viewshed.bat  —  Double-click launcher for aprs_viewshed_utah_parallel.py
REM
REM  Guarantees:
REM    1. Working directory = this folder (so all relative paths work)
REM    2. Uses python.exe (not pythonw.exe) so you get a real console window
REM    3. Window stays open after finish or crash so you can read the output
REM ─────────────────────────────────────────────────────────────────────────

REM Change to the folder this .bat lives in
cd /d "%~dp0"

REM Try to find python.exe on PATH, then common install locations
where python >nul 2>&1
if %errorlevel% == 0 (
    python aprs_viewshed_utah_parallel.py
    goto done
)

REM Fallback to common Python install paths
if exist "C:\Python312\python.exe" (
    "C:\Python312\python.exe" aprs_viewshed_utah_parallel.py
    goto done
)
if exist "C:\Python311\python.exe" (
    "C:\Python311\python.exe" aprs_viewshed_utah_parallel.py
    goto done
)
if exist "%LOCALAPPDATA%\Programs\Python\Python312\python.exe" (
    "%LOCALAPPDATA%\Programs\Python\Python312\python.exe" aprs_viewshed_utah_parallel.py
    goto done
)
if exist "%LOCALAPPDATA%\Programs\Python\Python311\python.exe" (
    "%LOCALAPPDATA%\Programs\Python\Python311\python.exe" aprs_viewshed_utah_parallel.py
    goto done
)

echo.
echo  ERROR: python.exe not found.
echo  Please install Python from https://www.python.org/downloads/
echo  and make sure to check "Add Python to PATH" during installation.
echo.

:done
pause
