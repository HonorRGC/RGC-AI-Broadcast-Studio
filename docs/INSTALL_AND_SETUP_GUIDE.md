# RGC AI Broadcast Studio install and setup guide

This guide is for a league admin, broadcaster, or tester setting up RGC AI Broadcast Studio on a Windows PC.

The goal is simple:

```text
Install the studio → add your keys and voices → set up the overlay → save a profile → start a broadcast
```

## 1. What you need before installing

You need:

- Windows 10 or Windows 11
- iRacing installed
- Python 3.11 or newer
- Streamlabs, OBS, or another broadcast tool that supports browser sources
- An OpenAI API key if you want AI-written commentary
- An ElevenLabs API key and voice IDs if you want spoken AI broadcasters

If you only want overlays, cameras, and race information for a human broadcaster, start the broadcast and use **Producer Assist** to turn OpenAI and ElevenLabs off.

## 2. Install Python

1. Go to the official Python download page:

   <https://www.python.org/downloads/>

2. Download Python 3.11 or newer.
3. Run the installer.
4. Important: check this box during install:

   ```text
   Add python.exe to PATH
   ```

5. Finish the install.

If Python is not installed correctly, `install_studio.bat` will tell you. The installer tries Python 3.11 first, then any available Python 3 runtime. Newer Python versions are okay as long as they can create a virtual environment.

## 3. Install RGC AI Broadcast Studio

1. Download or receive the RGC AI Broadcast Studio ZIP.
2. Right-click the ZIP and choose **Extract All**.
3. Extract it somewhere simple, for example:

   ```text
   Documents\RGC-AI-Broadcast-Studio
   ```

4. Open the extracted folder.
5. Double-click:

   ```text
   install_studio.bat
   ```

6. Wait for the setup to finish.

The installer will:

- create a local Python environment
- install the studio dependencies
- create the starting settings file
- create a desktop shortcut with the RGC AI Broadcast Studio icon
- open RGC AI Broadcast Studio

After install, you can open the program from the desktop shortcut:

```text
RGC AI Broadcast Studio
```

## 4. Create an OpenAI API key

OpenAI is used for the AI broadcast writing. It creates the commentary text that Mike, Jeff, and Sarah read.

1. Go to the OpenAI API keys page:

   <https://platform.openai.com/api-keys>

2. Sign in or create an OpenAI account.
3. Create a new API key.
4. Copy the key.
5. In RGC AI Broadcast Studio, paste it into:

   ```text
   OPENAI_API_KEY
   ```

6. Make sure OpenAI is turned on if you want full AI commentary:

   ```text
   USE_OPENAI = true
   ```

Official OpenAI API quickstart:

<https://developers.openai.com/api/docs/quickstart>

Important: do not share your OpenAI API key, do not post it in Discord, and do not commit it to GitHub.

## 5. Create an ElevenLabs API key

ElevenLabs is used for the spoken broadcaster voices.

1. Go to ElevenLabs:

   <https://elevenlabs.io/>

2. Sign in or create an account.
3. Open the API keys page:

   <https://elevenlabs.io/app/developers/api-keys>

4. Create or copy your API key.
5. In RGC AI Broadcast Studio, paste it into:

   ```text
   ELEVENLABS_API_KEY
   ```

6. Make sure ElevenLabs is turned on if you want spoken voices:

   ```text
   USE_ELEVENLABS = true
   ```

Important: do not share your ElevenLabs API key.

## 6. Add ElevenLabs voice IDs

RGC AI Broadcast Studio uses three voice slots:

- Lead announcer
- Color analyst
- Pit reporter

In the launcher, fill in:

```text
LEAD_VOICE_ID
COLOR_VOICE_ID
PIT_VOICE_ID
```

To find a voice ID:

1. Open ElevenLabs.
2. Go to your voices / voice library.
3. Choose the voice you want to use.
4. Copy the voice ID.
5. Paste it into the matching voice field in the studio.

ElevenLabs voice API reference:

<https://elevenlabs.io/docs/api-reference/voices/search>

Recommended setup:

- Lead announcer: main play-by-play voice
- Color analyst: second broadcaster / race analysis voice
- Pit reporter: pit road and strategy voice

After adding voices, use the voice test in the launcher if available, or start a short test broadcast to confirm audio works.

## 7. Set up the broadcast overlay

The overlay is a local browser page that works in Streamlabs, OBS, or any broadcast program that supports browser sources.

In RGC AI Broadcast Studio:

1. Go to the Broadcast Settings area.
2. Find the Streamlabs / OBS overlay link:

   ```text
   http://127.0.0.1:8765/overlay
   ```

3. Click **Copy Overlay Link**.

In Streamlabs or OBS:

1. Add a new **Browser Source**.
2. Paste the overlay link.
3. Set the browser source size to:

   ```text
   1920 x 1080
   ```

4. Put the browser source above your iRacing capture.

