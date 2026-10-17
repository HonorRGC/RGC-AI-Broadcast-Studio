# Race Highlights — v1.1.0 guide

## Capture lifecycle (implemented)

Every normal live or native iRacing replay broadcast records telemetry and commentary, including broadcasts without Driver Mode. Playing a previously recorded JSONL uses that existing capture rather than duplicating it. Capture begins when iRacing connects. Studio writes to disk during the session so an unexpected exit retains the material written so far.

Stop Broadcast offers Keep or Discard for the just-stopped worker's captures, including a size estimate. Cancel and closing the dialog keep the files. Discard removes matching telemetry, commentary events, capture metadata and saved car images inside this installation's recordings folder. Studio close uses the same flow when stopping its broadcast. Existing recordings, league data and iRacing .rpy files are not removed. Unexpected termination preserves pending captures. Terminal-only runs retain their files.

## Streamlabs highlights player

Open **Race Highlights** in Studio after stopping the normal broadcast. Select the main capture JSONL, transition style and optional graphic, and the highlight sponsor/logo. Fade, slide and diagonal wipe can be selected individually or cycled between segments. Keep the standard RGC overlay browser source visible in Streamlabs; the player waits for that source to receive the cover before seeking.

Load the matching saved .rpy and tick the replay checkbox. The optional incident-marker scan visits iRacing's replay markers, records their incident-camera target, and restores the original replay position afterward. Markers with unknown point values are clearly distinguished from verified incident-count increases; automated visual collision analysis is not implemented.

**Prepare Highlights** reads the capture and generates OpenAI narration and ElevenLabs audio ahead of playback. The configured OpenAI key, ElevenLabs key and Lead voice ID are required. API usage applies. A saved programme and its audio live in `highlights/<job>/`; interrupted narration can be reused when preparing the same job again. The programme preview lists warnings and narration, and estimates the overall duration without forcing a target length.

**Open Highlights Player** starts a separate presentation server and opens Producer Assist. Start recording in Streamlabs, then choose **Start Highlights** in Producer. A five-second countdown precedes the introduction. Producer also provides Pause, Resume / Retry Current Clip and Stop Highlights. Resume restarts the current segment so its voice and replay remain aligned. The ordinary live director and return-live commands are not used in this mode.

The player confirms the replay session/time, camera target and settling delay under the transition cover. An unavailable action clip is skipped under cover after its seek times out; persistent playback drift also skips forward. Missing overlay delivery still stops safely before seeking. The closing recap plays without a replay seek. The current capture must be unchanged since preparation. New captures include grid provenance and race session IDs to improve replay identity checks. Old captures use the available track and replay-time checks.

The complete verified lineup uses ten-driver pages, highlighting and following each driver without transitions between drivers or pages. Normal leaderboards and driver cards are hidden during action. The recap has a center podium, full-field results on the left and five race statistics on the right. Results show twenty drivers, preserving the top fifteen and cycling the remaining five rows. The sponsor sits upper right and the RGC stamp remains lower left. The player holds an end slate on completion; Streamlabs owns the recording and final video export. Studio does not control Streamlabs or export an MP4 itself.

Automated and browser tests cover selection, narration caching, replay scanning, pause/retry, transition delivery and failed seeks. Saved-replay testing informed the seek, timing and clip-selection fixes; replay availability and telemetry coverage still vary by recording.

## Title, music and costs

**Full-screen transition artwork** accepts a league image for the complete between-clip slate. A 1920x1080 image fills the frame without cropping; other aspect ratios fill the frame by cropping the edges. This replaces the slate background and default border while retaining the clip title, center graphic and sponsor branding, and uses the selected entry/exit transition. Results recap and error screens retain their regular layout. Leave blank to restore the RGC slate. This visual setting can be changed through Load Prepared without regenerating narration.

Center transitions and the upper-right clip sponsor have independent editable sponsor names and graphic choices. Type a custom name or select a profile sponsor. Load Prepared and Open Highlights Player save these visual edits without regenerating speech; prepare again to change spoken sponsor mentions. Transition styles animate both onto the slate and off it when revealing the clip.

**Left recap sponsor** adds an optional, separate name and logo only on the closing race recap. The upper-right clip sponsor remains on the right. Both sponsor areas sit above the lowered results and race highlights panels, with room for twenty results rows and the bottom-left RGC stamp. Leave the left fields blank to hide that sponsor area. Load Prepared, choose the sponsor and Open Highlights Player to apply it without preparing narration again.

For new captures, run SIMRacingApps and Trading Paints with iRacing before starting the original broadcast, with Use SIMRacingApps Car Graphics enabled. Studio saves the actual PNG car renders for the whole field in the background, including Driver Mode while you race. It retries unavailable images during the broadcast without blocking telemetry polling. The saved images live in a folder beside the capture, for example `broadcast_capture_2026-10-17_19-00-00.images/`. Keep this folder with the JSONL and other capture files if moving the recording. Capture metadata and the stop log show the saved image count.

Highlights use these saved pictures and number styles for the lineup and podium without contacting SIMRacingApps or rebuilding the images. SIMRacingApps is not needed during preparation or playback for drivers with archived images. Older captures and missing images still use the current matching replay's render resolver, so leave SIMRacingApps and the matching paint files available for those. An older JSONL cannot recover the exact original image pixels if they were never saved.

