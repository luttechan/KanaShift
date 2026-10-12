@echo off
cd /d "%~dp0"
py app.py
echo.
echo KanaShift exited with code %errorlevel%.
pause
