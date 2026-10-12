@echo off
cd /d "%~dp0"
py -m pip install -r requirements.txt
if errorlevel 1 goto fail
echo Installation complete.
pause
exit /b 0
:fail
echo Installation failed. Check Python installation.
pause
exit /b 1
