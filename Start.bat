@echo off
cd /d "%~dp0"
if exist ".runtime\Scripts\python.exe" (
  ".runtime\Scripts\python.exe" start.py %*
) else (
  py -3 start.py %*
)
if errorlevel 1 pause
