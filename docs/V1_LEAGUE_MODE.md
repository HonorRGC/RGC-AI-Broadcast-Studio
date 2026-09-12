# RGC AI Broadcast Studio v1 League Mode

The v1 league goal is to let a league admin configure a broadcast without editing Python files or opening VS Code.

## Near-term workflow

1. Fill out league files:
   - `league/drivers.csv` for hometown, country, driving style, team, sponsor, and notes.
   - `league/season.csv` for current-season stats, points, prior finish, and track history.
   - `league/career.csv` for all-season/career stats from the selected series.
2. Set broadcast settings in the app or `.env`.
3. Start the race broadcast once. Producer Assist launches with it so the broadcaster can turn OpenAI, ElevenLabs, and auto cameras on or off during the same session.

## Stats currently supported

`league/season.csv` and `league/career.csv` support:

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
python tools\sim_racer_hub_import.py "https://simracerhub.com/driver_stats.php?driver_id=YOUR_DRIVER_ID" --league-id YOUR_LEAGUE_ID --season-id YOUR_SEASON_ID --output league\season.csv
```

Useful placeholders for your league:

- `--league-id YOUR_LEAGUE_ID` filters to one league.
- `--series-id YOUR_SERIES_ID` filters to one series.
- `--season-id YOUR_SEASON_ID` filters to one season.
- Leave off `--season-id` for career totals across the selected series.

The importer currently reads one driver page at a time and updates a stats CSV with starts, wins, top fives, top tens, poles, average finish, last finish, optional track-history stats, and a stat note containing Sim Racer Hub values like laps led, passes, quality passes, closing passes, incidents, average start, and average running position. Use `league/season.csv` for current season imports and `league/career.csv` for all-season imports.

It can also bulk import a whole season from a Sim Racer Hub `league_stats.php` page:

```powershell
python tools\sim_racer_hub_import.py "https://simracerhub.com/league_stats.php?series_id=YOUR_SERIES_ID" --bulk --league-id YOUR_LEAGUE_ID --series-id YOUR_SERIES_ID --season-id YOUR_SEASON_ID --output league\season.csv
```

You can also pass the Sim Racer Hub series seasons URL; bulk mode automatically follows it to the matching stats page:

```powershell
python tools\sim_racer_hub_import.py "https://simracerhub.com/series_seasons.php?series_id=YOUR_SERIES_ID&reset_series=y" --bulk --league-id YOUR_LEAGUE_ID --series-id YOUR_SERIES_ID --season-id YOUR_SEASON_ID --output league\season.csv
```

Use `--min-starts 2` or higher if you want to skip one-off substitute drivers.

For career stats across every season in the selected series, leave off `--season-id`:

```powershell
python tools\sim_racer_hub_import.py "https://simracerhub.com/series_seasons.php?series_id=YOUR_SERIES_ID&reset_series=y" --bulk --league-id YOUR_LEAGUE_ID --series-id YOUR_SERIES_ID --min-starts 10 --output league\career.csv
```

That produces series-career totals for each driver, including total starts, wins, top fives, top tens, poles, average finish, laps led, passes, quality passes, closing passes, and incidents. Use a higher `--min-starts` value if you only want regular league drivers.

To add track-history stats for the race you are about to broadcast, include `--track-name`:

```powershell
python tools\sim_racer_hub_import.py "https://simracerhub.com/league_stats.php?series_id=YOUR_SERIES_ID" --bulk --league-id YOUR_LEAGUE_ID --series-id YOUR_SERIES_ID --track-name Nashville --min-starts 10 --output league\career.csv
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
- live Producer Assist toggles for OpenAI, ElevenLabs, and auto camera control
- race title, sponsor, and graphics
- league driver editor
- league stats importer
- overlay preview
- start broadcast button

The first league-stats workflow now exists in the launcher under `League / Sim Racer Hub`:

- paste a Sim Racer Hub URL
- enter league and series IDs
- choose season mode or career mode
- import season/career stats without choosing the next track manually
- preview the import
- write season stats into `league/season.csv` or career stats into `league/career.csv`

The launcher can also import a safe driver roster into `league/drivers.csv`. It adds missing drivers and cleans Sim Racer Hub suffixes, but preserves manual fields such as hometown, driving style, sponsor, and notes.
