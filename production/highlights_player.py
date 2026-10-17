"""Seek-confirmed highlights presentation; Streamlabs records the output."""
import json
import time
from bisect import bisect_right
from pathlib import Path


STYLES = ("fade", "slide", "wipe")


class HighlightsPlayer:
    def __init__(self, job, controller, server, audio, job_dir, clock=None, source=None, music=None, playlist=None):
        from production.highlights import selected_highlights_job
        job = selected_highlights_job(job)
        if source:
            from production.highlights import restart_camera_cues
            samples = [s for s in source.snapshots if s.session_num == job["session_num"]]
            segments = []
            for original in job["segments"]:
                segment = dict(original)
                start = next((e for e in segment.get("events", []) if e["kind"] in ("start", "restart")), None)
                if start:
                    segment["camera_cues"] = restart_camera_cues(samples, start["time"], segment["end"])
                    if segment["camera_cues"]:
                        segment["car_idx"] = segment["camera_cues"][0]["car_idx"]
                segments.append(segment)
            job = dict(job, segments=segments)
        self.job, self.controller, self.server, self.audio = job, controller, server, audio
        self.job_dir, self.clock = Path(job_dir).resolve(), clock or time.monotonic
        self.source = source
        from production.capture_images import archived_entries
        self.image_root, self.saved_images = archived_entries(job.get("source") or self.job_dir / "missing.jsonl")
        self.server.capture_image_dir = self.image_root
        self.music, self.playlist = music, list(playlist or [])
        self.seamless_lineup = False
        self.drift_since = None
        self.index, self.stage, self.message = 0, "armed", "Start recording in Streamlabs, then Start Highlights."
        self.changed_at, self.started_at, self.deadline = self.clock(), 0, 0
        self.transition_id, self.confirmations = 0, 0
        self.group = "TV1"
        self.last_camera_change = 0
        self.indices = sorted((float(s.session_time), i) for i, s in enumerate(source.snapshots)
                              if s.session_num == job["session_num"]) if source else []
        self.publish()

    @property
    def segment(self):
        return self.job["segments"][self.index]

    @property
    def seek_time(self):
        # The first race frame can still report the preceding session in iRacing.
        # Static opening graphics need a race frame, not that exact boundary.
        start = float(self.segment["start"])
        if self.segment["kind"] == "lineup":
            return max(60.0, start)
        return max(2.0, start) if self.segment["kind"] == "intro" else start

    def style(self):
        choice = self.job.get("options", {}).get("transition", "cycle")
        return STYLES[self.index % len(STYLES)] if choice == "cycle" else choice if choice in STYLES else "fade"

    def publish(self):
        segment = self.segment
        cover = self.stage != "playing" or segment["kind"] in ("intro", "outro") or getattr(self, "holding_frame", False)
        if self.stage == "camera_wait" and self.seamless_lineup:
            cover = False
        options = self.job.get("options", {})
        data = {"active": True, "stage": self.stage, "cover": cover, "segment_kind": segment["kind"], "title": segment["title"],
                "message": self.message, "progress": f"{self.index + 1} / {len(self.job['segments'])}",
                "transition": self.style(), "transition_id": self.transition_id,
                "graphic": options.get("transition_graphic", ""),
                "full_screen_graphic": options.get("full_screen_graphic", ""),
                "transition_sponsor": options.get("transition_sponsor", ""),
                "sponsor_logo": options.get("sponsor_logo", ""), "sponsor": options.get("sponsor", ""),
                "recap_sponsor": options.get("recap_sponsor", ""), "recap_sponsor_logo": options.get("recap_sponsor_logo", ""),
                "track": self.job.get("track", ""), "partial": self.job.get("partial", False)}
        data["programme_title"] = str(options.get("title") or "").strip()[:160]
        if segment["kind"] == "outro":
            data["recap"] = self.job.get("recap", {})
        with self.server.lock:
            self.server.highlights = data

    def stop_media(self, stop_music=False):
        self.audio.stop()
        if stop_music and self.music:
            self.music.stop()
        self.controller.pause_replay()

    def command(self, command):
        if command == "highlights_start" and self.stage in ("armed", "complete", "cancelled"):
            self.index = 0
            self.stage, self.changed_at = "countdown", self.clock()
            self.message = "Highlights begin in five seconds."
        elif command == "highlights_pause" and self.stage not in ("armed", "complete", "cancelled"):
            self.stop_media()
            self.stage, self.message = "paused", "Paused. Resume will replay the current highlight from its beginning."
        elif command == "highlights_resume" and self.stage in ("paused", "error"):
            self.begin_segment()
        elif command == "highlights_cancel":
            self.stop_media(stop_music=True)
            self.stage, self.message = "cancelled", "Highlights stopped. Your prepared programme is saved."
        self.publish()

    def fail(self, message):
        self.stop_media()
        self.stage, self.message = "error", message + " The transition stays on screen. Resume retries this highlight."
        self.publish()

    def skip_current(self, reason):
        diagnostic = {"segment": self.index + 1, "reason": reason, "action": "skip",
                      "replay_time": self.controller.get_replay_session_time(),
                      "replay_session": self.controller.get_replay_session_num()}
        with (self.job_dir / "playback-diagnostics.jsonl").open("a", encoding="utf-8") as log:
            log.write(json.dumps(diagnostic) + "\n")
        if self.index + 1 < len(self.job["segments"]):
            self.index += 1
            self.begin_segment()
            self.message = "Skipped an unavailable clip. Preparing the next highlight…"
        else:
            self.stop_media(stop_music=True)
            self.stage, self.message = "complete", "Highlights complete. An unavailable final clip was skipped."
        self.publish()

    def begin_segment(self):
        self.stop_media()
        self.seamless_lineup = False
        plan = getattr(self.server, "caution_assignments", None)
        if plan and self.segment["kind"] == "clip":
            for event in self.segment.get("events", []):
                if event["kind"] == "caution" and plan.for_time(self.job["session_num"], event["time"]):
                    self.segment["start"] = min(self.segment["start"], max(2, event["time"] - 20))
        self.transition_id += 1
        self.stage, self.changed_at = "covering", self.clock()
        self.message = "Preparing the next highlight…"
        self.confirmations = 0
        self.camera_idx = None
        self.cover_seen_at = None
        self.holding_frame = False
        self.server.clear_lineup_panel()
        self.publish()

    def camera_target(self, at):
        if self.is_race_start() and self.segment.get("camera_cues"):
            cues = sorted(self.segment["camera_cues"], key=lambda cue: cue["time"])
            return next((cue["car_idx"] for cue in reversed(cues) if cue["time"] <= at), cues[0]["car_idx"])
        plan = getattr(self.server, "caution_assignments", None)
        if plan:
            for event in self.segment.get("events", []):
                if event["kind"] == "caution":
                    selected = plan.for_time(self.job["session_num"], event["time"])
                    assigned = selected[1] if selected else None
                    if assigned is not None:
                        return assigned
        if self.segment["kind"] == "lineup":
            entries = self.segment.get("entries", [])
            active = self.segment.get("active_position")
            entry = next((entry for entry in entries if entry.get("position") == active), entries[0] if entries else {})
            return entry.get("car_idx")
        race_cues = [cue for cue in self.segment.get("camera_cues", []) if cue["time"] <= at]
        if race_cues:
            return max(race_cues, key=lambda cue: cue["time"])["car_idx"]
        events = sorted(self.segment.get("events", []), key=lambda event: event["time"])
        incidents = [event for event in events if event["kind"] in ("incident", "incident_marker")]
        cues = [event for event in events if event.get("car_idx") is not None and not (
            event["kind"] == "caution" and any(abs(incident["time"] - event["time"]) <= 15 for incident in incidents))]
        if not cues:
            return self.segment.get("car_idx")
        active = [event for event in cues if event["time"] - 6 <= at]
        return (active[-1] if active else cues[0])["car_idx"]

    def is_race_start(self):
        return self.segment["kind"] == "clip" and any(e["kind"] in ("start", "restart") for e in self.segment.get("events", []))

    def camera_group(self, at):
        cues = sorted(self.segment.get("camera_cues", []), key=lambda cue: cue["time"])
        current = next((cue for cue in reversed(cues) if cue["time"] <= at), cues[0] if cues else {})
        return current.get("group", "Rear Chase")

    def focus(self, group=None, idx=None):
        group = group or (self.camera_group(self.segment["start"]) if self.is_race_start() else "Rear Chase" if self.segment["kind"] == "lineup" else "TV1")
        if idx is None:
            idx = self.camera_target(self.segment["start"])
        if idx is None:
            return True
        lookup = self.source.current_snapshot().driver_lookup if self.source else self.controller.get_driver_lookup()
        info = lookup.get(idx) or lookup.get(str(idx)) or {}
        car_number = str(info.get("number") or "")
        groups = self.controller.get_camera_groups() or []
        desired = next((g for g in groups if str(g.get("GroupName", "")).lower() == group.lower()), None)
        if desired is None and group.lower() == "rear chase":
            desired = next((g for name in ("far chase", "chase") for g in groups
                            if str(g.get("GroupName", "")).lower() == name), None)
        if desired is None and group.lower() == "blimp":
            desired = next((g for name in ("blimp", "chopper") for g in groups
                            if name in str(g.get("GroupName", "")).lower()), None)
        desired = desired or next((g for g in groups if "tv" in str(g.get("GroupName", "")).lower()), None)
        if not desired or not car_number:
            return False
        result = self.controller.switch_camera_to_car(car_number, int(desired["GroupNum"]), 0)
        if result:
            self.group = group
            self.camera_idx = idx
        return bool(result)

    def sync_snapshot(self, replay_time):
        if self.source and self.indices:
            i = max(0, bisect_right(self.indices, (replay_time, len(self.source.snapshots))) - 1)
            self.source.current_index = self.indices[i][1]

    def lineup_entries(self, source_entries=None):
        from config import USE_IRACING_RENDERED_CAR_IMAGES
        entries = [dict(entry) for entry in (self.segment.get("entries", []) if source_entries is None else source_entries)]
        from production.capture_images import driver_key
        missing = []
        for entry in entries:
            info = dict(entry.get("render_driver") or {})
            info.setdefault("name", entry.get("driver_name", ""))
            info.setdefault("number", entry.get("car_number", ""))
            saved = self.saved_images.get(driver_key(info), {})
            name = str(saved.get("file", "")) if isinstance(saved, dict) else ""
            path = (self.image_root / name).resolve()
            if (len(name) == 68 and name.endswith(".png") and all(c in "0123456789abcdef" for c in name[:64])
                    and path.parent == self.image_root and path.is_file()):
                entry["car_image_url"] = "/capture-images/" + name
                entry["number_style"] = saved.get("number_style", {})
            else:
                missing.append(entry)
        if USE_IRACING_RENDERED_CAR_IMAGES and missing:
            from app import build_featured_driver_render_info
            current_lookup = getattr(self.controller, "get_driver_lookup", lambda: {})() or {}
            for entry in missing:
                info = dict(entry.get("render_driver") or {})
                info.setdefault("name", entry.get("driver_name", ""))
                info.setdefault("number", entry.get("car_number", ""))
                info.setdefault("car_idx", entry.get("car_idx"))
                for idx, current in current_lookup.items():
                    same_number = str(current.get("number", "")) == str(info.get("number", ""))
                    recorded_id = info.get("cust_id") or info.get("user_id")
                    current_id = current.get("cust_id") or current.get("user_id")
                    same_driver = (str(recorded_id) == str(current_id) if recorded_id and current_id else
                                   str(current.get("name", "")).casefold() == str(info.get("name", "")).casefold())
                    if same_number and same_driver:
                        info.update(current, car_idx=int(idx))
                        break
                # Use the full broadcast's resolver rather than trusting a saved render URL.
                info.pop("car_image_url", None)
                info.pop("paint_image_url", None)
                render = build_featured_driver_render_info(info)
                entry["car_image_url"] = render.get("image_url", "")
                entry["number_style"] = render.get("number_style", {})
        return entries

    def start_media(self):
        segment = self.segment
        entries = self.lineup_entries() if segment["kind"] == "lineup" else []
        path = (self.job_dir / segment["audio"]).resolve()
        if not path.is_relative_to(self.job_dir) or not path.is_file():
            return self.fail("Prepared audio is missing or outside the highlight job folder.")
        if not self.audio.play(str(path)):
            return self.fail("Prepared narration could not play.")
        if self.music:
            self.music.play_playlist(self.playlist)
        self.stage, self.started_at = "playing", self.clock()
        self.message = segment.get("narration", "")
        self.media_started_replay_time = float(self.controller.get_replay_session_time())
        self.last_camera_change = self.started_at
        self.drift_since = None
        self.deadline = self.started_at + max(float(segment["audio_seconds"]) + 1,
                                               float(segment["end"]) - float(segment["start"]))
        if segment["kind"] == "clip" and not self.controller.play_replay():
            return self.fail("iRacing did not accept replay playback.")
        if segment["kind"] == "lineup":
            self.server.show_lineup_panel(entries, segment.get("active_position", entries[0]["position"]), duration=self.deadline - self.started_at + 2)
        if segment["kind"] == "outro" and self.job.get("recap"):
            import math
            count = len(self.job["recap"].get("results", []))
            self.deadline = max(self.deadline, self.started_at + max(20, math.ceil(max(0, count - 15) / 5) * 8 + 2))
            podium = self.lineup_entries(self.job["recap"].get("podium", []))
            self.server.show_podium_panel(podium, duration=self.deadline - self.started_at + 300)
        self.publish()

    def tick(self):
        now = self.clock()
        if self.stage in ("armed", "paused", "complete", "error", "cancelled"):
            return
        if self.segment["kind"] != "outro" and not self.controller.is_connected():
            return self.fail("iRacing telemetry disconnected.")
        if self.stage == "countdown":
            self.message = f"Highlights begin in {max(0, 5 - int(now - self.changed_at))}…"
            self.publish()
            if now - self.changed_at >= 5:
                self.begin_segment()
        elif self.stage == "covering" and now - self.changed_at >= 1.2:
            poll_at = getattr(self.server, "last_overlay_poll", 0)
            if poll_at < self.changed_at or now - poll_at > 2:
                if now - self.changed_at > 20:
                    self.fail("The overlay is not receiving updates. Keep the overlay browser source open in Streamlabs.")
                return
            if self.cover_seen_at is None:
                self.cover_seen_at = poll_at
            if now - self.cover_seen_at < 1:
                return
            if self.segment["kind"] == "outro":
                # The recap is a narrated slate; it needs no available replay frame.
                self.start_media()
                return
            from production.highlights import request_highlight_seek
            if not request_highlight_seek(self.controller, self.job["session_num"], self.seek_time):
                if self.segment["kind"] == "clip":
                    return self.skip_current("iRacing rejected the replay seek.")
                return self.fail("iRacing rejected the replay seek.")
            self.stage, self.changed_at = "seeking", now
            self.next_seek_retry = now + 2
        elif self.stage == "seeking":
            replay_time = float(self.controller.get_replay_session_time())
            same_session = int(self.controller.get_replay_session_num()) == self.job["session_num"]
            aligned = same_session and abs(replay_time - self.seek_time) <= 0.3
            self.confirmations = self.confirmations + 1 if aligned else 0
            if self.confirmations >= 3:
                self.sync_snapshot(replay_time)
                if not self.focus():
                    if self.segment["kind"] == "clip":
                        return self.skip_current("Could not set a TV camera for the selected driver.")
                    return self.fail("Could not set a TV camera for the selected driver.")
                self.stage, self.changed_at = "camera_wait", now
            elif now - self.changed_at > 12:
                message = (f"Could not confirm replay session {self.job['session_num']} at {self.seek_time:.2f}s "
                           f"(received session {self.controller.get_replay_session_num()} at {replay_time:.2f}s).")
                if self.segment["kind"] == "clip":
                    self.skip_current(message)
                else:
                    self.fail(message)
            elif not aligned and now >= self.next_seek_retry:
                from production.highlights import request_highlight_seek
                request_highlight_seek(self.controller, self.job["session_num"], self.seek_time)
                self.next_seek_retry = now + 2
        elif self.stage == "camera_wait" and now - self.changed_at >= 0.7:
            camera_reader = getattr(self.controller, "safe_read", None)
            actual = camera_reader("CamCarIdx") if callable(camera_reader) else None
            if getattr(self, "camera_idx", None) is not None and actual is not None and int(actual) != self.camera_idx:
                if now - self.changed_at > 4:
                    if self.segment["kind"] == "clip":
                        self.skip_current("The camera did not reach the requested driver.")
                    else:
                        self.fail("The camera did not reach the requested driver.")
                return
            self.start_media()
        elif self.stage == "playing":
            if self.segment["kind"] == "clip" and not self.holding_frame:
                current = float(self.controller.get_replay_session_time())
                elapsed = now - self.started_at
                drift = current - self.media_started_replay_time - elapsed
                wrong_session = int(self.controller.get_replay_session_num()) != self.job["session_num"]
                if wrong_session or (abs(drift) > 1.5 and not self.segment["end"] <= current <= self.segment["end"] + 1):
                    self.drift_since = now if self.drift_since is None else self.drift_since
                    if now - self.drift_since >= 1:
                        diagnostic = {"segment": self.index + 1, "requested_session": self.job["session_num"],
                                      "actual_session": self.controller.get_replay_session_num(), "replay_time": current,
                                      "elapsed": elapsed, "drift": drift, "start": self.segment["start"], "end": self.segment["end"]}
                        with (self.job_dir / "playback-diagnostics.jsonl").open("a", encoding="utf-8") as log:
                            log.write(json.dumps(diagnostic) + "\n")
                        if self.index + 1 < len(self.job["segments"]):
                            self.index += 1
                            self.begin_segment()
                            self.message = "Skipped an out-of-sync clip. Preparing the next highlight…"
                            self.publish()
                            return
                        self.stop_media(stop_music=True)
                        self.stage, self.message = "complete", "Highlights complete. The final out-of-sync clip was skipped."
                        self.publish()
                        return
                    return
                self.drift_since = None
                self.sync_snapshot(current)
                if self.source:
                    self.server.update_from_telemetry(self.source)
                    from production.highlights import race_lap
                    with self.server.lock:
                        subject = self.segment["title"].split("·", 1)[-1].strip()
                        self.server.highlights["title"] = f"Lap {race_lap(self.source.current_snapshot())} · {subject}"
                if current >= self.segment["end"]:
                    self.controller.pause_replay()
                    self.holding_frame = True
                    self.publish()
                # One alternate angle for an overtake; incident causation is not
                # inferred from a camera change. Start and finish on TV.
                target = self.camera_target(current)
                if self.is_race_start():
                    group = self.camera_group(current)
                    if target is not None and (target != getattr(self, "camera_idx", None) or self.group != group):
                        self.focus(group, idx=target)
                        self.last_camera_change = now
                elif target is not None and target != getattr(self, "camera_idx", None):
                    self.focus("TV1", idx=target)
                    self.last_camera_change = now
                if not self.is_race_start() and target is not None and now - self.last_camera_change > 8:
                    next_group = "Chase" if self.group == "TV1" and elapsed < 17 else "TV1"
                    self.focus(next_group, idx=target)
                    self.last_camera_change = now
            if now >= self.deadline:
                continuous_lineup = (self.segment["kind"] == "lineup" and self.index + 1 < len(self.job["segments"])
                                     and self.job["segments"][self.index + 1]["kind"] == "lineup")
                if continuous_lineup:
                    self.audio.stop()
                else:
                    self.stop_media()
                    self.server.clear_lineup_panel()
                if self.index + 1 >= len(self.job["segments"]):
                    if self.music:
                        self.music.stop()
                    self.stage, self.message = "complete", "Highlights complete. You can stop recording in Streamlabs."
                    self.publish()
                else:
                    self.index += 1
                    if continuous_lineup:
                        if not self.focus("Rear Chase"):
                            return self.fail("Could not set the lineup driver's camera.")
                        self.seamless_lineup = True
                        self.stage, self.changed_at = "camera_wait", now
                        self.publish()
                    else:
                        self.begin_segment()


