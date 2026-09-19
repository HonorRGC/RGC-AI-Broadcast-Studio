@echo off
setlocal

cd /d "%~dp0"

echo ============================================================
echo RGC AI Broadcast Studio - Installer
echo ============================================================
echo.
echo This will set up the app, create a desktop shortcut, and open the studio.
echo.

set RGC_SETUP_NO_PAUSE=1
call "%~dp0setup_windows.bat"
if errorlevel 1 (
    echo.
    echo Install failed. Check the message above.
    echo.
    pause
    exit /b 1
)

echo.
echo Creating desktop shortcut...
powershell -NoProfile -ExecutionPolicy Bypass -File "%~dp0create_desktop_shortcut.ps1"
if errorlevel 1 (
    echo.
    echo The app was installed, but the desktop shortcut could not be created.
    echo You can still open the studio with launch_studio.bat.
    echo.
) else (
    echo.
    echo Desktop shortcut created.
)

echo.
echo Opening RGC AI Broadcast Studio...
call "%~dp0launch_studio.bat"

echo.
echo Install complete.
echo You can now use the desktop icon named RGC AI Broadcast Studio.
echo.
pause
