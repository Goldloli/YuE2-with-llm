@echo off
rem YuE2 Studio launcher for Windows — double-click this file to start.
cd /d "%~dp0"

if exist ".venv\Scripts\python.exe" (
  ".venv\Scripts\python.exe" tools\start.py
  goto :end
)

where py >nul 2>nul && py -3 -c "import sys; raise SystemExit(0 if sys.version_info >= (3, 10) else 1)" >nul 2>nul && py -3 tools\start.py && goto :end

where python >nul 2>nul && python -c "import sys; raise SystemExit(0 if sys.version_info >= (3, 10) else 1)" >nul 2>nul && python tools\start.py && goto :end

echo Python 3.10+ was not found.
echo Install it from https://www.python.org/downloads/ and run this file again.
pause

:end