def run_highlights(job_path, host="127.0.0.1", port=8765):
    from broadcaster.telemetry import IRacingTelemetry
    from config import STUDIO_VOLUME, PRACTICE_MUSIC_PLAYLIST
    from production.audio_bed import OneShotAudioPlayer, PlaylistAudioPlayer, percent_to_mci_volume
    from production.overlay import OverlayServer
    from replay.replay_telemetry import ReplayTelemetry
    job_path = Path(job_path).resolve()
    job = json.loads(job_path.read_text(encoding="utf-8"))
    from production.highlights import selected_highlights_job
    job = selected_highlights_job(job)
    if job.get("status") != "ready" or not job.get("segments"):
        raise ValueError("Prepare the highlight programme before playing it.")
    controller = IRacingTelemetry()
    from production.sim_racing_apps import reset_sim_racing_apps_state
    reset_sim_racing_apps_state()
    if not controller.startup() or controller.get_replay_frame_number() is None:
        raise RuntimeError("Open the matching saved iRacing replay before playing highlights.")
    actual = str(controller.get_track_info().get("track_name", "")).strip().casefold()
    if actual != str(job.get("track", "")).strip().casefold():
        raise RuntimeError("The loaded replay track does not match this highlight capture.")
    capture_path = Path(job["source"])
    if job.get("source_size") is not None and (capture_path.stat().st_size != job["source_size"] or capture_path.stat().st_mtime_ns != job["source_mtime_ns"]):
        raise RuntimeError("The telemetry capture changed after preparation. Prepare highlights again.")
    from production.highlights import read_highlight_snapshots
    source = ReplayTelemetry(capture_path, snapshots=read_highlight_snapshots(capture_path))
    if "cautions" not in job:
        from production.highlights import build_plan
        catalogue = build_plan(source.snapshots, capture_path)
        job.update({key: catalogue[key] for key in ("cautions", "drivers")})
    captured_session = job.get("subsession_id")
    actual_session = controller.get_weekend_info().get("SubSessionID")
    if captured_session and actual_session and str(captured_session) != str(actual_session):
        raise RuntimeError("The saved replay is from a different race session than this capture.")
    server = OverlayServer(host=host, port=port)
    from production.caution_assignments import CautionAssignments, handle_assignment
    server.caution_assignments = CautionAssignments(job)
    server.state.track_name = job.get("track", "")
    audio = OneShotAudioPlayer(normal_volume=percent_to_mci_volume(STUDIO_VOLUME), alias="rgc_highlights")
    music = PlaylistAudioPlayer(normal_volume=percent_to_mci_volume(10), alias="rgc_highlights_music")
    player = HighlightsPlayer(job, controller, server, audio, job_path.parent, source=source,
                              music=music, playlist=PRACTICE_MUSIC_PLAYLIST)
    server.start()
    stop_path = Path(__file__).resolve().parents[1] / ".runtime" / "broadcast_stop.request"
    print("Highlights armed. Start recording in Streamlabs, then use Start Highlights in Producer Assist.", flush=True)
    try:
        while not stop_path.exists():
            for item in server.drain_commands():
                if handle_assignment(server, item["command"], item.get("payload", {})):
                    continue
                player.command(item["command"])
            try:
                player.tick()
            except Exception as error:
                player.fail(f"Highlight playback error: {error}")
            time.sleep(0.1)
    finally:
        player.stop_media(stop_music=True)
        server.stop()
