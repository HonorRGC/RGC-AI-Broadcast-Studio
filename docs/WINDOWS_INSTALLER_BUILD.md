# Windows installer build guide

This guide is for building a more professional Windows installer for RGC AI Broadcast Studio.

The installer path is separate from broadcast development. Building the installer should not change the race commentary, camera logic, overlay behavior, or caution handling.

## What this creates

The goal is a normal Windows setup file:

```text
RGC-AI-Broadcast-Studio-Setup-0.18.0.exe
```

The setup file installs the studio into the user profile:

```text
%LOCALAPPDATA%\RGC AI Broadcast Studio
```

It also creates:

- a Start Menu shortcut
- a Desktop shortcut
- a branded RGC desktop icon
- a Windows uninstall entry

On first setup, it runs the same Python dependency setup that the current tester package uses. The installed app still needs a local Python 3.11-or-newer runtime available on the user's PC for this early installer version.

## Required installer tool

Install Inno Setup:

<https://jrsoftware.org/isinfo.php>

Inno Setup is the tool that turns the clean app folder into a Windows `Setup.exe`.

The build script checks the common Inno Setup 7 and Inno Setup 6 install folders automatically. If your install is somewhere else, pass the compiler path manually:

```powershell
.\.venv\Scripts\python.exe tools\build_windows_setup.py --inno-path "C:\Program Files (x86)\Inno Setup 7\ISCC.exe"
```

## Build command

From the project folder:

```powershell
.\.venv\Scripts\python.exe tools\build_windows_setup.py
```

The script does two things:

1. Prepares a clean installer source folder:

   ```text
   dist\windows_installer_source
   ```

2. If Inno Setup is installed, builds:

   ```text
   dist\RGC-AI-Broadcast-Studio-Setup-0.18.0.exe
   ```

If Inno Setup is not installed, the script still prepares the clean installer source and tells you what to install next.

## What is excluded

The installer source excludes private/local files:

- `.env`
- `league/`
- `profiles/`
- `.venv/`
- `.runtime/`
- recordings
- cache folders
- logs
- local audio files

That means your personal keys, league data, profiles, and recordings should not be packaged into the installer.

## What to test after building an installer

You do not need to run a full race just because the installer changed.

Do this smoke test:

1. Install the setup file.
2. Open RGC AI Broadcast Studio from the desktop shortcut.
3. Confirm the launcher opens.
4. Save settings.
5. Save and load a profile.
6. Start Producer Assist or Start Broadcast.
7. Confirm the overlay URL opens:

   ```text
   http://127.0.0.1:8765/overlay
   ```

8. Stop the broadcast from the launcher.
9. Uninstall from Windows Settings if testing uninstall.

Run a full race test only when broadcast logic changes.

## Future professional steps

Before selling this as purchasable software, the likely next steps are:

- move user settings fully into AppData
- add a real auto-updater
- sign the installer with a code-signing certificate
- add versioned release notes
- add license/account activation
- add crash/error reporting
- build a cleaner onboarding wizard