Highlights lineup and podium images now use the full broadcast's render resolver. Live replay driver design strings provide per-driver body/number styling and wheel finish/color; new captures retain those design strings too. Local fallback renders do not copy rim or number styling from another driver's cached request. Existing captures can obtain these fields from the loaded matching replay without rebuilding narration. Accurate custom paint still depends on the matching paint files being available locally.

Enter an optional title in Race Highlights. It stays across the top during playback. Load Prepared can update only the title before opening the player, without regenerating narration. Practice music plays continuously at ten percent and loops back to the first song; it stops at programme completion or Stop Highlights.

Preparation uses OpenAI and ElevenLabs credits. Prepared playback and title/camera edits do not generate new narration calls. Changing clip facts or timing requires preparation again for the affected audio; compatible completed segments are reused.

## Editorial requirements

Long-race programmes aim near eighteen minutes, with a measured-audio check against twenty minutes. Starts/restarts are longer and use camera cues for the closest available on-track racing in P5-P10; they end early if another yellow interrupts. Front-running overtakes rank higher, with a small allowance for rear-field recognition. The last recorded on-track lead change, start, restarts, cautions, key pit stops and finish are protected. Quiet races are not padded to fifteen minutes; unusually large essential coverage may exceed twenty minutes and displays a warning.

Pit coverage summarizes each observed window with its first car and up to five early followers. The driver leading when the window opened gets a separate short stop clip if their arrival is later. This replaces repeated reports for every pit-entry lap and excludes cars already parked on pit road. New windows are separated by an arrival gap or a maximum four-minute grouping span, rather than assuming a fuel range.

- Post-race production from the full saved .rpy plus matching telemetry capture, including leagues and officials.
- A concise race introduction and existing RGC starting-lineup graphic, ten drivers per page, based on verified race grid data. Do not replace missing starting positions with current running order.
- No persistent leaderboard. Selected highlight sponsor logo at upper right and RGC AI Broadcast Studio branding at lower left.
- Narrate each selected event with its lap, named drivers and verified action. Build one coherent race story rather than a list of unrelated clips.
- Include on-track lead passes; exclude pit-cycle lead changes from pass counts. Include well-supported battles and overtakes elsewhere in the field, especially a driver's progress through traffic.
- Seek incident markers and review available footage. Include verified incident-count increases of two or more where exposed. An accumulated increase is not automatically one 2x event, and unavailable counts are not zero incident evidence. Group markers referring to the same crash.
- Relate incidents to cautions with qualified wording when cause is unconfirmed: "This may have contributed to the lap 34 caution." Timing alone does not establish causation or fault.
- Cover meaningful pit cycles and damage retirements only where supported; a stationary car, pit visit, disconnect or disappearance is not proof of damage retirement.
- Finish with the decisive late action, winner and results.
- Generate fresh OpenAI narration and ElevenLabs audio suited to the clips rather than replaying live commentary without editing.
- Story-driven duration with no forced five- or fifteen-minute limit. Trim repetition and quiet footage while retaining important events.
- Use resumable production jobs, verified seeks and camera settling, capture progress/cancel controls, narration timing, Streamlabs audio capture and video export. Do not claim a complete race when the source recording is partial.

## Known limits

### Producer-selected caution drivers

Open Highlights Player with the matching capture, then use **Caution Review Drivers** in Producer Assist before starting playback. Each yellow lists its lap and replay time with a dropdown of the race drivers. A selection steers the review to that car with a twenty-second lookback; **Automatic detection** clears it. Choices persist per race under `recordings/caution-plans/` and are also used by broadcasts from the matching captured replay. Native saved-replay broadcasts can reuse an existing plan when iRacing reports replay mode and the same race session ID. Live sessions do not apply these overrides.

Changing a selection does not make paid API calls or replace prepared audio. Prepare again to update the caution narration for the chosen driver. The selection identifies the producer's review subject; commentary does not invent contact or fault.

Incident counts are not guaranteed for every driver. A replay marker is not proof of a 2x/4x, contact, fault, or caution causation. The player does not perform visual video analysis, so scripts stay within recorded facts. Race-lap labels use leader progress when the focused driver is lapped. Persistent same-lap close-running order changes are candidates for overtakes; recent pit stops are excluded. At most two nearby overtakes share a clip; pit reports and restarts remain separate. One incident can share its related caution review.

Partial captures are explicitly marked and cannot supply an unrecorded finish or missing lead changes. Captures combining different tracks/race session IDs are rejected. If no verified grid exists, lineup pages are omitted. Damage retirements require an explicit recorded reason; stopped or disconnected cars are not assumed damaged.

Streamlabs should capture iRacing, the overlay browser source, game audio and Studio's audio output as in a normal broadcast. Keep the overlay visible during transitions. Preparation may take several minutes and uses online service credits; gameplay footage is still rendered by iRacing during playback.

Grid introductions use Rear Chase with Far Chase/Chase fallbacks. Start/restart narration describes the race rather than explaining camera position choices. Caution narration briefly introduces the yellow and the producer-selected review driver, or a general review when Automatic is selected. Clip captions retain their subject (for example, Lap 27 · Pit Stops) as the lap updates. Finish coverage starts forty seconds before the first confirmed finish, limited by the available capture.
