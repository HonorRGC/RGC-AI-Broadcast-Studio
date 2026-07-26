# RGC AI Broadcast Studio

AI-directed race production for iRacing. The studio turns live or recorded telemetry into editorial assignments, natural commentary, and routed ElevenLabs voices for a lead announcer, analyst, and pit reporter.

## How the platform works

```text
iRacing or JSONL replay
        -> Race intelligence and event detectors
        -> Editorial producer
        -> OpenAI commentary renderer
        -> Priority broadcast scheduler
        -> Lead / Jeff / Sarah ElevenLabs voices
```

Both live and replay telemetry use the same `BroadcastEngine`. Race-control messages can preempt stale commentary, pending stories are deduplicated and expired, and every story has one route to air.

The action detector watches position-adjacent cars on the same lap for very small longitudinal gaps. It creates side-by-side and three-car-battle assignments and attaches the involved car indices plus a recommended camera target. Lane-specific calls such as "on the outside" or "three-wide" are intentionally withheld until a future camera or spatial-data layer can confirm them.

For multi-session league events, Practice and Qualifying are detected but remain silent. Entering the Race session resets race-only state and begins the welcome, weather, track report, and starting-field rundown while cars are gridding.

See [docs/ARCHITECTURE.md](docs/ARCHITECTURE.md) for responsibilities and extension rules.

## Setup

Requirements: Windows, Python 3.11 or newer, and iRacing for live operation. Newer Python 3 versions are okay as long as they can create a virtual environment.

```powershell
py -m venv .venv
.\.venv\Scripts\Activate.ps1
python -m pip install -e ".[dev]"
Copy-Item .env.example .env
```

Add the desired API keys and voice IDs to `.env`. Generated audio and telemetry recordings are intentionally ignored by Git.

For outside testers, the preferred path is now a Windows `Setup.exe`; see [docs/WINDOWS_INSTALLER_BUILD.md](docs/WINDOWS_INSTALLER_BUILD.md). For a full step-by-step install and key setup tutorial, see [docs/INSTALL_AND_SETUP_GUIDE.md](docs/INSTALL_AND_SETUP_GUIDE.md). For a league admin handoff, see [docs/ADMIN_TESTER_HANDOFF.md](docs/ADMIN_TESTER_HANDOFF.md). The tester ZIP path in [docs/TESTER_QUICKSTART.md](docs/TESTER_QUICKSTART.md) remains available as a fallback while the installer is being polished.

## Early desktop launcher

An early Windows-friendly launcher is available:

```powershell
python studio_launcher.py
```

The launcher can save the main `.env` settings, create `league\drivers.csv`, `league\season.csv`, and `league\career.csv` from the examples, and start the broadcast engine. Use `Start Broadcast` for AI or human-broadcaster workflows: the overlay, Producer Assist control room, cameras, and incident replay all launch together. Producer Assist can turn OpenAI, ElevenLabs, and auto cameras on or off while the broadcast is running. Use `Stop Broadcast` to stop a broadcast launched from the program.

Use each sponsor slot’s `Choose Logo` button to copy one sponsor graphic into the overlay assets folder. The title-logo rotation follows Sponsor 1 through Sponsor 5 in order, with the series and cause logos added from their own fields.

Practice music, RGC Anthem audio, caution replay audio, and presentation graphics can also be selected in the launcher. These local audio files play through hidden Windows audio controls so testers do not get a media-player window popping up on the desktop. MP3 or WAV files are recommended; OGA/OGG files are not supported by the hidden Windows player. Practice music loops through the playlist until practice ends. The RGC Anthem remains a one-time qualifying ceremony and can play multiple selected songs once in order. Use semicolons between multiple songs if editing a playlist manually.
Use the **Studio Volume** slider in the launcher to control program audio, including practice music, RGC Anthem audio, caution replay audio, and ElevenLabs voice playback. The slider is a percentage from 0 to 100.

Turn on `POST_RACE_INTERVIEWS_ENABLED` when the league admin plans to interview the podium after the race. With that option enabled, the broadcast still reads the top ten finishers, then hands off to post-race interviews in third, second, winner order instead of playing the normal sign-off.

