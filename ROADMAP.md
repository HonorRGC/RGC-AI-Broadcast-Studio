# RGC AI Broadcast Studio Roadmap

## Current: v0.18 - Platform Foundation

The studio now has one orchestration path for live and replay telemetry. Development should focus on broadcast truth, timing, and memory before expanding the number of production departments.

## v0.19 - Replay Validation

- Record representative green runs, cautions, restarts, pit cycles, incidents, and finishes
- Build compact, anonymized replay fixtures
- Validate battle gaps and incident signals against those fixtures
- Add end-to-end editorial timing assertions

## Weekend Session Intelligence

- Start the broadcast during practice
- Track practice pace, consistency, incidents, and developing driver stories
- Carry relevant practice observations into qualifying
- Report qualifying results and build the race starting lineup
- Preserve weekend memory across Practice, Qualifying, and Race transitions
- Reset race-control state without losing weekend-level driver context

## v0.20 - Managed Audio

- Replace shell-launched MP3 playback with a managed player
- Observe actual playback completion
- Prevent overlapping voices
- Support urgent interruption and cancellation
- Cache repeated deterministic calls where appropriate

## v0.21 - Broadcast Memory and Personalities

- Record which facts, phrases, and drivers were recently discussed
- Give Lead, Jeff, and Sarah distinct prompt contracts
- Add analyst follow-ups and pit-reporter handoffs
- Prevent factual and phrasing repetition across a race

## v0.22 - Incident Director

- Combine surface, motion, position, pace, and caution evidence
- Distinguish spins, contact, slow cars, pit entry, and normal lap wrap
- Require confidence thresholds before making definitive calls
- Track likely caution cause for replay direction

## v0.23 - Camera and Replay Direction

- Convert editorial assignments into camera targets
- Follow active battles and pit cycles
- Capture likely incidents for replay
- Return cleanly from replay to live action

## v0.24 - League Product and Graphics

- Browser-source overlay for Streamlabs, OBS, and other production tools
- Top race banner, leaderboard, lower-third driver card, and segment graphics
- League configuration files for race name, branding, sponsors, and event data
- Driver profiles with hometown, state/country, sponsor, style, and notes
- Sponsor reads and static sponsor graphics
- Setup guide for league admins
- Later: commercial video playback after managed audio and overlay control exist

See [docs/LEAGUE_PRODUCT_PLAN.md](docs/LEAGUE_PRODUCT_PLAN.md).

## Version 1.0

A believable autonomous iRacing broadcast with reliable race understanding, disciplined editorial timing, distinct booth personalities, managed audio, camera direction, replay direction, and graphics-ready output.
