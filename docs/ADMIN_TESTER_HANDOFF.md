# Admin tester handoff

Use this when sending RGC AI Broadcast Studio to a league admin for a first test.

## What to send

Send the clean tester ZIP built from this repo. Do not send your working folder directly, because it can contain private keys, saved profiles, league files, local music paths, and recordings.

Build the ZIP with:

```powershell
cd "$HOME\Documents\RGC-AI-Broadcast-Studio-Test"
.\.venv\Scripts\python.exe tools\build_tester_zip.py
```

The ZIP will be created in:

```text
dist\
```

## What the admin needs

- Windows 10 or 11
- iRacing installed
- Python 3.11 or newer
- Their own OpenAI API key if testing full AI mode
- Their own ElevenLabs API key and voice IDs if testing spoken broadcast audio
- Streamlabs, OBS, or another program that supports browser sources

## First setup

1. Extract the ZIP somewhere simple, like `Documents\RGC-AI-Broadcast-Studio`.
2. Double-click `install_studio.bat`.
3. Wait for setup to finish.
4. The installer creates a desktop shortcut named `RGC AI Broadcast Studio`.
5. Fill in the launcher settings.
6. Click `Save Settings`.
7. Create a profile for their league or test session.

If the installer cannot create the desktop shortcut, the admin can still open the program with `launch_studio.bat`.

## Overlay setup

In the launcher, copy the Streamlabs / OBS browser-source link:

```text
http://127.0.0.1:8765/overlay
```

Add it as a browser source at `1920 x 1080`.

## Recommended first test

For the first run, use `Start Producer Assist` if they only want cameras, overlays, and live broadcast prompts.

Use `Start Broadcast` when they are ready to test OpenAI and ElevenLabs voices.

## Admin first-run checklist

Before race night, have the admin verify:

- iRacing is open and connected to a live, hosted, league, or AI session.
- The launcher Broadcast Health panel looks ready.
- OpenAI and ElevenLabs are either configured or intentionally turned off.
- The Streamlabs / OBS browser source is showing the overlay.
- Camera control works in a short test session.
- They can start and stop the broadcast from the launcher.
- A profile is saved for the league race.

## Private files intentionally not included

The tester ZIP excludes:

- `.env`
- `league/`
- `profiles/`
- `.venv/`
- `.runtime/`
- `recordings/`
- cache folders
- logs
- local audio files

That keeps your personal keys, league data, and local setup out of the tester package.
