@echo off
"%~dp0.venv\Scripts\python.exe" "%~dp0launch_cyrene.py"
if errorlevel 1 pause
