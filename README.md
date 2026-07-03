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
```

`--voice-test` reports whether the ElevenLabs key and voice IDs were loaded, plays one Lead sample, and exits without connecting to iRacing.

Camera direction is off by default. `observe` prints the car and camera group that would be selected without controlling iRacing. `auto` keeps the leader on the `TV Mixed` home shot, uses `TV1` for passes, close battles, pit stories, and incidents, and returns home after ten seconds. During the starting-lineup narration it advances through the named drivers, and the green flag immediately restores the leader shot. Use camera modes while spectating or viewing the session screen.

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
