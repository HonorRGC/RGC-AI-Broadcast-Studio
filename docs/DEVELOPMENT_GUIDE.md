# Development Guide

## Workflow

1. Create a focused branch.
2. Make the smallest coherent change to the canonical engine.
3. Add or update component/replay tests.
4. Run `python -m pytest`.
5. Run a console-only replay with `python app.py --replay <file> --no-voice`.
6. Live-test changes that depend on iRacing flags, timing, or audio.
7. Update project documentation when responsibilities or behavior change.

## Guardrails

- Do not commit `.env`, recordings, generated audio, caches, or bytecode.
- Do not create a second live and replay implementation.
- Do not call OpenAI from event detectors.
- Do not send the same fact directly to the queue and through editorial review.
- Keep urgent race-control language deterministic and protected.
- Give normal commentary an expiration time so stale calls cannot air.

## Verification

```powershell
python -m pytest
python app.py --replay recordings\race.jsonl --no-voice
```
