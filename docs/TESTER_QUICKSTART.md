# RGC AI Broadcast Studio tester quickstart

This is the simple Windows tester path before the project has a full installer.

## What testers need

- Windows 10 or 11
- iRacing installed for live broadcast testing
- Python 3.11 or newer from <https://www.python.org/downloads/>
  - During Python install, check **Add python.exe to PATH**
- Their own OpenAI and ElevenLabs keys if testing full AI voices

## Download from GitHub

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
   setup_windows.bat
   ```

3. Wait for setup to finish.
4. Double-click:

   ```text
   launch_studio.bat
   ```

## Add a desktop icon

Right-click:

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

- Use **Start Broadcast** for the full AI broadcast.
- Use **Start Producer Assist** for overlays, cameras, and race information without AI voices.
- Use **Stop Broadcast** to stop a broadcast launched from the program.

## Streamlabs / OBS overlay

Add this as a browser source:

```text
http://127.0.0.1:8765/overlay
```

Recommended browser-source size:

```text
1920 x 1080
```

## Updating to a newer test build

For ZIP testers, the easiest early method is:

1. Download the latest ZIP from GitHub.
2. Extract it to a new folder.
3. Run `setup_windows.bat` again.
4. Copy any private `.env` or `league\` files from the old test folder if needed.

Later releases should use a real installer so testers do not need to repeat these steps.
