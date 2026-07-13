# Project State

Current version: **v0.18.1 - Platform Foundation**

## Working foundation

- Live iRacing telemetry adapter
- JSONL replay telemetry adapter
- One live/replay `BroadcastEngine`
- Race phase and milestone calls
- Pass, battle, story, pit-entry, and experimental incident detection
- Editorial prioritization, delay, cooldown, and speaker assignment
- OpenAI commentary with rule-based fallback
- Lead, Jeff, and Sarah ElevenLabs voice routing
- Priority, expiration, and deduplication in the broadcast scheduler
- Progressive pre-race welcome, weather, track report, and full-field rundown
- Silent Practice/Qualifying detection with race-state reset when the Race session begins
- Voice configuration diagnostics and a standalone ElevenLabs test command
- Automated tests for the critical orchestration rules

## Known limitations

- Incident detection needs validation against representative recordings.
- ElevenLabs playback is launched by Windows and does not yet report completion back to the scheduler.
- Battle gap interpretation needs comparison with recorded iRacing fields.
- Driver history is represented by several internal intelligence models.
- Camera, replay, graphics, championship, and interview direction are not implemented.

## Current goal

Collect representative race recordings and use them to validate incident detection, battle gaps, editorial timing, and audio pacing before adding camera automation.

## Planned weekend-session intelligence

The broadcast now recognizes Practice, Qualifying, Warmup, and Race, but intentionally remains silent before the Race session. The next layer will collect practice and qualifying observations into a separate weekend memory while preserving the current rule that on-air commentary begins only when the Race session opens.
