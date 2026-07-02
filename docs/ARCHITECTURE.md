# Architecture

## Design rule

A fact should have one owner and a story should have one route to air. Feature modules detect or enrich information; `BroadcastEngine` owns orchestration.

## Runtime flow

1. A telemetry source exposes the live/replay read contract.
2. `RaceDirector` owns race phase and protected race-control calls.
3. `RaceIntelligence`, `RaceBrain`, `IncidentDetector`, and `PitStrategyDetector` produce facts and candidate stories.
4. `EditorialProducer` deduplicates, delays, prioritizes, and assigns a speaker.
5. `OpenAIDirector` turns the assignment into concise on-air language. Rule-based text remains the fallback.
6. `BroadcastQueue` expires stale work and lets protected race control outrank normal stories.
7. `BroadcastBooth` routes the selected item to console and the appropriate ElevenLabs voice.

## Ownership

| Responsibility | Owner |
| --- | --- |
| Live SDK reads | `broadcaster.telemetry.IRacingTelemetry` |
| Recorded SDK reads | `replay.replay_telemetry.ReplayTelemetry` |
| Session orchestration | `broadcast.engine.BroadcastEngine` |
| Race phase | `broadcaster.race_director.RaceDirector` |
| Developing stories | `production.race_intelligence.RaceIntelligence` |
| Pass detection | `broadcaster.race_brain.RaceBrain` |
| Incident candidates | `production.incident_detector.IncidentDetector` |
| Pit entry candidates | `production.pit_strategy_detector.PitStrategyDetector` |
| Editorial timing | `production.editorial_producer.EditorialProducer` |
| Natural language | `production.openai_director.OpenAIDirector` |
| Airtime scheduling | `broadcast.broadcast_queue.BroadcastQueue` |
| Voice routing | `broadcast.booth.BroadcastBooth` |

## Extension rules

- New detectors return structured facts; they do not speak or call OpenAI.
- Only the race director and confirmed incidents bypass editorial review.
- Every queued item needs a category, expiration, and stable deduplication key.
- Live and replay modes must use the same engine.
- A feature is not complete without automated replay/component tests and a live validation note when SDK behavior is involved.

## Planned boundaries

The current `RaceIntelligence` package still contains several internal driver-history models. A later migration will replace those with a canonical immutable race snapshot. This should happen alongside recorded telemetry validation, rather than as a blind data-model rewrite.