The overlay will only show live data while the broadcast program is running.

## 8. Add event, sponsor, and graphics

In the launcher, fill in:

- Event title
- Race sponsor
- Series name
- Sponsor / brand logos
- Crank It Up sponsor graphic
- Anthem graphics if used
- Caution presentation graphics if used

Use the logo buttons in the launcher to choose images from your PC. The program copies those graphics into the overlay assets folder for you.

Good image types:

- `.png`
- `.jpg`
- `.jpeg`
- `.webp`

## 9. Set up league files and Sim Racer Hub

For official race testing, league files are optional.

For league races, use the **League / Sim Racer Hub** tab.

Recommended Sim Racer Hub URL:

```text
https://simracerhub.com
```

Then fill in:

```text
League ID
Series ID
Season ID
```

Use:

- **Preview** first, to make sure the import looks right.
- **Import Drivers** to create or update `league\drivers.csv`.
- **Import Stats** with Career Mode off to create or update `league\season.csv`.
- **Import Stats** with Career Mode on to create or update `league\career.csv`.
- **Import Schedule** to create or update `league\race_schedule.csv`.

The driver import is designed to preserve manual notes. That means you can add hometown, sponsor, team, driving style, or other notes later without the import wiping them out.

If schedule import cannot find any rows, paste the first race's Sim Racer Hub `schedule_id` into **First Race Schedule ID** and run **Import Schedule** again. Sim Racer Hub usually numbers the next races one at a time, so the Studio can build the remaining IDs automatically from the season race order.

For automatic post-race Discord results links, fill out the **Race Schedule CSV** for the profile. The default file is:

```text
league/race_schedule.csv
```

Use one row per race:

```csv
track_name,schedule_id,results_url,notes
Michigan International Speedway,356761,,Race 1
Homestead Miami Speedway,356762,,Race 2
```

If `results_url` is blank, the Studio builds the Sim Racer Hub race-results link from `schedule_id`. If `Race Results Link` is filled in under Discord Race Report, that manual link wins for that event.

## 10. Set up event sponsors

In **Broadcast Settings**, use the **Event Sponsors / Overlay Links** section.

Recommended setup:

```text
Overlay Event Title = race name
Series Name = league or series name
Series Logo = optional series logo
Cause / Awareness Read = optional cause, such as Autism Awareness
Cause / Awareness Logo = optional cause logo
Sponsor 1 Name / Logo / Spoken Read / Commercial Video
Sponsor 2 Name / Logo / Spoken Read / Commercial Video
Sponsor 3 Name / Logo / Spoken Read / Commercial Video
Sponsor 4 Name / Logo / Spoken Read / Commercial Video
Sponsor 5 Name / Logo / Spoken Read / Commercial Video
```

Sponsor names are used in order for spoken reads during pre-race, caution breaks, and race updates. Choose one logo per sponsor; those logos rotate in the title overlay in sponsor order and are shown when a sponsor is mentioned. If a sponsor read is blank, the AI writes a natural sponsor mention. If a cause/awareness read is set, it is added to sponsor calls. If a sponsor commercial video is set, the broadcaster will make the sponsor read and then the overlay can play that video full-screen.

The **Streamlabs / OBS Link** and **Producer Assist / Remote Admin Link** are in this same area so overlay setup and remote producer setup stay easy to find.

## 11. Save settings and create a profile

After filling out the launcher:

1. Click **Save Settings**.
2. Enter a profile name, for example:

   ```text
   WFO Truck League
   ```

3. Click **Save Profile**.

Profiles are useful because you can keep separate setups, such as:

- League race
- Official race testing
- Human-broadcaster defaults
- No-voice overlay/camera defaults

Before race night, load the correct profile and check the Broadcast Health panel.

## 12. Start the broadcast

Start Broadcast launches:

- AI commentary controls
- ElevenLabs voice controls
- Producer Assist
- camera direction
- overlay graphics
- race control and caution handling

Click:

```text
Start Broadcast
```

Then open Producer Assist if you want to switch between AI broadcast and human-broadcaster control during the same running session.

Race Control note: `Race Admin Send Mode = clipboard` is the broadcast-safe default. It copies commands like `!yellow` or `!eol #34` so the admin can send them without the program opening iRacing chat on stream. `open_chat` copies the command and opens iRacing text chat for quick Ctrl+V/Enter. `ui_paste` is testing-only and may show the iRacing window/chat box in the broadcast capture.

Important broadcast warning: if the same PC is running the stream/recording and also sends iRacing chat/admin commands, the chat box or iRacing window can interrupt what viewers see. For the cleanest league production, use a second trusted race-control admin on another PC. Have that admin connect to Producer Assist through Tailscale and handle race-control commands away from the broadcast capture.

Optional Discord race report:

