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
```

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
