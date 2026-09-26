@echo off
setlocal

cd /d "%~dp0"

if not exist ".venv\Scripts\python.exe" (
    echo RGC AI Broadcast Studio is not set up yet.
    echo Run setup_windows.bat first.
    echo.
    pause
    exit /b 1
)

if exist "launch_studio.vbs" (
    start "" wscript.exe "%~dp0launch_studio.vbs"
) else (
    start "RGC AI Broadcast Studio" ".venv\Scripts\pythonw.exe" "studio_launcher.py"
)
exit /b 0
