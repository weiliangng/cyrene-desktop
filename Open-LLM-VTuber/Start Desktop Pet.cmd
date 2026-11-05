@echo off
setlocal
set ELECTRON_RUN_AS_NODE=
"%~dp0.venv\Scripts\python.exe" "%~dp0launch_cyrene.py" --no-browser
if errorlevel 1 (
  pause
  exit /b 1
)
start "" "%~dp0..\Open-LLM-VTuber-Web\release\control\win-unpacked\Cyrene Desktop.exe"
echo Cyrene starts in pet mode. Hover to wake her; she sleeps after five idle seconds.