After the checkered flag, the camera stays with the winner/leader shot for the celebration and post-race handoff.

The launcher also includes a `League / Sim Racer Hub` tab. Paste a Sim Racer Hub series or stats URL, choose season mode or career mode, optionally enter the upcoming track name, preview the import, and then write season results to `league\season.csv` or career results to `league\career.csv`.

The same tab can import a driver roster into `league\drivers.csv`. Roster import is safe for manual edits: it adds missing drivers and fills empty basics, but keeps your hometown, sponsor, driving-style, and notes fields.

For a cleaner Sim Racer Hub setup, the URL can simply be `https://simracerhub.com`; the launcher uses the Series ID and optional Season ID to open the correct stats page. The Track History field is optional. It does not tell the live broadcast what track iRacing is at; it only pre-loads stats like prior starts, wins, and best finish at a specific track.

## Optional league driver notes and stats

To let the broadcast use real league details, copy the example driver and stats files and edit them for your league:

```powershell
New-Item -ItemType Directory -Force league
Copy-Item league.example\drivers.csv league\drivers.csv
Copy-Item league.example\season.csv league\season.csv
Copy-Item league.example\career.csv league\career.csv
```

Then enable league context in `.env`:

```text
USE_LEAGUE_DRIVER_NOTES=true
LEAGUE_DRIVERS_CSV=league/drivers.csv
LEAGUE_SEASON_STATS_CSV=league/season.csv
LEAGUE_CAREER_STATS_CSV=league/career.csv
STAGE_END_LAPS=30,60
```

For official races or unknown fields, leave this off:

```text
USE_LEAGUE_DRIVER_NOTES=false
```

