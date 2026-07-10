@echo off
setlocal

cd /d "%~dp0"

echo ============================================================
echo RGC AI Broadcast Studio - Windows Setup
echo ============================================================
echo.

where py >nul 2>nul
if errorlevel 1 (
    echo Python launcher "py" was not found.
    echo Install Python 3.11 or newer from https://www.python.org/downloads/
    echo Make sure "Add python.exe to PATH" is checked during install.
    pause
    exit /b 1
)

if not exist ".venv\Scripts\python.exe" (
    echo Creating local Python environment...
    py -3.11 -m venv .venv
    if errorlevel 1 (
        echo Python 3.11 was not available. Trying default Python...
        py -m venv .venv
    )
)

if not exist ".venv\Scripts\python.exe" (
    echo Could not create .venv.
    pause
    exit /b 1
)

echo Installing RGC AI Broadcast Studio dependencies...
".venv\Scripts\python.exe" -m pip install --upgrade pip
".venv\Scripts\python.exe" -m pip install -e .
if errorlevel 1 (
    echo Install failed. Check the message above.
    pause
    exit /b 1
)

if not exist ".env" (
    if exist ".env.example" (
        copy ".env.example" ".env" >nul
        echo Created .env from .env.example.
    )
)

echo.
echo Setup complete.
echo Next: double-click launch_studio.bat, or run create_desktop_shortcut.ps1.
echo.
pause
