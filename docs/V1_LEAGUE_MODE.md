# RGC AI Broadcast Studio v1 League Mode

The v1 league goal is to let a league admin configure a broadcast without editing Python files or opening VS Code.

## Near-term workflow

1. Fill out league files:
   - `league/drivers.csv` for hometown, country, driving style, team, sponsor, and notes.
   - `league/stats.csv` for season stats, points, prior finish, and track history.
2. Set broadcast settings in the app or `.env`.
3. Start the race broadcast in one of two modes:
   - Full AI broadcast: OpenAI + ElevenLabs speak the show.
   - Broadcast helper: camera, overlays, and suggested talking points without AI voices.

## Stats currently supported

`league/stats.csv` supports:

- starts
- wins
- top fives
- top tens
- poles
- average finish
- last race finish
- points position
- points to next position
- track starts
- track wins
- best finish at the current track
- free-form stat notes

These stats are added to the verified driver context OpenAI receives, so the broadcast can mention them naturally when that driver is already part of a story.

## Sim Racer Hub integration plan

The safe integration path is:

1. Import or export Sim Racer Hub league data into `league/stats.csv`.
2. Confirm the exact fields available for the league.
3. Add a dedicated importer that converts Sim Racer Hub standings/results/track history into the same internal stats format.

This keeps the broadcast engine stable while we learn the exact Sim Racer Hub data shape.

## Desktop app plan

The desktop app should become a setup shell around the existing engine:

- API keys and voice IDs
- full AI broadcast vs broadcast helper mode
- race title, sponsor, and graphics
- league driver editor
- league stats importer
- overlay preview
- start broadcast button

