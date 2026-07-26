# RGC AI Broadcast Studio tester quickstart

This is the fallback ZIP tester path. The preferred outside-tester path is the Windows `Setup.exe` described in
[WINDOWS_INSTALLER_BUILD.md](WINDOWS_INSTALLER_BUILD.md).

If you are preparing a ZIP for another league admin, see
[ADMIN_TESTER_HANDOFF.md](ADMIN_TESTER_HANDOFF.md). That path builds a clean
tester ZIP without private `.env`, `league`, or saved profile data.

For the full step-by-step install, OpenAI, ElevenLabs, overlay, and profile setup tutorial, see
[INSTALL_AND_SETUP_GUIDE.md](INSTALL_AND_SETUP_GUIDE.md).

## What testers need

- Windows 10 or 11
- iRacing installed for live broadcast testing
- Python 3.11 or newer from <https://www.python.org/downloads/>
  - During Python install, check **Add python.exe to PATH**
- Their own OpenAI and ElevenLabs keys if testing full AI voices

## Preferred tester install

If the broadcaster sends you a file named like this, use it first:

```text
RGC-AI-Broadcast-Studio-Setup-1.0.0.exe
```

Run the setup file, then open `RGC AI Broadcast Studio` from the desktop shortcut.

## Fallback: download from GitHub

1. Open the GitHub repository.
2. Click the green **Code** button.
3. Click **Download ZIP**.
4. Extract the ZIP somewhere easy, like:

   ```text
   Documents\RGC-AI-Broadcast-Studio
   ```

## First-time setup

1. Open the extracted folder.
2. Double-click:

   ```text
   install_studio.bat
   ```

3. Wait for setup to finish. This creates the local Python environment, installs the app, creates `.env`, adds a desktop shortcut, and opens the studio.

If you prefer the manual setup path, double-click:

   ```text
   setup_windows.bat
   ```

Then open the app with `launch_studio.bat`.

## Add a desktop icon

The installer normally creates the desktop shortcut automatically.

If you need to create it manually, right-click:

```text
create_desktop_shortcut.ps1
```

Choose **Run with PowerShell**.

This creates a desktop shortcut named:

```text
RGC AI Broadcast Studio
```

## Configure the program

In the launcher:

1. Add OpenAI and ElevenLabs keys if testing full AI broadcast mode.
2. Add voice IDs.
3. Add event title, sponsor, series name, and sponsor logos.
4. Click **Save Settings**.
5. Click **Create League Files** if testing league notes/stats.

## Start a test

- Use **Start Broadcast** for AI or human-broadcaster testing.
- Open Producer Assist to turn OpenAI, ElevenLabs, and auto cameras on or off while it is running.
- Use **Stop Broadcast** to stop a broadcast launched from the program.

## Remote helper with Tailscale

If a trusted admin will help from another location, use Tailscale:

<https://tailscale.com/download/windows>

Install and sign into Tailscale on both PCs, using the same Tailscale network. In RGC AI Broadcast Studio, set **Remote Producer Assist Access** to `0.0.0.0`, save settings, start the broadcast, then copy the **Producer Assist / Remote Admin Link** and send it to the helper.

Keep the OBS/Streamlabs overlay link on `127.0.0.1`; Tailscale is only for the private Producer Assist control room.

Race-control warning: sending iRacing admin commands from the broadcast PC can show the chat box or iRacing window on stream. For league races, the cleanest setup is a trusted remote admin using Producer Assist/Tailscale from another PC so race-control commands do not interrupt the broadcast capture.

## Optional SIMRacingApps car graphics

The broadcast works without SIMRacingApps, but live 3D car renders and styled car numbers require SIMRacingAppsServer to be running in the background.

1. Download SIMRacingAppsServer from <https://simracingapps.com/>.
2. Download the patched build from <https://github.com/ZoneXV/SIMRacingAppsServer/releases/tag/v1.22-paceCar-pitspeed-fix>.
3. Start SIMRacingAppsServer before starting the broadcast.
4. Leave SIMRacingAppsServer open or minimized while iRacing is running.
5. Refresh Broadcast Health. It should show `SIMRacingApps: Running`.

If SIMRacingApps is not running, car cards and leaderboards may fall back to plain numbers/manual graphics.

## Streamlabs / OBS overlay

In **Broadcast Settings**, the browser-source link is shown right after the overlay title, sponsor, series, and brand graphics fields. Click **Copy Overlay Link** and paste it into Streamlabs or OBS:

```text
http://127.0.0.1:8765/overlay
```

Recommended browser-source size:

```text
1920 x 1080
```

## Updating to a newer test build

For installer testers, run the newer Setup.exe when the broadcaster sends it.

For ZIP testers, the fallback method is:

1. Download the latest ZIP from GitHub.
2. Extract it to a new folder.
3. Run `setup_windows.bat` again.
4. Copy any private `.env` or `league\` files from the old test folder if needed.

Installer releases should not require repeating the ZIP extraction steps.
