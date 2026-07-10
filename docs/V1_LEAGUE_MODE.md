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

The first Sim Racer Hub importer is available as a command-line bridge:

```powershell
python tools\sim_racer_hub_import.py "https://simracerhub.com/driver_stats.php?driver_id=90223" --league-id 1598 --season-id 29247 --output league\stats.csv
```

Useful WFO examples from the public driver page:

- `--league-id 1598` filters to WFO Racing League.
- `--series-id 3872` filters to WFO Racing League Wicked Wednesday Truck Series.
- `--series-id 4737` filters to WFO X Series Xfinity Cars.
- `--season-id 29247` filters to WFO Burn't Bacon Truck Series Season 17.
- `--season-id 29222` filters to RGC O'Reillys Series Season 17.

The importer currently reads one driver page at a time and updates `league/stats.csv` with starts, wins, top fives, top tens, poles, average finish, last finish, optional track-history stats, and a stat note containing Sim Racer Hub values like laps led, passes, quality passes, closing passes, incidents, average start, and average running position.

It can also bulk import a whole season from a Sim Racer Hub `league_stats.php` page:

```powershell
python tools\sim_racer_hub_import.py "https://simracerhub.com/league_stats.php?series_id=3872" --bulk --league-id 1598 --series-id 3872 --season-id 29247 --output league\stats.csv
```

You can also pass the Sim Racer Hub series seasons URL; bulk mode automatically follows it to the matching stats page:

```powershell
python tools\sim_racer_hub_import.py "https://simracerhub.com/series_seasons.php?series_id=3872&reset_series=y" --bulk --league-id 1598 --series-id 3872 --season-id 29247 --output league\stats.csv
```

Use `--min-starts 2` or higher if you want to skip one-off substitute drivers.

For career stats across every WFO Wicked Wednesday Truck Series season on the page, leave off `--season-id`:

```powershell
python tools\sim_racer_hub_import.py "https://simracerhub.com/series_seasons.php?series_id=3872&reset_series=y" --bulk --league-id 1598 --series-id 3872 --min-starts 10 --output league\stats.csv
```

That produces series-career totals for each driver, including total starts, wins, top fives, top tens, poles, average finish, laps led, passes, quality passes, closing passes, and incidents. Use a higher `--min-starts` value if you only want regular WFO drivers.

To add track-history stats for the race you are about to broadcast, include `--track-name`:

```powershell
python tools\sim_racer_hub_import.py "https://simracerhub.com/league_stats.php?series_id=3872" --bulk --league-id 1598 --series-id 3872 --track-name Nashville --min-starts 10 --output league\stats.csv
```

The importer matches the name against Sim Racer Hub track names and config names, then fills `track_starts`, `track_wins`, `best_track_finish`, and a note about the driver's most recent race at that track.

The next integration path is:

1. Import each known league driver from a full Sim Racer Hub series stats page.
2. Add standings-page support for official points position and points-to-next.
3. Add a launcher button for importing Sim Racer Hub stats without typing commands.

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

The first league-stats workflow now exists in the launcher under `League / Sim Racer Hub`:

- paste a Sim Racer Hub URL
- enter league and series IDs
- choose season mode or career mode
- add the upcoming track name for track-history stats
- preview the import
- write stats into `league/stats.csv`

The launcher can also import a safe driver roster into `league/drivers.csv`. It adds missing drivers and cleans Sim Racer Hub suffixes, but preserves manual fields such as hometown, driving style, sponsor, and notes.
