# v1.0 release checklist

Use this checklist before sending a new installer to a league admin or calling a build ready for public testing.

## Build readiness

- Version number updated in `pyproject.toml`.
- `CHANGELOG.md` has release notes for the build.
- `docs/PROJECT_STATE.md` matches the actual current feature set.
- No personal `.env`, `league/`, `profiles/`, recordings, logs, or local audio files are included.
- Full automated test suite passes.
- Windows installer builds successfully with Inno Setup.

## Studio smoke test

1. Install the Setup.exe on a clean or secondary folder.
2. Open RGC AI Broadcast Studio from the desktop shortcut.
3. Confirm the app version shown in the title is correct.
4. Save settings.
5. Create, save, load, and switch profiles.
6. Add sponsor graphics and confirm the overlay can load them.
7. Copy the OBS/Streamlabs overlay link.
8. Start Broadcast.
9. Open Producer Assist.
10. Toggle OpenAI, ElevenLabs, and auto cameras from Producer Assist.
11. Stop Broadcast.
12. Start Broadcast again without closing the Studio.

## Overlay smoke test

- Title banner appears.
- Sponsor logos appear in the upper-left title area.
- Leaderboard style matches the selected setting.
- Practice/Qualifying session text and timer show when applicable.
- Caution/green state indicator changes.
- Driver card appears when a driver is focused.
- Crank It Up graphic appears during a test or live trigger.

## Optional SIMRacingApps car graphics smoke test

- SIMRacingAppsServer is running before the broadcast starts.
- Broadcast Health shows `SIMRacingApps: Running`.
- Driver cards can show live car renders when SIMRacingApps has that car available.
- Leaderboard/driver-card numbers can use the styled number data from SIMRacingApps when available.
- If SIMRacingApps is closed, the broadcast still runs and falls back to plain numbers/manual graphics.

## Live iRacing smoke test

Use a short AI or hosted test session when possible.

- App connects to iRacing.
- Practice music stops when the session changes.
- RGC Anthem plays once during qualifying when configured.
- Race commentary does not start until the Race session.
- Starting lineup runs and returns to the home camera.
- Camera follows leader/home shots and story targets.
- Caution replay returns live after finishing.
- Pit-road panel updates when cars pit.
- Finish call waits for the field to finish before reading the top ten.

## Admin handoff check

- The admin has Python 3.11 or newer installed.
- The admin has their own OpenAI and ElevenLabs accounts if using AI voices.
- The admin knows SIMRacingAppsServer is optional, but recommended for live car renders and styled numbers.
- The admin knows the overlay link is local to the broadcast PC.
- The admin knows Tailscale is only needed for a trusted remote Producer Assist helper.
- Race Admin Mode stays off unless the broadcaster PC is an iRacing admin in the hosted session.
