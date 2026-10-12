@echo off
cd /d "%~dp0"
pyw app.py
if errorlevel 1 goto fail
exit /b 0
:fail
echo KanaShift could not start. Run debug.bat for details.
pause
exit /b 1
