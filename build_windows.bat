@echo off
cd /d "%~dp0"
py -m pip install -r requirements.txt pyinstaller
if errorlevel 1 goto fail
py -m PyInstaller --noconfirm --clean --onefile --windowed --name KanaShift app.py
if errorlevel 1 goto fail
echo EXE built: dist\KanaShift.exe
pause
exit /b 0
:fail
echo Build failed. Run build_windows.bat in Windows CMD.
pause
exit /b 1
