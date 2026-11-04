@echo off
cd /d "%~dp0"
if exist ".runtime\Scripts\python.exe" (
  ".runtime\Scripts\python.exe" start.py --update
) else (
  py -3 start.py --update
)
pause
