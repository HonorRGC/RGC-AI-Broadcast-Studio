# Admin tester handoff

Use this when sending RGC AI Broadcast Studio to a league admin for a first test.

For the full step-by-step install, OpenAI, ElevenLabs, overlay, and profile setup tutorial, send them:

```text
docs\INSTALL_AND_SETUP_GUIDE.md
```

## What to send

Preferred: send the Windows Setup.exe from the `dist` folder after building the installer:

```text
dist\RGC-AI-Broadcast-Studio-Setup-0.19.0.exe
```

Fallback: send the clean tester ZIP built from this repo.

Do not send your working folder directly, because it can contain private keys, saved profiles, league files, local music paths, and recordings.

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
- Python 3.11 or newer for this early installer generation
- Their own OpenAI API key if testing full AI mode
- Their own ElevenLabs API key and voice IDs if testing spoken broadcast audio
- Streamlabs, OBS, or another program that supports browser sources

## First setup

1. Run the Setup.exe.
2. Wait for setup to finish.
3. The installer creates a desktop shortcut named `RGC AI Broadcast Studio`.
4. If using the fallback ZIP, extract it somewhere simple, like `Documents\RGC-AI-Broadcast-Studio`, then double-click `install_studio.bat`.
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

## Remote helper setup

If another trusted admin will help run Producer Assist from a different location, have both PCs install Tailscale:

```text
https://tailscale.com/download/windows
```

Both PCs must be signed into the same Tailscale network. In the Studio, set `Remote Producer Assist Access` to `0.0.0.0`, save settings, start the broadcast, then copy/send the Producer Assist Link.

The OBS/Streamlabs overlay should still use `http://127.0.0.1:8765/overlay` on the broadcast PC.

Race-control note: if iRacing chat/admin commands are sent from the broadcast PC, the chat box or iRacing window can interrupt the stream capture. For the cleanest league broadcast, have the trusted remote admin handle Race Control from their own PC through Producer Assist/Tailscale.

## Recommended first test

For the first run, use `Start Broadcast`. The overlay, Producer Assist control room, cameras, and replay controls launch together.

If they only want a human-broadcaster workflow, open Producer Assist and turn OpenAI and ElevenLabs off.

## Admin first-run checklist

Before race night, have the admin verify:

- iRacing is open and connected to a live, hosted, league, or AI session.
- The launcher Broadcast Health panel looks ready.
- OpenAI and ElevenLabs are either configured or intentionally turned off.
- The Streamlabs / OBS browser source is showing the overlay.
- Camera control works in a short test session.
- They can start and stop the broadcast from the launcher.
- A profile is saved for the league race.

Before sending a public-style build, also walk through:

```text
docs\V1_RELEASE_CHECKLIST.md
```

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
