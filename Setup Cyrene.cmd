@echo off
setlocal
cd /d "%~dp0"
uv run --no-project --python 3.12 scripts/setup_windows.py
if errorlevel 1 pause
