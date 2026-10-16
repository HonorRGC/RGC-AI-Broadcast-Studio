# Race Highlights — v1.1.0 guide

## Capture lifecycle (implemented)

Every normal live or native iRacing replay broadcast records telemetry and commentary, including broadcasts without Driver Mode. Playing a previously recorded JSONL uses that existing capture rather than duplicating it. Capture begins when iRacing connects. Studio writes to disk during the session so an unexpected exit retains the material written so far.

Stop Broadcast offers Keep or Discard for the just-stopped worker's captures, including a size estimate. Cancel and closing the dialog keep the files. Discard removes only matching telemetry, commentary events and capture metadata inside this installation's recordings folder. Studio close uses the same flow when stopping its broadcast. Existing recordings, league data and iRacing .rpy files are not removed. Unexpected termination preserves pending captures. Terminal-only runs retain their files.

## Streamlabs highlights player

Open **Race Highlights** in Studio after stopping the normal broadcast. Select the main capture JSONL, transition style and optional graphic, and the highlight sponsor/logo. Fade, slide and diagonal wipe can be selected individually or cycled between segments. Keep the standard RGC overlay browser source visible in Streamlabs; the player waits for that source to receive the cover before seeking.

Load the matching saved .rpy and tick the replay checkbox. The optional incident-marker scan visits iRacing's replay markers, records their incident-camera target, and restores the original replay position afterward. Markers with unknown point values are clearly distinguished from verified incident-count increases; automated visual collision analysis is not implemented.

**Prepare Highlights** reads the capture and generates OpenAI narration and ElevenLabs audio ahead of playback. The configured OpenAI key, ElevenLabs key and Lead voice ID are required. API usage applies. A saved programme and its audio live in `highlights/<job>/`; interrupted narration can be reused when preparing the same job again. The programme preview lists warnings and narration, and estimates the overall duration without forcing a target length.

**Open Highlights Player** starts a separate presentation server and opens Producer Assist. Start recording in Streamlabs, then choose **Start Highlights** in Producer. A five-second countdown precedes the introduction. Producer also provides Pause, Resume / Retry Current Clip and Stop Highlights. Resume restarts the current segment so its voice and replay remain aligned. The ordinary live director and return-live commands are not used in this mode.

The player confirms the replay session/time, camera target and settling delay under the transition cover. An unavailable action clip is skipped under cover after its seek times out; persistent playback drift also skips forward. Missing overlay delivery still stops safely before seeking. The closing recap plays without a replay seek. The current capture must be unchanged since preparation. New captures include grid provenance and race session IDs to improve replay identity checks. Old captures use the available track and replay-time checks.

The complete verified lineup uses ten-driver pages, highlighting and following each driver without transitions between drivers or pages. Normal leaderboards and driver cards are hidden during action. The recap has a center podium, full-field results on the left and five race statistics on the right. Results show twenty drivers, preserving the top fifteen and cycling the remaining five rows. The sponsor sits upper right and the RGC stamp remains lower left. The player holds an end slate on completion; Streamlabs owns the recording and final video export. Studio does not control Streamlabs or export an MP4 itself.

Automated and browser tests cover selection, narration caching, replay scanning, pause/retry, transition delivery and failed seeks. Saved-replay testing informed the seek, timing and clip-selection fixes; replay availability and telemetry coverage still vary by recording.

## Title, music and costs

Enter an optional title in Race Highlights. It stays across the top during playback. Load Prepared can update only the title before opening the player, without regenerating narration. Practice music plays continuously at ten percent and loops back to the first song; it stops at programme completion or Stop Highlights.

Preparation uses OpenAI and ElevenLabs credits. Prepared playback and title/camera edits do not generate new narration calls. Changing clip facts or timing requires preparation again for the affected audio; compatible completed segments are reused.

## Editorial requirements

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
