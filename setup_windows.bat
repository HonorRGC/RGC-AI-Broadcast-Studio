@echo off
setlocal

cd /d "%~dp0"

echo ============================================================
echo RGC AI Broadcast Studio - Windows Setup
echo ============================================================
echo.

if not exist ".venv\Scripts\python.exe" (
    echo Creating local Python environment...
    call :try_create_venv
)

if not exist ".venv\Scripts\python.exe" (
    echo Could not create .venv.
    echo.
    echo Install Python 3.11 or newer from https://www.python.org/downloads/
    echo During install, check "Add python.exe to PATH".
    echo.
    echo If you installed Python with the Python launcher, you can also try:
    echo   py install 3.11
    echo.
    if not "%RGC_SETUP_NO_PAUSE%"=="1" pause
    exit /b 1
)

echo Installing RGC AI Broadcast Studio dependencies...
".venv\Scripts\python.exe" -m pip install --upgrade pip
".venv\Scripts\python.exe" -m pip install -e .
if errorlevel 1 (
    echo Install failed. Check the message above.
    if not "%RGC_SETUP_NO_PAUSE%"=="1" pause
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
if not "%RGC_SETUP_NO_PAUSE%"=="1" pause
exit /b 0

:try_create_venv
where py >nul 2>nul
if not errorlevel 1 (
    echo Trying Python launcher: py -3.11
    py -3.11 -m venv .venv >nul 2>nul
    if exist ".venv\Scripts\python.exe" (
        echo Created .venv with py -3.11.
        exit /b 0
    )

    echo Trying Python launcher: py -3
    py -3 -m venv .venv >nul 2>nul
    if exist ".venv\Scripts\python.exe" (
        echo Created .venv with py -3.
        exit /b 0
    )

    echo Trying Python launcher: py
    py -m venv .venv >nul 2>nul
    if exist ".venv\Scripts\python.exe" (
        echo Created .venv with py.
        exit /b 0
    )
)

where python >nul 2>nul
if not errorlevel 1 (
    echo Trying command: python
    python -m venv .venv >nul 2>nul
    if exist ".venv\Scripts\python.exe" (
        echo Created .venv with python.
        exit /b 0
    )
)

exit /b 1
