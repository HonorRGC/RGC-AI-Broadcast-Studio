# Project State

Current version: **v0.18 - Platform Foundation**

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

The intended broadcast lifecycle begins in practice, carries driver observations into qualifying, and then uses qualifying and practice context during the race. Session transitions must reset session-specific timing while preserving a separate weekend memory. This is the next architectural layer after race-mode validation.