1. In Discord, open the results channel settings.
2. Create a webhook for that channel.
3. Copy the webhook URL.
4. In RGC AI Broadcast Studio, set:

   ```text
   Discord Race Report = true
   Race Report Webhook URL = your Discord webhook URL
   Use OpenAI Race Recap = true
   Race Results Link = optional manual Sim Racer Hub race-results URL
   Championship Standings Link = optional manual league standings URL
   ```

After the race, the Studio waits for the finishing order to stabilize, then posts a Discord recap with a short race breakdown, the top ten, biggest movers, available race stats, and official results/championship links. If the manual Race Results Link is blank, the Studio can use the Race Schedule CSV to find the matching Sim Racer Hub race link automatically. If the manual Championship Standings Link is blank, the Studio can build the Sim Racer Hub standings link from the Season ID and that race's schedule ID. The Discord interview bot fields are separate and can stay blank for now.

## 12. Remote Producer Assist with Tailscale

Use Tailscale when a trusted admin in another location needs to help with Producer Assist, cameras, notes, incident review, or race control.

Official Tailscale Windows download:

<https://tailscale.com/download/windows>

Setup:

1. Install Tailscale on the broadcast PC.
2. Install Tailscale on the helper admin's PC.
3. Sign both PCs into the same Tailscale account/network.
4. In RGC AI Broadcast Studio, set:

   ```text
   Remote Producer Assist Access = 0.0.0.0
   ```

5. Click **Save Settings**.
6. Start the broadcast.
7. Copy the **Producer Assist / Remote Admin Link** from the launcher.
8. Send that link only to trusted helpers on your Tailscale network.

Important:

- Keep the Streamlabs / OBS overlay link as `http://127.0.0.1:8765/overlay` on the broadcast PC.
- Tailscale is only for the private Producer Assist control-room link.
- Do not use normal router port forwarding unless you have a separate security plan.
- Camera control still uses the take/release button so only one producer moves cameras at a time.

## 13. Recommended race-night flow

1. Open iRacing.
2. Join the session as a spectator, admin, or driver depending on your workflow.
3. Open RGC AI Broadcast Studio.
4. Load your saved profile.
5. Open Streamlabs or OBS.
6. Confirm the overlay browser source is visible.
7. Check Broadcast Health.
8. Start the broadcast during practice.
9. Let the studio detect practice, qualifying, and race.
10. Stop the broadcast after the race or after post-race coverage.

## 14. Updating to a newer build

For now, updates are handled by receiving a newer ZIP.

Recommended update method:

1. Extract the new ZIP into a new folder.
2. Run:

   ```text
   install_studio.bat
   ```

3. Open the launcher.
4. Re-enter settings or recreate the profile if needed.

Later versions may add a true installer/updater.

## 15. Troubleshooting

### The program will not install

Check that Python 3.11 or newer is installed and that **Add python.exe to PATH** was checked during Python install. If the Python launcher says no 3.11 runtime is installed, either install Python from python.org or run `py install 3.11` in PowerShell.

### No AI commentary

Check:

- `USE_OPENAI` is on
- OpenAI API key is entered
- internet connection works
- OpenAI account has API access and billing set up if required

### No spoken voices

Check:

- `USE_ELEVENLABS` is on
- ElevenLabs API key is entered
- voice IDs are entered
- Windows audio output is correct
- ElevenLabs account has enough usage available

### Overlay does not show

Check:

- broadcast is started
- browser source URL is `http://127.0.0.1:8765/overlay`
- browser source size is `1920 x 1080`
- overlay source is above the iRacing capture

### Helper cannot open Producer Assist

Check:

- Tailscale is installed on both PCs.
- Both PCs are signed into the same Tailscale network.
- Broadcast Settings has `Remote Producer Assist Access = 0.0.0.0`.
- The broadcast is started.
- The helper is using the Producer Assist link, not the OBS overlay link.

### Cameras do not move

Check:

- iRacing is running
- you are connected to a session
- camera mode is enabled in the launcher
- iRacing replay/camera controls are not blocked by another tool

### Race Control button does not instantly throw a caution

Check `Race Admin Send Mode`.

- `clipboard` is broadcast-safe. It copies the command, but does not visibly open/send chat.
- `open_chat` copies the command and opens iRacing text chat for quick Ctrl+V/Enter.
- `ui_paste` tries to paste/send the command through iRacing chat and may show the chat box/window on stream.

Until a true hidden iRacing admin-command method is confirmed, use clipboard mode for live broadcasts. If you need fast live race-control decisions without risking the broadcast screen, use a trusted remote admin through Producer Assist/Tailscale on a separate PC.

## 16. Safety notes

- Never share API keys publicly.
- Do not stream your launcher while keys are visible.
- Do not send your personal `.env` file to another user.
- Each league/admin should use their own OpenAI and ElevenLabs accounts.
- Use Producer Assist to turn OpenAI and ElevenLabs off if you want to test overlays and cameras without AI costs.
