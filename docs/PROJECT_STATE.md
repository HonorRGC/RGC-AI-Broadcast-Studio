# PROJECT STATE

Last Updated: June 2026

Current Version: **v0.17 – Broadcast Production Foundation**

---

# Current Status

RGC AI Broadcast Studio has evolved beyond a simple AI commentator.

The project is now structured as an AI television production system consisting of independent production departments that work together to produce a realistic race broadcast.

The current focus is improving production quality rather than simply adding commentary.

---

# Core Systems

## Telemetry

Status: ✔ Complete

Responsibilities

- Connect to iRacing SDK
- Driver lookup
- Session information
- Track information
- Weekend information
- Pit road status
- Position data
- Results data

Future

- Replay telemetry
- Telemetry recording
- Telemetry playback

---

## Race Director

Status: ✔ Complete

Responsibilities

- Detect race phase
- Formation
- Green Flag
- Yellow Flag
- One To Green
- White Flag
- Checkered Flag

Current State

Stable

---

## Race Brain

Status: ✔ Complete

Responsibilities

- Detect passes
- Position changes
- Biggest movers
- Running order

Current State

Stable

---

## Story Detector

Status: ✔ Complete

Responsibilities

Determine what stories are developing during the race.

Current State

Needs expansion for longer race storylines.

---

## Editorial Producer

Status: ✔ Complete

Responsibilities

Rank stories by importance.

Controls what reaches the broadcast.

Current State

Working well.

Future

Smarter prioritization.

---

## Broadcast Producer

Status: ✔ Complete

Responsibilities

Final quality control before commentary.

Filters repetitive stories.

Current State

Stable.

---

## Voice Director

Status: ✔ Complete

Responsibilities

Controls:

- Lead
- Jeff
- Sarah

Controls timing between personalities.

Current State

Working well.

Future

Conversation timing.

Natural interruptions.

---

## Lead Announcer

Status: ✔ Complete

Current State

Needs additional phrase variety.

---

## Jeff

Status: ✔ Complete

Current State

Needs larger knowledge base.

Needs OpenAI personality.

---

## Sarah

Status: ✔ Complete

Current State

Needs green flag pit strategy expansion.

Needs caution strategy expansion.

---

# Systems Under Development

## Incident Director

Priority: VERY HIGH

Goal

Detect meaningful race trouble.

Not simply official incident points.

Desired detection

✔ Contact

✔ Wall contact

✔ Spins

✔ Off-track

✔ Slow cars

✔ Damage

✔ Position loss

✔ Tire failures (future)

Current Status

Research phase.

No production implementation yet.

---

## Replay Harness

Priority: VERY HIGH

Purpose

Reduce live iRacing testing.

This will become the primary testing environment.

Expected Benefits

- Faster development

- Repeatable tests

- Less ElevenLabs usage

- Less iRacing setup

---

# Future Departments

Camera Director

Replay Director

Graphics Director

Statistics Director

Weather Director

Commercial Director

Victory Lane Director

Interview Director

---

# Technical Debt

Current items to improve

- Incident detection

- Commentary repetition

- Replay testing

- Documentation

- Camera automation

---

# Development Rules

Every feature must:

✔ Compile

✔ Replay test

✔ Live test

✔ Update PROJECT_STATE

✔ Git Commit

---

# Current Goal

Build the Replay Harness before adding major broadcast features.

The Replay Harness is expected to reduce development time significantly.

---

# Long-Term Goal

Create the most realistic AI race broadcast system available.

The final system should feel less like software and more like an actual television production crew.