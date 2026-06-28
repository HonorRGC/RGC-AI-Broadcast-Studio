# RGC AI Broadcast Studio

> Professional AI race production for iRacing.

RGC AI Broadcast Studio is an AI-powered race broadcast system designed to make iRacing events feel like professionally produced motorsports broadcasts.

This project is not just an AI commentator. It is being built as a full AI production crew with race control, story detection, editorial decision-making, booth personalities, pit reporting, voice direction, and future camera/replay control.

---

## Vision

The goal is simple:

**Build an AI broadcast that racing fans can watch without feeling like they are listening to AI.**

The system should not talk about everything. It should notice what matters, choose the right story, and deliver it with the timing and tone of a real broadcast team.

---

## Current Capabilities

- Live iRacing SDK connection
- Race phase detection
  - Formation
  - Green flag
  - Caution
  - One to green
  - White flag
  - Checkered flag
- Pre-race track report
- Starting lineup rundown
- Restart rundown
- Finish rundown
- Lap milestone calls
  - 10 to go
  - 5 to go
  - White flag
- RaceBrain event detection
- Broadcast Producer filtering
- Broadcast Context driver memory
- Story Detector
- Editorial Producer
- Voice Director
- Lead Announcer
- Jeff, Color Analyst
- Sarah, Pit Reporter
- ElevenLabs voice routing
- OpenAI commentary generation
- Pit strategy detection
- Driver name cleanup
- SDK inspection tools

---

## In Development

- Incident Director
- Trouble detection
- Replay/test harness
- Broadcast memory
- Personality engine
- Camera Director
- Replay Director
- OpenAI Broadcast Brain

---

## Broadcast Architecture

```text
iRacing SDK
    ↓
Race Director
    ↓
Broadcast Context
    ↓
Story Detector
    ↓
Editorial Producer
    ↓
Broadcast Producer
    ↓
Voice Director
    ↓
Lead / Jeff / Sarah
    ↓
Broadcast Queue
    ↓
ElevenLabs / Console Output