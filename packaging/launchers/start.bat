@echo off
rem YuE2 Studio launcher (Windows). Double-click this file to start.
rem
rem The self-contained package ships its own Python runtime and dependencies, so
rem no install step and no network access are needed (models are downloaded later
rem from the in-app Models page).
cd /d "%~dp0"

if exist "runtime\python.exe" if exist "envs\web" (
  "runtime\python.exe" tools\start.py --bundled %*
  goto :end
)

if exist ".venv\Scripts\python.exe" (
  ".venv\Scripts\python.exe" tools\start.py %*
  goto :end
)

where py >nul 2>nul && py -3 -c "import sys; raise SystemExit(0 if sys.version_info >= (3, 10) else 1)" >nul 2>nul && py -3 tools\start.py %* && goto :end

where python >nul 2>nul && python -c "import sys; raise SystemExit(0 if sys.version_info >= (3, 10) else 1)" >nul 2>nul && python tools\start.py %* && goto :end

echo Python 3.10+ was not found.
echo Install it from https://www.python.org/downloads/ and run this file again.
pause

:end
