import threading
from types import SimpleNamespace

from production.highlights import build_plan
from production.highlights_player import HighlightsPlayer
from production.highlights_studio import import_graphic
from replay.telemetry_snapshot import TelemetrySnapshot


def snapshots():
    result = []
    for second in range(12):
        rows = [{"CarIdx": 0, "Position": 1, "LapsComplete": second // 3, "Incidents": 0},
                {"CarIdx": 1, "Position": 2, "LapsComplete": second // 3, "Incidents": 0}]
        result.append(TelemetrySnapshot(timestamp=second, session_num=2, session_time=second,
            session_type="Race", session_state=4, lap=1 + second // 3, total_laps=4,
            results=rows, driver_lookup={0: {"name": "T.J. Lee", "number": "34"}, 1: {"name": "Chuck Sweeting", "number": "75"}},
            track_info={"track_name": "Richmond"}, pit_road_status=[False, False],
            lap_completed=[1, 1], lap_dist_pct=[0.5, 0.499]))
    return result


def events(plan):
    return [event for segment in plan["segments"] for event in segment.get("events", [])]


def test_planner_qualifies_incidents_and_caution_cause_without_repeating_clips():
    data = snapshots()
    for snapshot in data[4:]:
        snapshot.results[1]["Incidents"] = 4
    for snapshot in data[5:8]:
        snapshot.session_flags = 0x4000
    plan = build_plan(data)
    matches = [s for s in plan["segments"] if "incident" in [e["kind"] for e in s.get("events", [])]]
    assert len(matches) == 1
    assert any("increased by 4" in e["facts"] for e in matches[0]["events"])
    assert "Let's see what could have brought out the caution" in matches[0]["facts"]
    assert "causation is unconfirmed" not in matches[0]["facts"]
    assert len([e for e in events(plan) if e["kind"] == "incident"]) == 1


def test_missing_incident_counts_and_mid_race_grid_are_not_invented():
    data = snapshots()
    for snapshot in data:
        snapshot.lap += 30
        snapshot.starting_grid = list(snapshot.results)
        for row in snapshot.results:
            row.pop("Incidents")
    plan = build_plan(data)
    assert plan["partial"]
    assert not any(s["kind"] == "lineup" for s in plan["segments"])
    assert not any(e["kind"] == "incident" for e in events(plan))
    assert any("incident counts" in warning for warning in plan["warnings"])


def test_caution_follows_isolated_slowdown_before_yellow_without_incident_points():
    data = snapshots()
    for i, s in enumerate(data):
        s.car_speed_mph = {"0": 120, "1": 120 if i < 5 else 35}
        s.track_surface = [3, 3 if i < 5 else 0]
        if i >= 8:
            s.session_flags = 0x4000
    plan = build_plan(data)
    review, = [e for e in events(plan) if e.get("evidence") == "isolated_pre_caution_slowdown"]
    caution, = [e for e in events(plan) if e["kind"] == "caution"]
    assert caution["car_idx"] == review["car_idx"] == 1
    assert review["start"] < review["time"] < caution["time"]
    assert "possible contributor" in review["facts"]
    assert "Do not claim wheelspin" in review["facts"]


def test_caution_slowdown_excludes_pit_entries_and_field_wide_braking():
    from production.highlights import caution_slowdown_candidate
    data = snapshots()
    for i, s in enumerate(data):
        s.car_speed_mph = {0: 120, 1: 120 if i < 5 else 35}
        s.pit_road_status = [False, i >= 7]
    assert caution_slowdown_candidate(data, 8) is None
    for i, s in enumerate(data):
        s.pit_road_status = [False, False]
        s.car_speed_mph[0] = 120 if i < 5 else 35
    assert caution_slowdown_candidate(data, 8) is None
    for s in data:
        s.car_speed_mph = {}
    assert caution_slowdown_candidate(data, 8) is None


def test_producer_caution_choice_controls_clip_and_narration():
    data = snapshots()
    for s in data[5:8]:
        s.session_flags = 0x4000
    plan = build_plan(data, caution_assignments={"2:caution:1": 1})
    caution, = [e for e in events(plan) if e["kind"] == "caution"]
    assert caution["car_idx"] == 1
    assert "Chuck Sweeting" in caution["facts"]
    assert plan["cautions"] == [{"id": "2:caution:1", "lap": 2, "time": 5}]
    assert len(plan["drivers"]) == 2


def test_verified_grid_is_paged_ten_at_a_time():
    data = snapshots()
    data[0].starting_grid_source = "qualifying"
    data[0].starting_grid = [{"CarIdx": index, "Position": index} for index in range(23)]
    plan = build_plan(data)
    pages = [s for s in plan["segments"] if s["kind"] == "lineup"]
    assert len(pages) == 23
    assert [page["active_position"] for page in pages] == list(range(1, 24))
    assert [len(pages[i]["entries"]) for i in (0, 10, 20)] == [10, 10, 3]
    assert pages[0]["entries"][0]["position"] == 1
    assert pages[-1]["entries"][-1]["position"] == 23


def test_pit_cycle_lead_change_is_not_presented_as_on_track_pass():
    data = snapshots()
    for s in data[3:]:
        s.results[0]["Position"], s.results[1]["Position"] = 2, 1
        s.pit_road_status[0] = True
    plan = build_plan(data)
    lead, = [e for e in events(plan) if e["kind"] == "lead_change"]
    assert "pit-cycle or caution-order change" in lead["facts"]


def test_scoring_flicker_does_not_create_a_lead_change():
    data = snapshots()
    data[3].results[0]["Position"], data[3].results[1]["Position"] = 2, 1
    assert not any(e["kind"] == "lead_change" for e in events(build_plan(data)))


def test_finish_requires_confirmed_finish_not_lap_number():
    data = snapshots()
    plan = build_plan(data)
    assert not any(e["kind"] == "finish" for e in events(plan))
    data[-1].session_flags = 1
    plan = build_plan(data)
    assert not plan["partial"]
    assert any(e["kind"] == "finish" for e in events(plan))


def test_graphic_import_is_local_and_reusable(tmp_path):
    graphic = tmp_path / "logo.png"
    graphic.write_bytes(b"image")
    url = import_graphic(graphic, tmp_path)
    copied = tmp_path / "production" / "static" / url.split("/")[-1]
    assert copied.read_bytes() == b"image"
    assert import_graphic(copied, tmp_path) == url


def test_title_edits_preserve_prepared_narration(tmp_path):
    import json
    from production.highlights_studio import save_highlights_title
    path = tmp_path / "programme.json"
    path.write_text(json.dumps({"status": "ready", "options": {"sponsor": "RGC"},
                                "segments": [{"audio": "voice.mp3", "narration": "Saved commentary."}]}))
    save_highlights_title(path, "  Richmond Race Highlights  ")
    job = json.loads(path.read_text())
    assert job["options"] == {"sponsor": "RGC", "title": "Richmond Race Highlights"}
    assert job["status"] == "ready" and job["segments"][0]["audio"] == "voice.mp3"
    save_highlights_title(path, "Richmond", {"transition_sponsor": "Center Sponsor", "transition_graphic": "/static/center.png", "full_screen_graphic": "/static/league.png",
                                            "sponsor": "Clip Sponsor", "sponsor_logo": "/static/clip.png"})
    job = json.loads(path.read_text())
    assert job["options"]["transition_sponsor"] == "Center Sponsor"
    assert job["options"]["sponsor_logo"] == "/static/clip.png"
    assert job["options"]["full_screen_graphic"] == "/static/league.png"
    assert job["segments"][0]["narration"] == "Saved commentary."


def test_lineup_refreshes_stored_image_using_matched_current_replay_driver(tmp_path, monkeypatch):
    import config
    import app
    import production.sim_racing_apps as sra
    import production.iracing_render_cache as cache
    player, controller, server, clock, plays = make_player(tmp_path)
    player.segment["entries"] = [{"car_idx": 1, "car_number": "34", "driver_name": "T.J. Lee",
                                  "car_image_url": "old-paint.png", "render_driver": {"cust_id": 123}}]
    controller.get_driver_lookup = lambda: {1: {"name": "Another Driver", "number": "75", "cust_id": 999},
                                           4: {"name": "T.J. Lee", "number": "34", "cust_id": 123, "car_path": "current-car"}}
    seen = []
    monkeypatch.setattr(config, "USE_IRACING_RENDERED_CAR_IMAGES", True)
    def render(info):
        seen.append(info)
        return {"image_url": "current-paint.png"}
    monkeypatch.setattr(app, "build_featured_driver_render_info", render)
    monkeypatch.setattr(cache, "build_iracing_render_image_url", lambda info: "fallback.png")
    entries = player.lineup_entries()
    assert entries[0]["car_image_url"] == "current-paint.png"
    assert seen[0]["car_idx"] == 4 and seen[0]["car_path"] == "current-car"


class Controller:
    def __init__(self):
        self.time, self.session, self.connected, self.seeks = 0, 2, True, []
    def is_connected(self):
        return self.connected
    def pause_replay(self):
        return True
    def play_replay(self):
        return True
    def seek_replay_session_time(self, session, time):
        self.seeks.append((session, time))
        return True
    def get_replay_session_time(self):
        return self.time
    def get_replay_session_num(self):
        return self.session
    def get_driver_lookup(self):
        return {}


class Server:
    def __init__(self):
        self.lock = threading.Lock()
        self.last_overlay_poll = 0
    def clear_lineup_panel(self):
        pass


def make_player(tmp_path):
    clock = [100.0]
    controller, server = Controller(), Server()
    plays = []
    audio = SimpleNamespace(stop=lambda: None, play=lambda path: plays.append(path) or True)
    (tmp_path / "voice.mp3").write_bytes(b"audio")
    job = {"session_num": 2, "track": "Richmond", "segments": [
        {"kind": "clip", "title": "Lap 34", "start": 50, "end": 70,
         "audio": "voice.mp3", "audio_seconds": 8}], "options": {"transition": "cycle"}}
    player = HighlightsPlayer(job, controller, server, audio, tmp_path, clock=lambda: clock[0])
    return player, controller, server, clock, plays


def test_lineup_and_podium_use_archived_pixels_without_live_renderer(tmp_path, monkeypatch):
    import hashlib
    import json
    from production.capture_images import driver_key, image_directory
    player, controller, server, clock, plays = make_player(tmp_path)
    capture = tmp_path / "race.jsonl"
    root = image_directory(capture)
    root.mkdir()
    body = b"saved original car image"
    name = hashlib.sha256(body).hexdigest() + ".png"
    (root / name).write_bytes(body)
    driver = {"name": "Driver", "number": "34", "cust_id": 123}
    (root / "manifest.json").write_text(json.dumps({driver_key(driver): {"file": name, "number_style": {"color": "#fff"}}}))
    player.job["source"] = str(capture)
    replacement = HighlightsPlayer(player.job, controller, server, player.audio, tmp_path)
    def unavailable(*args, **kwargs):
        raise AssertionError("Archived images must not contact the live renderer")
    monkeypatch.setattr("app.build_featured_driver_render_info", unavailable)
    monkeypatch.setattr(controller, "get_driver_lookup", unavailable)
    entry = {"render_driver": driver, "driver_name": "Driver", "car_number": "34"}
    result = replacement.lineup_entries([entry])
    assert result[0]["car_image_url"] == "/capture-images/" + name
    assert result[0]["number_style"] == {"color": "#fff"}
    assert server.capture_image_dir == root.resolve()


def test_seek_waits_for_visible_transition_and_never_guesses_after_timeout(tmp_path):
    player, controller, server, clock, plays = make_player(tmp_path)
    player.begin_segment()
    clock[0] = 102
    player.tick()
    assert controller.seeks == []
    server.last_overlay_poll = 102
    player.tick()
    assert controller.seeks == []
    clock[0] = 103.1
    server.last_overlay_poll = clock[0]
    player.tick()
    assert controller.seeks == [(2, 50)]
    clock[0] = 116
    player.tick()
    assert player.stage == "complete"
    assert server.highlights["cover"]
    assert plays == []


def test_seek_must_match_session_and_time_before_audio_starts(tmp_path):
    player, controller, server, clock, plays = make_player(tmp_path)
    player.begin_segment()
    clock[0], server.last_overlay_poll = 102, 100.5
    player.tick()
    controller.time, controller.session = 50, 1
    for _ in range(4):
        player.tick()
    assert player.stage == "seeking"
    assert not plays
    controller.session = 2
    for _ in range(3):
        player.tick()
    assert player.stage == "camera_wait"
    clock[0] += 0.8
    player.tick()
    assert player.stage == "playing"
    assert not server.highlights["cover"]
    assert len(plays) == 1


def test_opening_graphics_seek_inside_race_instead_of_qualifying_boundary(tmp_path):
    player, controller, server, clock, plays = make_player(tmp_path)
    player.segment.update(kind="intro", start=.116, end=.116)
    player.begin_segment()
    clock[0], server.last_overlay_poll = 102, 100.5
    player.tick()
    assert controller.seeks == [(2, 2.0)]
    controller.session, controller.time = 1, .1
    for _ in range(3):
        player.tick()
    assert player.stage == "seeking" and not plays
    controller.session, controller.time = 2, 1.93
    for _ in range(3):
        player.tick()
    clock[0] += .8
    player.tick()
    assert player.stage == "playing" and len(plays) == 1
    player.segment["kind"] = "lineup"
    assert player.seek_time == 60.0
    player.segment["kind"] = "clip"
    assert player.seek_time == .116


def test_pause_and_cancel_cover_picture_and_resume_retries_current_clip(tmp_path):
    player, controller, server, clock, plays = make_player(tmp_path)
    player.stage = "playing"
    player.command("highlights_pause")
    assert player.stage == "paused" and server.highlights["cover"]
    player.command("highlights_resume")
    assert player.stage == "covering" and player.index == 0
    player.command("highlights_cancel")
    assert player.stage == "cancelled" and server.highlights["cover"]


def test_lineup_highlights_driver_and_changes_pages_without_seek_or_transition(tmp_path):
    player, controller, server, clock, plays = make_player(tmp_path)
    panels = []
    server.show_lineup_panel = lambda entries, active, duration: panels.append(active)
    player.lineup_entries = lambda: player.segment["entries"]
    player.job["segments"] = [dict(player.segment, kind="lineup", active_position=p,
                                   entries=[{"position": p}], start=60, end=60) for p in (10, 11)]
    player.start_media()
    transition = player.transition_id
    clock[0] = player.deadline
    player.tick()
    assert player.stage == "camera_wait" and not server.highlights["cover"]
    clock[0] += .8
    player.tick()
    assert player.index == 1 and player.stage == "playing"
    assert panels == [10, 11]
    assert player.transition_id == transition and not controller.seeks


def test_persistent_replay_drift_skips_clip_and_records_actual_times(tmp_path):
    player, controller, server, clock, plays = make_player(tmp_path)
    player.job["segments"].append(dict(player.segment, title="Next highlight"))
    player.begin_segment()
    player.start_media()
    clock[0] += 4
    player.tick()
    assert player.stage == "playing"  # One delayed telemetry read is tolerated.
    clock[0] += 1.1
    player.tick()
    assert player.stage == "covering" and player.index == 1
    assert "Skipped" in player.message
    assert '"drift"' in (tmp_path / "playback-diagnostics.jsonl").read_text()


def test_lineup_camera_targets_the_driver_being_announced(tmp_path):
    player, controller, server, clock, plays = make_player(tmp_path)
    player.segment.update(kind="lineup", active_position=12,
                          entries=[{"position": 11, "car_idx": 5}, {"position": 12, "car_idx": 8}])
    assert player.camera_target(60) == 8


def test_saved_caution_choice_overrides_automatic_camera_before_yellow(tmp_path):
    from production.caution_assignments import CautionAssignments
    player, controller, server, clock, plays = make_player(tmp_path)
    server.caution_assignments = CautionAssignments({"track": "Richmond", "session_num": 2,
        "subsession_id": 123, "source": "capture.jsonl", "cautions": [{"id": "2:caution:1", "lap": 3, "time": 60}],
        "drivers": [{"car_idx": 0}]}, tmp_path)
    server.caution_assignments.assign("2:caution:1", 0)
    player.segment["events"] = [{"kind": "incident", "time": 55, "car_idx": 8},
                               {"kind": "caution", "time": 60, "car_idx": 8}]
    player.begin_segment()
    assert player.segment["start"] == 40
    assert player.camera_target(40) == 0


def test_finish_uses_first_checkered_and_ignores_postrace_incidents_and_pits():
    data = snapshots()
    for i, s in enumerate(data):
        if i >= 7:
            s.session_flags = 1
            s.session_state = 5
            s.results[1]["Incidents"] = 12
            s.pit_road_status = [True, True]
    plan = build_plan(data)
    finish, = [e for e in events(plan) if e["kind"] == "finish"]
    assert finish["time"] == 7
    assert not any(e["kind"] in ("pit_cycle", "incident") for e in events(plan))
    assert plan["segments"][-2]["events"][-1]["kind"] == "finish"
    assert plan["segments"][-1]["kind"] == "outro"


def test_recap_contains_classification_podium_and_recorded_stats():
    data = snapshots()
    for s in data:
        s.results[0].update(StartingPosition=2, FastestTime=21.25, LapsLed=3)
        s.results[1].update(StartingPosition=1, FastestTime=21.4, LapsLed=1)
    data[-1].session_flags = 1
    plan = build_plan(data)
    recap = plan["recap"]
    assert [r["position"] for r in recap["results"]] == [1, 2]
    assert recap["podium"][0]["driver_name"] == "T.J. Lee"
    stats = {s["label"]: s for s in recap["stats"]}
    assert stats["Fastest lap"]["value"] == "0:21.250"
    assert stats["Biggest mover"]["value"] == "+1 places"
    assert stats["Biggest loser"]["value"] == "-1 places"
    assert stats["Most laps led"]["value"] == "3"
    assert stats["Cautions"]["value"] == "0"
    assert "Fastest lap" in plan["segments"][-1]["facts"]


def test_seek_timeout_advances_to_recap_which_does_not_seek(tmp_path):
    player, controller, server, clock, plays = make_player(tmp_path)
    player.job["segments"].append(dict(player.segment, kind="outro", title="Recap"))
    player.begin_segment()
    clock[0], server.last_overlay_poll = 102, 100.5
    player.tick()
    clock[0] += 13
    player.tick()
    assert player.index == 1 and player.stage == "covering"
    seeks = len(controller.seeks)
    clock[0] += 2
    server.last_overlay_poll = clock[0] - 1.1
    player.tick()
    assert player.stage == "playing" and len(plays) == 1
    assert len(controller.seeks) == seeks


def test_recap_shows_podium_and_allows_time_for_every_results_page(tmp_path):
    player, controller, server, clock, plays = make_player(tmp_path)
    player.segment.update(kind="outro", start=70, end=70)
    player.job["recap"] = {"results": [{"position": p} for p in range(1, 41)],
                           "podium": [{"position": 1}], "stats": []}
    shown = []
    server.show_podium_panel = lambda entries, duration: shown.append((entries, duration))
    player.lineup_entries = lambda entries: entries
    player.start_media()
    assert shown[0][0] == [{"position": 1}]
    assert player.deadline - player.started_at >= 42
    assert len(server.highlights["recap"]["results"]) == 40


def test_music_continues_across_transitions_pause_and_retry_until_stopped(tmp_path):
    player, controller, server, clock, plays = make_player(tmp_path)
    stops = []
    player.music = SimpleNamespace(stop=lambda: stops.append(True))
    player.begin_segment()
    player.command("highlights_pause")
    player.command("highlights_resume")
    player.fail("Temporary replay interruption")
    assert not stops
    player.command("highlights_cancel")
    assert stops == [True]


def test_parked_pit_car_is_not_treated_as_a_new_arrival():
    data = snapshots()
    for i, s in enumerate(data):
        s.session_time = i * 10
        s.pit_road_status = [True, i in (2, 8)]
    stops = [e for e in events(build_plan(data)) if e["kind"] == "pit_cycle"]
    assert len(stops) == 1
    assert all(e["pit_entrants"] == [1] for e in stops)
    assert all("T.J. Lee" not in e["facts"] for e in stops)


def test_pit_arrivals_are_summarized_per_window_without_repeating_each_lap():
    data = snapshots()
    for i, s in enumerate(data):
        s.session_time = i * 5
        s.lap = 1 if i < 5 else 2
        for row in s.results:
            row["LapsComplete"] = s.lap - 1
        s.pit_road_status = [2 <= i < 4, 3 <= i < 4 or i >= 6]
    stops = [e for e in events(build_plan(data)) if e["kind"] == "pit_cycle"]
    assert len(stops) == 1
    assert stops[0]["pit_entrants"] == [0, 1]
    assert "T.J. Lee" in stops[0]["facts"] and "Chuck Sweeting" in stops[0]["facts"]
    assert stops[0]["end"] == 23  # Opening arrival at 10s plus 13s; no long pit montage.
    assert "may span several laps" in stops[0]["facts"]


def test_overtakes_include_longer_run_up_and_restarts_continue_longer():
    data = snapshots()
    for i, s in enumerate(data):
        s.session_time = i * 10
        s.session_flags = 0x4000 if i in (2, 3) else 0
        if i >= 7:
            s.results[0]["Position"], s.results[1]["Position"] = 2, 1
    plan = build_plan(data)
    restart, = [e for e in events(plan) if e["kind"] == "restart"]
    assert restart["end"] - restart["time"] == 50
    lead, = [e for e in events(plan) if e["kind"] == "lead_change"]
    assert lead["time"] - lead["start"] == 25
    assert lead["end"] == lead["time"]


def test_grouping_limits_passes_to_two_and_keeps_other_subjects_separate():
    from production.highlights import group_highlight_events
    def event(kind, time, lap=10):
        return {"kind": kind, "time": time, "lap": lap, "start": time - 25,
                "end": time + 10, "car_idx": 1, "facts": kind}
    clips = group_highlight_events([event("overtake", 100), event("lead_change", 105),
                                   event("overtake", 110), event("restart", 112),
                                   event("pit_cycle", 114), event("caution", 116)])
    assert [[e["kind"] for e in c["events"]] for c in clips] == [
        ["overtake", "lead_change"], ["overtake"], ["restart"], ["pit_cycle"], ["caution"]]
    chain = group_highlight_events([event("overtake", i * 10, i // 2) for i in range(30)])
    assert all(len(c["events"]) <= 2 and c["end"] - c["start"] <= 55 for c in chain)


def test_long_recap_budget_keeps_key_moments_and_some_rear_field_recognition():
    from production.highlights import apply_highlight_budget, programme_seconds
    def clip(i, kind="overtake", position=6):
        return {"kind": "clip", "start": i * 100, "end": i * 100 + 25, "car_idx": i,
                "events": [{"kind": kind, "position": position, "time": i * 100, "lap": i, "car_idx": i}]}
    clips = [clip(0, "start"), clip(1, "restart"), clip(2, "caution"), clip(3, "finish")]
    clips += [clip(i, position=6 if i % 2 else 20) for i in range(4, 100)]
    job = {"segments": clips, "warnings": []}
    apply_highlight_budget(job)
    selected = [e for s in job["segments"] for e in s["events"]]
    assert programme_seconds(job) <= 1080
    assert {"start", "restart", "caution", "finish"} <= {e["kind"] for e in selected}
    assert sum(e.get("position") == 20 and e["kind"] == "overtake" for e in selected) >= 2
    assert sum(e.get("position") == 6 and e["kind"] == "overtake" for e in selected) > sum(e.get("position") == 20 and e["kind"] == "overtake" for e in selected)
    assert job["omitted_optional_clips"] > 0


def test_restart_camera_tracks_fifth_to_tenth_not_the_leader(tmp_path):
    from production.highlights import restart_camera_cues
    data = snapshots()
    for s in data:
        s.results = [{"CarIdx": i, "Position": i + 1, "LapsComplete": 0} for i in range(12)]
        s.lap_completed = [0] * 12
        s.lap_dist_pct = [.8 - i * .01 for i in range(12)]
        s.pit_road_status = [False] * 12
    cues = restart_camera_cues(data, 0, 11)
    assert cues and all(4 <= cue["car_idx"] <= 9 for cue in cues)
    player, *_ = make_player(tmp_path)
    player.segment["camera_cues"] = [{"time": 50, "car_idx": 5}, {"time": 65, "car_idx": 8}]
    assert player.camera_target(51) == 5
    assert player.camera_target(66) == 8


def test_lineup_uses_rear_chase_with_chase_fallback(tmp_path):
    player, controller, server, clock, plays = make_player(tmp_path)
    player.segment.update(kind="lineup", active_position=1, entries=[{"position": 1, "car_idx": 0}])
    controller.get_driver_lookup = lambda: {0: {"number": "34", "name": "T.J. Lee"}}
    groups = [{"GroupName": "TV1", "GroupNum": 3}, {"GroupName": "Rear Chase", "GroupNum": 7}]
    controller.get_camera_groups = lambda: groups
    shots = []
    controller.switch_camera_to_car = lambda number, group, camera: shots.append((number, group)) or True
    assert player.focus()
    assert shots[-1] == ("34", 7)
    groups[1] = {"GroupName": "Chase", "GroupNum": 8}
    assert player.focus()
    assert shots[-1] == ("34", 8)


def test_clip_caption_keeps_its_subject_when_lap_updates(tmp_path):
    player, controller, server, clock, plays = make_player(tmp_path)
    player.segment["title"] = "Lap 26 · Pit Stops"
    player.source = SimpleNamespace(current_snapshot=lambda: TelemetrySnapshot(lap=27, total_laps=150))
    server.update_from_telemetry = lambda source: None
    player.begin_segment()
    controller.time = 50
    player.start_media()
    clock[0] += 1
    controller.time = 51
    player.tick()
    assert server.highlights["title"] == "Lap 27 · Pit Stops"


def test_finish_covers_last_forty_seconds_and_start_omits_camera_instructions():
    data = snapshots()
    for s in data:
        s.session_time *= 10
        s.total_laps = 150
    data[-1].session_flags = 1
    plan = build_plan(data)
    finish, = [e for e in events(plan) if e["kind"] == "finish"]
    assert finish["time"] - finish["start"] == 40
    start, = [e for e in events(plan) if e["kind"] == "start"]
    assert "fifth" not in start["facts"] and "Focus" not in start["facts"]
    assert "start of the race" in start["facts"]


def test_pit_window_includes_first_car_and_later_leader_stop():
    data = snapshots()
    for i, s in enumerate(data):
        s.session_time = i * 10
        s.pit_road_status = [i >= 7, 2 <= i <= 4]
    stops = [e for e in events(build_plan(data)) if e["kind"] == "pit_cycle"]
    assert [e["pit_role"] for e in stops] == ["opening", "leader"]
    assert stops[0]["car_idx"] == 1 and stops[1]["car_idx"] == 0
    assert all(e["end"] - e["start"] <= 21 for e in stops)


def test_short_clip_waits_for_narration_to_finish(tmp_path):
    player, controller, server, clock, plays = make_player(tmp_path)
    player.segment.update(start=50, end=52, audio_seconds=8)
    player.begin_segment()
    controller.time = 50
    player.start_media()
    assert player.deadline == clock[0] + 9
    controller.time = 52
    clock[0] += 2
    player.tick()
    assert player.holding_frame and player.stage == "playing"
    clock[0] = player.deadline
    player.tick()
    assert player.stage == "complete"


def test_cycle_uses_different_styles_between_segments(tmp_path):
    player, *_ = make_player(tmp_path)
    styles = []
    for index in range(3):
        player.index = index
        styles.append(player.style())
    assert styles == ["fade", "slide", "wipe"]


def test_incident_scan_restores_replay_position_and_speed():
    from production.highlights import scan_incident_markers
    class IncidentController(Controller):
        def __init__(self):
            super().__init__()
            self.time = 99
            self.session = 1  # Preparation can begin in practice/qualifying.
            self.seek_requests = []
            self.points = iter([20, 40, 40])
            self.restored_speed = None
        def get_replay_play_speed(self):
            return 0
        def get_camera_groups(self):
            return [{"GroupNum": 4, "GroupName": "TV1"}]
        def seek_replay_session_time(self, session, at):
            self.seek_requests.append((session, at))
            if session == 2 and at < 2:
                return True  # Simulate the ambiguous race-opening boundary.
            self.session, self.time = session, at
            return True
        def seek_next_incident_marker(self):
            self.time = next(self.points, 40)
            return True
        def switch_camera_to_incident(self, group):
            return True
        def safe_read(self, name):
            return 1
        def set_replay_speed(self, speed):
            self.restored_speed = speed
    controller = IncidentController()
    virtual = [0.0]
    def sleep(seconds):
        virtual[0] += seconds
    markers = scan_incident_markers(controller, 2, 0, 60, clock=lambda: virtual[0], sleep=sleep)
    assert markers == [{"time": 20.0, "car_idx": 1}, {"time": 40.0, "car_idx": 1}]
    assert controller.time == 99
    assert controller.session == 1
    assert controller.seek_requests[0] == (2, 2.0)
    assert controller.restored_speed == 0


def test_marker_review_does_not_claim_a_two_point_incident_or_fault():
    plan = build_plan(snapshots(), markers=[{"time": 5, "car_idx": 1}])
    marker, = [event for event in events(plan) if event["kind"] == "incident_marker"]
    assert "amount, collision type, fault" in marker["facts"]
    assert "unconfirmed" in marker["facts"]


def test_race_lap_uses_leader_progress_when_focused_driver_is_lapped():
    from production.highlights import race_lap
    snapshot = TelemetrySnapshot(lap=31, total_laps=150, session_state=4,
                                 results=[{"LapsComplete": 33}, {"LapsComplete": 30}])
    assert race_lap(snapshot) == 34


def test_preparation_reuses_completed_narration_on_retry(tmp_path, monkeypatch):
    import config
    import openai
    import elevenlabs.client
    import production.audio_bed
    import production.highlights as highlights
    calls = []
    for key in ("OPENAI_API_KEY", "ELEVENLABS_API_KEY", "LEAD_VOICE_ID"):
        monkeypatch.setattr(config, key, "test-placeholder")
    def narrate(**kwargs):
        calls.append("text")
        return SimpleNamespace(output_text="Here is the recorded race action.")
    def voice(**kwargs):
        calls.append("voice")
        return iter([b"prepared audio"])
    monkeypatch.setattr(openai, "OpenAI", lambda **kwargs: SimpleNamespace(responses=SimpleNamespace(create=narrate)))
    monkeypatch.setattr(elevenlabs.client, "ElevenLabs", lambda **kwargs: SimpleNamespace(text_to_speech=SimpleNamespace(convert=voice)))
    monkeypatch.setattr(production.audio_bed, "OneShotAudioPlayer", lambda **kwargs: SimpleNamespace(stop=lambda: None))
    monkeypatch.setattr(highlights, "audio_duration", lambda *args: 4.0)
    monkeypatch.setattr(highlights, "read_highlight_snapshots", lambda path: snapshots())
    capture, job_path = tmp_path / "capture.jsonl", tmp_path / "job" / "programme.json"
    capture.write_text("capture")
    first = highlights.prepare_highlights(capture, job_path)
    count = len(calls)
    second = highlights.prepare_highlights(capture, job_path)
    assert first["status"] == second["status"] == "ready"
    assert len(calls) == count
    assert all(segment.get("audio_seconds") == 4.0 for segment in second["segments"])


def test_narration_retries_explicit_truncation_even_with_terminal_punctuation():
    from production.highlights import generate_narration
    responses = iter([
        SimpleNamespace(output_text="Only part of the lineup.", status="incomplete",
                        incomplete_details=SimpleNamespace(reason="max_output_tokens")),
        SimpleNamespace(output_text="The complete lineup", status="completed", incomplete_details=None),
    ])
    budgets, checkpoints = [], []
    def create(**kwargs):
        budgets.append(kwargs["max_output_tokens"])
        return next(responses)
    segment = {}
    client = SimpleNamespace(responses=SimpleNamespace(create=create))
    assert generate_narration(client, "model", "facts", segment, lambda: checkpoints.append(True)) == "The complete lineup."
    assert budgets == [1200, 2400]
    assert len(checkpoints) == 2
    assert segment["narration_attempts"][0]["reason"] == "max_output_tokens"


def test_narration_exhaustion_saves_diagnostics_and_never_returns_partial_text():
    import pytest
    from production.highlights import generate_narration
    response = SimpleNamespace(output_text="An unfinished", status="incomplete",
                               incomplete_details={"reason": "max_output_tokens"})
    client = SimpleNamespace(responses=SimpleNamespace(create=lambda **kwargs: response))
    segment, checkpoints = {}, []
    with pytest.raises(RuntimeError, match="automatic retries"):
        generate_narration(client, "model", "facts", segment, lambda: checkpoints.append(True))
    assert len(checkpoints) == 3
    assert segment["narration_attempts"][-1]["text"] == "An unfinished"


def test_streamed_samples_keep_the_last_frame_and_incident_change(tmp_path):
    import json
    from production.highlights import read_highlight_snapshots
    path = tmp_path / "capture.jsonl"
    data = []
    for i in range(40):
        snapshot = snapshots()[0]
        snapshot.session_time = i / 10
        if i >= 5:
            snapshot.results[1]["Incidents"] = 2
        data.append(snapshot.to_dict())
    path.write_text("".join(json.dumps(row) + "\n" for row in data))
    kept = read_highlight_snapshots(path)
    assert len(kept) < len(data)
    assert kept[-1].session_time == 3.9
    assert any(snapshot.session_time == .5 for snapshot in kept)


def test_planner_rejects_captures_combining_different_races():
    import pytest
    data = snapshots()
    data[-1].track_info = {"track_name": "Daytona"}
    with pytest.raises(ValueError, match="different races"):
        build_plan(data)


def test_merged_clip_camera_follows_each_moment_but_stays_on_incident_for_yellow(tmp_path):
    player, *_ = make_player(tmp_path)
    player.segment["events"] = [
        {"kind": "overtake", "time": 55, "car_idx": 1},
        {"kind": "incident", "time": 65, "car_idx": 2},
        {"kind": "caution", "time": 66, "car_idx": 0},
    ]
    assert player.camera_target(50) == 1
    assert player.camera_target(60) == 2
    assert player.camera_target(67) == 2


def test_job_checkpoint_retries_a_brief_windows_file_lock(tmp_path, monkeypatch):
    import production.highlights as highlights
    original = type(tmp_path).replace
    attempts = []
    def replace(path, target):
        attempts.append(path)
        if len(attempts) == 1:
            raise PermissionError("temporary read lock")
        return original(path, target)
    monkeypatch.setattr(type(tmp_path), "replace", replace)
    monkeypatch.setattr(highlights.time, "sleep", lambda seconds: None)
    path = tmp_path / "programme.json"
    highlights.save_job(path, {"status": "ready"})
    assert len(attempts) == 2
    assert '"ready"' in path.read_text()


def test_seek_uses_single_command_and_retries_if_busy_replay_ignores_first():
    from production.highlights import wait_for_highlight_seek
    virtual = [0.0]
    class BusyController(Controller):
        def __init__(self):
            super().__init__()
            self.requests = 0
        def request_replay_session_time(self, session, seconds):
            self.requests += 1
            if self.requests >= 2:
                self.session, self.time = session, seconds
            return True
        def seek_replay_session_time(self, *args):
            raise AssertionError("Must use the isolated seek command")
        def pause_replay(self):
            raise AssertionError("Must not overwrite a pending seek with pause")
        def play_replay(self):
            raise AssertionError("Must not overwrite a pending seek with play")
    controller = BusyController()
    def sleep(seconds): virtual[0] += seconds
    assert wait_for_highlight_seek(controller, 2, 20, clock=lambda: virtual[0], sleep=sleep)
    assert controller.requests == 2
