# Project State

Current version: **v0.19.0 - v1.0 Release Prep**

## Working foundation

- Live iRacing telemetry adapter
- JSONL replay telemetry adapter
- One live/replay `BroadcastEngine`
- Race phase and milestone calls
- Pass, battle, story, pit-entry, pit-strategy, green-run, stage, and conservative incident detection
- Editorial prioritization, delay, cooldown, and speaker assignment
- OpenAI commentary with rule-based fallback
- Lead, Jeff, and Sarah ElevenLabs voice routing
- Priority, expiration, and deduplication in the broadcast scheduler
- Progressive pre-race welcome, weather, track report, and full-field rundown
- Practice, Qualifying, Warmup, and Race session detection with race-state reset when the Race session begins
- Practice music playlist, qualifying RGC Anthem ceremony, caution replay music bed, and global Studio volume
- Browser-source overlay with title, sponsor logos, caution/green state, vertical or ticker leaderboard, driver card, sponsor graphics, and Crank It Up graphics
- Automatic camera direction for leader/home shots, stories, driver rundowns, Crank It Up, and caution replay review
- Producer Assist control room with driver list, selected-driver details, race focus, director suggestions, race event log, pit road strategy, camera controls, and optional race-control commands
- League profiles, Sim Racer Hub imports, separate season/career stats CSVs, driver notes, sponsor reads, stage laps, and post-race interview handoff
- Windows installer build path, desktop shortcut, update checker, first-time setup checklist, and admin handoff docs
- Voice configuration diagnostics and a standalone ElevenLabs test command
- Automated tests for the critical orchestration rules

## Known limitations

- iRacing does not expose a clean all-driver incident-points feed through the SDK, so non-caution incident calls remain conservative.
- Hosted-race admin commands still rely on iRacing chat-command workflows; hidden/direct admin command support has not been confirmed.
- Caution replays depend on iRacing replay controls and previous-incident behavior, so they need real-session testing on each major update.
- The early Windows installer still requires Python 3.11-or-newer on the user's PC.
- Trading Paints/car-image support is planned as a league-admin/manual asset workflow first, not automatic public scraping.

## Current goal

Stabilize the current feature set into a v1.0 release candidate that outside league admins can install, configure, test, and use without editing code.

## Planned weekend-session intelligence

The broadcast recognizes Practice, Qualifying, Warmup, and Race. Practice and Qualifying can show overlay/session information and play configured presentation audio, while race commentary begins when the Race session opens. The next layer is richer weekend memory: practice pace notes, qualifying stories, league championship context, and track-history stats that can be used naturally during the race.