Fill in hometown, state, country, driving style, sponsor, and notes for the drivers you know. The stats file can include starts, wins, top fives, last finish, points position, points to the next spot, and prior history at the current track. The real `league\` folder is ignored by Git so private league notes do not get published by accident.

When OpenAI is enabled, race-story commentary can use one verified league detail when it naturally fits. For example, it may mention a driver’s hometown, driving style, or sponsor during a pass, battle, pit call, or momentum update. It should not invent missing facts or force a sponsor mention into every call.

League stats are also treated as verified context. For example, the broadcast may mention points position, last finish, wins, average finish, or prior track history when it naturally fits the current story.

For leagues that use stages, set `STAGE_END_LAPS` to the laps where stage points are awarded, such as `30,60`. If the race stays green, the broadcast will still call the stage end and read the stage-points top ten. If a caution comes out at that stage lap, the caution call is treated as a scheduled stage break instead of an accident caution.

See [docs/V1_LEAGUE_MODE.md](docs/V1_LEAGUE_MODE.md) for the league-mode and Sim Racer Hub importer plan.

### Import Sim Racer Hub driver stats

Public Sim Racer Hub driver stat pages can be imported into `league\season.csv`:

```powershell
python tools\sim_racer_hub_import.py "https://simracerhub.com/driver_stats.php?driver_id=YOUR_DRIVER_ID" --league-id YOUR_LEAGUE_ID --season-id YOUR_SEASON_ID --output league\season.csv
```

Use `--dry-run` first if you want to preview the row before updating the CSV.

To import a current league season from the series stats page:

```powershell
python tools\sim_racer_hub_import.py "https://simracerhub.com/league_stats.php?series_id=YOUR_SERIES_ID" --bulk --league-id YOUR_LEAGUE_ID --series-id YOUR_SERIES_ID --season-id YOUR_SEASON_ID --output league\season.csv
```

The same bulk command also accepts the Sim Racer Hub series seasons URL and automatically follows it to the matching stats page.

For career stats across every season in a series, leave off `--season-id`:

```powershell
python tools\sim_racer_hub_import.py "https://simracerhub.com/series_seasons.php?series_id=YOUR_SERIES_ID&reset_series=y" --bulk --league-id YOUR_LEAGUE_ID --series-id YOUR_SERIES_ID --min-starts 10 --output league\career.csv
```

To include prior history at the upcoming track:

```powershell
python tools\sim_racer_hub_import.py "https://simracerhub.com/league_stats.php?series_id=YOUR_SERIES_ID" --bulk --league-id YOUR_LEAGUE_ID --series-id YOUR_SERIES_ID --track-name Nashville --min-starts 10 --output league\career.csv
```

## Run a live broadcast

```powershell
python app.py
```

The default live run has voice enabled, camera control on auto, caution replay on auto, and the browser-source overlay on.

Useful options:

```powershell
python app.py --no-voice
python app.py --tick-seconds 0.5
python app.py --voice-test
python app.py --camera-mode observe
python app.py --camera-mode auto --camera-group TV1 --camera-home-group "TV Mixed"
python app.py --incident-marker-preroll-seconds 28
python app.py --no-overlay
```

`--voice-test` reports whether the ElevenLabs key and voice IDs were loaded, plays one Lead sample, and exits without connecting to iRacing.

Camera direction is auto by default. `observe` prints the car and camera group that would be selected without controlling iRacing. `auto` keeps the viewed replay at the live edge, holds the leader on the `TV Mixed` home shot, uses the closer `TV1` group for passes, battles, and race stories, and returns home after the story hold. The starting lineup uses Rear Chase when available and holds the lineup shot until the next driver or green flag.

Incident replay is auto by default and requires `--camera-mode auto`. Cautions receive one stable Far Chase replay using iRacing's previous-incident marker with 25 seconds of pre-roll, held for 20 seconds, then the broadcast returns to the live leader. Live-edge enforcement pauses while replay is active, and green or checkered immediately aborts replay and returns live. Use `--incident-replay observe` to preview replay decisions without sending replay or camera commands.

Race-flow resets are intentionally conservative. The pre-race starting lineup moves quickly from driver to driver, then returns the camera to the TV Mixed leader/home shot when the lineup closes. During a race, Jeff gives one long-run top-ten reset only after 20 consecutive green-flag laps; if a caution interrupts that feature, it does not resume with stale positions. Under caution, Sarah waits until one-to-green to summarize pit-road activity so the field has time to finish the pit cycle, and Jeff can add one quick current top-ten reset before the restart. If a caution flies immediately after a restart, the replay backs up farther to include more of the restart stack-up.

During long green runs, the booth can add one-time racing insight about tire wear, throttle technique, drafting, or fuel saving. These notes are non-repeating and only air when the race has enough natural space. On a late caution before a short run to the finish, Jeff can also frame the restart as a sprint where track position and execution matter more than saving tires.

## Browser-source overlay

The first overlay layer is a local browser page for Streamlabs, OBS, or any tool that supports browser sources.

Set the race title and sponsor in `.env`:

```text
OVERLAY_EVENT_TITLE=RGC 80 at Nashville
OVERLAY_RACE_SPONSOR=Lee Family Racing
OVERLAY_SERIES_NAME=RGC Cup Series
OVERLAY_HOST=127.0.0.1
RACE_SPONSOR_1_LOGO=/assets/rgc_motorsports.png
RACE_SPONSOR_2_LOGO=/assets/autism_awareness.png
CRANK_IT_UP_SPONSOR_GRAPHIC=/assets/rgc_motorsports.png
CRANK_IT_UP_ICON_GRAPHIC=/assets/crank_it_up.png
```

`OVERLAY_HOST=127.0.0.1` keeps the overlay and Producer Assist on the broadcast PC only. Use `OVERLAY_HOST=0.0.0.0` when a helper on the same local network or VPN needs to open the Producer Assist link. Camera movement uses a take/release control button so only one producer moves cameras at a time.

For remote league admins in different locations, the recommended v1.0 helper workflow is [Tailscale](https://tailscale.com/download/windows). Install and sign in on the broadcast PC and on the helper admin's PC, make sure both machines are in the same Tailscale network, then set `Remote Producer Assist Access` to `0.0.0.0` in the Studio. The Producer Assist link will prefer the broadcast PC's Tailscale address when available, usually a `100.x.x.x` address. Send that link only to trusted helpers. Keep the OBS/Streamlabs overlay link on `127.0.0.1`. Avoid normal router port forwarding unless you have a separate security plan.

Producer Assist also includes an optional Race Control panel for hosted-race admins. Keep `RACE_ADMIN_MODE=false` unless the broadcaster PC is an iRacing admin in the hosted session. In broadcast-safe mode, Race Control copies the iRacing admin command, such as `!yellow` or `!eol #34`, so the admin can send it without the program popping the iRacing chat box on stream. `RACE_ADMIN_SEND_MODE=open_chat` copies the command and opens iRacing text chat for quick Ctrl+V/Enter. `RACE_ADMIN_SEND_MODE=ui_paste` is testing-only and may show iRacing chat/window on the broadcast. If the broadcast PC is also the streaming PC, any chat-command workflow can interrupt what viewers see. For clean league race control, have a trusted admin use Producer Assist from another PC through Tailscale so race-control chat/admin actions happen away from the broadcast capture. Dangerous actions use confirmation prompts and every command is logged to Producer Feed.

