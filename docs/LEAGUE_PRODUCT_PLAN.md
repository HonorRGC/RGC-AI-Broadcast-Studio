# League Product and Broadcast Overlay Plan

This document describes the next product layer for RGC AI Broadcast Studio: turning the current race-calling engine into something a league admin can download, configure, and run for a professional-looking broadcast.

## Product goal

A league admin should be able to:

1. Download RGC AI Broadcast Studio.
2. Add their OpenAI and ElevenLabs keys.
3. Choose or paste voice IDs for Lead, Analyst, and Pit Reporter.
4. Add league, race, sponsor, and driver information.
5. Add Streamlabs, OBS, or any browser-source overlay.
6. Join/spectate the iRacing session.
7. Press play and get a believable broadcast with commentary, cameras, replays, graphics, and sponsor presentation.

The overlay and league-data systems should not depend on Streamlabs specifically. Streamlabs, OBS, XSplit, and most production tools can all use a browser source, so the safest target is a local web overlay.

## Recommended overlay architecture

Use a local browser overlay served by the app.

```text
iRacing telemetry
    -> BroadcastEngine
    -> OverlayState
    -> local web server
    -> Browser Source in Streamlabs / OBS / any production tool
```

The app should run a small local server, for example:

```text
http://localhost:8765/overlay
```

The league admin adds that URL as a browser source in Streamlabs. This keeps the graphics platform-neutral.

## Overlay package

The first graphics package should be simple, clean, and NASCAR-style:

- Top banner
  - league name
  - track name
  - race name or sponsor
  - lap count
  - flag state
- Left-side leaderboard
  - position
  - car number
  - driver name
  - gap or interval when reliable
  - pit/incident/status icons later
- Lower-third driver card
  - driver name
  - car number
  - hometown/state/country
  - sponsor
  - current position
  - movement from start
- Segment graphics
  - starting lineup
  - quarter-race field reset
  - top ten finish
  - pit stop summary
  - caution/replay banner
- Sponsor graphic
  - small rotating bug
  - full-width sponsor read card
  - optional commercial break slate

## Overlay data source

The overlay should not scrape console output. It should receive structured state from the broadcast engine.

Suggested internal model:

```text
OverlayState
  race:
    league_name
    event_name
    track_name
    sponsor_name
    lap
    total_laps
    flag_state
  leaderboard:
    position
    car_number
    driver_name
    gap
    interval
    last_pit_lap
    status
  focused_driver:
    car_number
    name
    hometown
    region
    country
    sponsor
    position
    starting_position
    movement
  segment:
    type
    title
    rows
  replay:
    active
    angle
    label
```

The first implementation can update a JSON endpoint every tick:

```text
GET /overlay/state.json
```

Later, this can become WebSocket updates for smoother animation.

## League configuration

The league admin needs a place to enter non-iRacing context. Start with editable JSON or YAML files, then later build a simple setup UI.

Recommended files:

```text
league/
  league.yaml
  drivers.csv
  sponsors.yaml
  events.yaml
  assets/
    league_logo.png
    sponsor_logos/
    commercials/
```

### league.yaml

```yaml
league_name: "RGC Racing League"
short_name: "RGC"
default_country: "United States"
broadcast_brand: "RGC AI Broadcast"
lead_name: "Mike"
analyst_name: "Jeff"
pit_reporter_name: "Sarah"
primary_color: "#e10600"
secondary_color: "#111111"
```

### drivers.csv

```csv
car_number,driver_name,hometown,state,country,sponsor,driving_style,notes
46,Michael Hinkle,Charlotte,NC,USA,Acme Tools,aggressive on restarts,"Strong short-run pace"
19,Alex Gustafson,Des Moines,IA,USA,Northline Motors,smooth tire saver,"Usually gets stronger late"
```

### sponsors.yaml

```yaml
sponsors:
  - name: "Acme Tools"
    logo: "assets/sponsor_logos/acme.png"
    reads:
      - "Tonight's race coverage is presented by Acme Tools."
      - "Acme Tools, proud supporter of grassroots sim racing."
  - name: "Northline Motors"
    logo: "assets/sponsor_logos/northline.png"
    reads:
      - "Northline Motors brings you tonight's restart zone."
```

### events.yaml

```yaml
events:
  - track: "Homestead Miami Speedway"
    race_name: "RGC Homestead 100"
    presenting_sponsor: "Acme Tools"
    scheduled_laps: 100
    commercial_videos:
      - "assets/commercials/acme_15s.mp4"
```

## Driver context in commentary

Driver facts should be treated as broadcast seasoning, not spam.

Good usage:

- “Michael Hinkle out of Charlotte has always been strong on restarts, and this is exactly the kind of situation he likes.”
- “Alex Gustafson is known as a tire saver, so watch whether that long-run style starts to pay off.”
- “The 46 carries Acme Tools on the quarter panel tonight.”

Rules:

- Do not repeat the same hometown/style fact more than once or twice per race.
- Use driver facts when the driver is already relevant to the race story.
- Avoid forcing context into every call.
- If a fact is missing, say nothing instead of inventing it.

## Sponsor and commercial handling

Sponsor reads should be scheduled like broadcast items.

Possible triggers:

- pre-race welcome
- pace laps
- caution periods
- one-to-green
- halfway
- post-race

Commercial videos are more complex because the app must coordinate:

- play commercial video overlay/source
- lower or pause booth audio
- keep tracking live telemetry
- return to race if green flag comes back or major incident happens

First version should support sponsor reads and static sponsor graphics. Commercial video should come later after managed audio and overlay control exist.

## Setup experience

### Phase 1: text-file setup

Provide:

- `.env.example`
- `league.example/`
- `docs/LEAGUE_SETUP_GUIDE.md`
- validation command:

```powershell
python tools\validate_league_config.py
```

### Phase 2: setup wizard

Add a command-line wizard:

```powershell
python tools\setup_league.py
```

It asks:

- league name
- broadcast names
- OpenAI key
- ElevenLabs key
- voice IDs
- primary color
- sponsor names
- driver CSV path

### Phase 3: desktop/admin UI

Later, create a simple UI with tabs:

- API keys
- Voices
- League info
- Drivers
- Sponsors
- Overlay preview
- Test voice
- Start broadcast

## Implementation phases

### Phase A: League data foundation

- Add `league/` sample files.
- Add `LeagueConfig` loader.
- Add `DriverProfile` model.
- Merge driver profile data into `driver_lookup`.
- Add tests for config loading and missing fields.

### Phase B: Commentary integration

- Teach `RaceIntelligence` / `OpenAIDirector` about driver profile context.
- Add memory so hometown/style/sponsor facts are not repeated.
- Add sponsor read scheduling.

### Phase C: Overlay state

- Add `OverlayState` model.
- Add `OverlayDirector` that converts telemetry and broadcast items into overlay state.
- Add JSON endpoint.
- Add a simple HTML/CSS overlay.

### Phase D: Streamlabs/OBS guide

- Add a setup guide:
  - add browser source
  - set width/height
  - make background transparent
  - test overlay with replay mode

### Phase E: Managed audio and commercial readiness

- Replace `os.startfile` voice playback with a managed audio player.
- Track playback completion.
- Support stop/interruption for race control.
- Add commercial/sponsor video playback after managed audio exists.

## First build target

The best next product target is:

1. Load `league/drivers.csv`.
2. Use driver hometown/style/sponsor facts in commentary.
3. Serve a simple overlay page with:
   - top banner
   - left leaderboard
   - lower-third focused driver card
4. Add a Streamlabs/OBS setup guide.

This would make the project feel like a league product instead of only a Python script.
