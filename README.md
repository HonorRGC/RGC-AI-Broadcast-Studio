# RGC AI Broadcast Studio

AI-directed race production for iRacing. The studio turns live or recorded telemetry into editorial assignments, natural commentary, and routed ElevenLabs voices for a lead announcer, analyst, and pit reporter.

## How the platform works

```text
iRacing or JSONL replay
        -> Race intelligence and event detectors
        -> Editorial producer
        -> OpenAI commentary renderer
        -> Priority broadcast scheduler
        -> Lead / Jeff / Sarah ElevenLabs voices
```

Both live and replay telemetry use the same `BroadcastEngine`. Race-control messages can preempt stale commentary, pending stories are deduplicated and expired, and every story has one route to air.

The action detector watches position-adjacent cars on the same lap for very small longitudinal gaps. It creates side-by-side and three-car-battle assignments and attaches the involved car indices plus a recommended camera target. Lane-specific calls such as "on the outside" or "three-wide" are intentionally withheld until a future camera or spatial-data layer can confirm them.

For multi-session league events, Practice and Qualifying are detected but remain silent. Entering the Race session resets race-only state and begins the welcome, weather, track report, and starting-field rundown while cars are gridding.

See [docs/ARCHITECTURE.md](docs/ARCHITECTURE.md) for responsibilities and extension rules.

## Setup

Requirements: Windows, Python 3.11 or newer, and iRacing for live operation.

```powershell
py -m venv .venv
.\.venv\Scripts\Activate.ps1
python -m pip install -e ".[dev]"
Copy-Item .env.example .env
```

Add the desired API keys and voice IDs to `.env`. Generated audio and telemetry recordings are intentionally ignored by Git.

## Optional league driver notes

To let the broadcast use real league details, copy the example driver file and edit it for your league:

```powershell
New-Item -ItemType Directory -Force league
Copy-Item league.example\drivers.csv league\drivers.csv
```

Then enable driver notes in `.env`:

```text
USE_LEAGUE_DRIVER_NOTES=true
LEAGUE_DRIVERS_CSV=league/drivers.csv
```

For official races or unknown fields, leave this off:

```text
USE_LEAGUE_DRIVER_NOTES=false
```

Fill in hometown, state, country, driving style, sponsor, and notes for the drivers you know. The real `league\` folder is ignored by Git so private league notes do not get published by accident.

When OpenAI is enabled, race-story commentary can use one verified league detail when it naturally fits. For example, it may mention a driver’s hometown, driving style, or sponsor during a pass, battle, pit call, or momentum update. It should not invent missing facts or force a sponsor mention into every call.

## Run a live broadcast

```powershell
python app.py
```

Useful options:

```powershell
python app.py --no-voice
python app.py --tick-seconds 0.5
python app.py --voice-test
python app.py --camera-mode observe
python app.py --camera-mode auto --camera-group TV1 --camera-home-group "TV Mixed"
python app.py --camera-mode auto --incident-replay auto
python app.py --overlay
```

`--voice-test` reports whether the ElevenLabs key and voice IDs were loaded, plays one Lead sample, and exits without connecting to iRacing.

Camera direction is off by default. `observe` prints the car and camera group that would be selected without controlling iRacing. `auto` keeps the viewed replay at the live edge, holds the leader on the `TV Mixed` home shot, uses the closer `TV1` group for passes, lineup drivers, battles, pit stories, and incidents, and returns home after ten seconds. Starting-lineup groups rotate Lead, Jeff, then Lead while the camera advances through the named drivers; the green flag immediately restores the leader shot. Use camera modes while spectating or viewing the session screen.

Incident replay is separately opt-in. `--incident-replay auto` requires `--camera-mode auto`. A 2x-or-higher incident receives one TV1 replay with five seconds of pre-roll. When that incident is detected as a new caution begins, the director repeats the same moment on TV2 before returning to the live leader. Live-edge enforcement pauses while replay is active, and green or checkered immediately aborts replay and returns live. Use `--incident-replay observe` to preview replay decisions without sending replay or camera commands.

## Browser-source overlay

The first overlay layer is a local browser page for Streamlabs, OBS, or any tool that supports browser sources.

Set the race title and sponsor in `.env`:

```text
OVERLAY_EVENT_TITLE=RGC 80 at Nashville
OVERLAY_RACE_SPONSOR=Lee Family Racing
OVERLAY_SERIES_NAME=RGC Cup Series
```

Optional sponsor reads can use the same sponsor or a specific read:

```text
USE_SPONSOR_READS=true
SPONSOR_READ_NAME=RGC Motorsports
SPONSOR_READ_CAUSE=Autism Awareness
SPONSOR_READ_MESSAGE=
```

When enabled, the broadcast can place short sponsor mentions after the pre-race field rundown and during natural caution breaks after replay or pit-road coverage.

Then start the broadcast with:

```powershell
python app.py --overlay
```

The app prints the browser-source URL:

```text
Overlay: ON (http://127.0.0.1:8765/overlay)
```

Add that URL to Streamlabs or OBS as a browser source. The page shows a top race banner with the title, sponsor, series, track, and session, plus a left-side leaderboard that updates from iRacing telemetry.

## Run a recorded race

```powershell
python tools\telemetry_recorder.py recordings\race.jsonl
python app.py --replay recordings\race.jsonl --no-voice
```

Replay mode exercises the same race director, detectors, editorial producer, OpenAI renderer, and scheduler as live mode.

## Verify changes

```powershell
python -m pytest
```

Live validation is still required for SDK flag behavior and audio playback changes.

## Current focus

The next production improvements are a managed audio player, stronger incident confirmation, broadcast memory, and camera/replay direction. See [ROADMAP.md](ROADMAP.md).