Optional sponsor reads now use the race sponsor slots in the Studio:

```text
USE_SPONSOR_READS=true
RACE_SPONSOR_1_NAME=RGC Motorsports
RACE_SPONSOR_1_LOGO=/assets/rgc_motorsports.png
RACE_SPONSOR_1_READ=
RACE_SPONSOR_2_NAME=
RACE_SPONSOR_2_LOGO=
SPONSOR_READ_CAUSE=Autism Awareness
SPONSOR_READ_CAUSE_LOGO=/assets/autism_awareness.png
```

When enabled, the broadcast rotates up to five race sponsors in order after the pre-race field rundown, during natural caution breaks after replay or pit-road coverage, and during race-update sponsor reads. If a sponsor-specific read is blank, the AI writes a natural read. The cause/awareness message is added to sponsor calls.

Optional RGC Anthem ceremony:

```text
USE_NATIONAL_ANTHEM=true
NATIONAL_ANTHEM_AUDIO=C:\Path\To\rgc_anthem.mp3
NATIONAL_ANTHEM_GRAPHICS=/assets/rgc_motorsports.png,/assets/autism_awareness.png
```

If you start the program during practice or qualifying, the overlay can show the RGC Anthem graphics near the top of the screen and play the configured local audio file once qualifying begins. To play more than one anthem/sponsor song, separate the files with semicolons. The anthem graphic stays up through the qualifying session and clears automatically when the race session starts. The qualifying board stays visible underneath. Once the race session starts, the normal brand graphics cycle cleanly in the title banner. The project does not include an anthem recording; use your own recording or a properly licensed MP3/WAV audio file.

Optional music beds:

```text
STUDIO_VOLUME=65
PRACTICE_MUSIC_PLAYLIST=C:\Path\To\song1.mp3;C:\Path\To\song2.mp3
CAUTION_REPLAY_AUDIO=C:\Path\To\rgc_anthem.mp3
CAUTION_PRESENTATION_GRAPHICS=/assets/rgc_motorsports.png,/assets/autism_awareness.png
```

Practice music starts only during practice when a playlist is configured. Caution replay audio starts only when a caution replay package begins during the race, ducks while Mike, Jeff, or Sarah talk, and stops when race control goes back green or the race ends. Caution graphics are shown during caution sponsor presentation periods. Leave either audio setting blank to disable that music bed.

Then start the broadcast with:

```powershell
python app.py --overlay
```

The app prints the browser-source URL:

```text
Overlay: ON (http://127.0.0.1:8765/overlay)
```

Add that URL to Streamlabs or OBS as a browser source. The page shows a top race banner with the title, sponsor, series, track, and session, plus a left-side leaderboard that updates from iRacing telemetry.

## Run a recorded race

```powershell
python tools\telemetry_recorder.py recordings\race.jsonl
python app.py --replay recordings\race.jsonl --no-voice
```

Replay mode exercises the same race director, detectors, editorial producer, OpenAI renderer, and scheduler as live mode.

## Verify changes

```powershell
python -m pytest
```

Live validation is still required for SDK flag behavior and audio playback changes.

## Current focus

The next production improvements are a managed audio player, stronger incident confirmation, broadcast memory, and camera/replay direction. See [ROADMAP.md](ROADMAP.md).
