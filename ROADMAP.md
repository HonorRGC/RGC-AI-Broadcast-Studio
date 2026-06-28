# RGC AI Broadcast Studio Roadmap

## Current Version

**v0.17 — Broadcast Production Foundation**

RGC AI Broadcast Studio is moving from an AI commentator into a full AI race production system.

---

## Core Mission

Build a professional AI broadcast crew for iRacing that can:

- Understand the race
- Detect important stories
- Decide what matters
- Use multiple booth personalities
- Control voice timing
- Report strategy
- Eventually control cameras, replays, and graphics

---

## Completed Milestones

### v0.10 — Race Director

- Formation detection
- Green flag detection
- Caution detection
- One-to-green detection

### v0.11 — Broadcast Producer

- Event filtering
- Priority handling
- Reduced random pass chatter

### v0.12 — Race Lifecycle

- 10 to go
- 5 to go
- White flag
- Checkered flag
- Finish rundown
- Stop pass calls after race end

### v0.13 — Broadcast Intelligence

- Broadcast Context
- Driver movement tracking
- Biggest mover detection
- Story summaries
- Mention cooldowns

### v0.14 — Voice Direction

- Jeff, Color Analyst
- Voice Director
- Lead/Jeff timing
- Separate voice routing
- Pre-race track report

### v0.15 — Pit Strategy

- Pit Strategy Detector
- Green-flag pit callouts
- Caution pit callouts
- Sarah pit voice routing

### v0.16 — Editorial Producer

- Editorial Producer created
- Race stories submitted for editorial review
- Pit strategy stories submitted
- Project structure cleanup started

### v0.17 — Production Foundation

- Track info fixed through direct WeekendInfo
- Driver name cleanup
- SDK inspector tool
- Project documentation update
- Incident/Trouble Director research started

---

## In Progress

### Incident Director

Goal:

Detect meaningful race trouble live.

Targets:

- Wall contact
- Vehicle contact
- Spins
- Off-track events
- Sudden position loss
- Sudden speed loss
- Slow cars
- Damage indicators when available
- Caution-triggering incidents

Status:

Experimental. We are moving away from only using official incident points because they are not reliable enough live for full-field broadcast detection.

---

## Next Milestones

### v0.18 — Replay/Test Harness

Purpose:

Reduce live iRacing testing time.

Goals:

- Run broadcaster logic without opening iRacing
- Feed saved telemetry snapshots into the system
- Simulate cautions, restarts, pit stops, incidents, and finishes
- Make testing faster and repeatable

### v0.19 — Incident Director 2.0

Purpose:

Create reliable live race trouble detection.

Inputs may include:

- Car position changes
- Lap distance percent
- Track surface
- Track surface material
- Estimated time loss
- Pit road status
- Session flags
- Position loss
- Official incident fields when available

### v0.20 — Camera Director

Purpose:

Automatically move the iRacing camera to the story being discussed.

Goals:

- Focus on leader
- Focus on battle
- Focus on pit road
- Focus on incident
- Follow Editorial Producer decisions

### v0.21 — Replay Director

Purpose:

Capture and replay important moments.

Goals:

- Save incident moments
- Replay passes for the lead
- Replay pit road mistakes
- Replay restart chaos
- Allow Jeff to analyze replay moments

### v0.22 — OpenAI Broadcast Brain

Purpose:

Make Lead, Jeff, and Sarah sound less repetitive and more human.

Goals:

- Personality prompts
- Broadcast memory
- Avoid repeated phrases
- Context-aware commentary
- Natural booth conversations

### v0.23 — Track Knowledge Base

Purpose:

Make pre-race introductions sound professional and track-specific.

Goals:

- Track facts
- Track history
- Banking
- Length
- Strategy notes
- Signature corners
- Broadcast trivia

### v0.24 — Broadcast Memory

Purpose:

Allow the booth to remember what has already been said.

Goals:

- Lead memory
- Jeff memory
- Sarah memory
- Avoid repeating topics
- Reference earlier comments naturally

### v0.25 — Graphics Director

Purpose:

Prepare future overlay and stream integration.

Goals:

- Driver lower thirds
- Running order
- Pit strategy graphics
- Incident alerts
- Replay labels

---

## Version 1.0 Goal

A complete AI broadcast system capable of producing a believable iRacing race broadcast with:

- Race control
- Story detection
- Editorial decision-making
- Multiple booth personalities
- Pit reporting
- Camera direction
- Replay direction
- Natural OpenAI-generated commentary
- ElevenLabs voice output
- Console-only testing mode

---

## Long-Term Vision

RGC AI Broadcast Studio should become a full AI production truck for sim racing.

Future possibilities:

- League-specific broadcast packages
- Sponsor reads
- Championship storylines
- Driver profiles
- Season databases
- Victory lane interviews
- Automated highlight reels
- Stream overlays
- Multiple broadcast teams
- Custom voices and personalities