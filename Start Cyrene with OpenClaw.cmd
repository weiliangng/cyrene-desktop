@echo off
"%~dp0Open-LLM-VTuber\.venv\Scripts\python.exe" "%~dp0scripts\setup_openclaw.py" start --connect
if errorlevel 1 (pause & exit /b 1)
call "%~dp0Start Cyrene Desktop.cmd"
