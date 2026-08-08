from types import SimpleNamespace

from app import (
    build_featured_driver_country,
    build_featured_driver_profile,
    build_director_suggestions,
    build_featured_driver_story,
    build_featured_driver_image,
    build_featured_driver_render_info,
    featured_driver_position_info,
    update_overlay_featured_driver,
    update_overlay_focused_driver,
    build_producer_pit_road_rows,
    find_brand_graphic_for_name,
    handle_producer_command,
    log_race_event_for_item,
    reserve_sponsor_commercial_if_needed,
    split_sponsor_names,
    should_show_movers_graphic,
    show_sponsor_commercial_if_available,
    show_overlay_feature,
    sponsor_graphics_for_mentions,
    sponsor_mentions_for_message,
    should_update_overlay_for_camera_update,
)


class OverlaySpy:
    def __init__(self):
        self.stat_panels = []
        self.special_presentations = []
        self.featured = []

    def show_stat_panel(self, **kwargs):
        self.stat_panels.append(kwargs)
        return True

    def show_special_presentation(self, **kwargs):
        self.special_presentations.append(kwargs)

    def show_featured_driver(self, **kwargs):
        self.featured.append(kwargs)


class FeaturedDriverOverlaySpy:
    def __init__(self):
        self.featured = []

    def show_featured_driver(self, **kwargs):
        self.featured.append(kwargs)


class QueueSpy:
    def __init__(self):
        self.items = []

    def add(self, message, **kwargs):
        kwargs["message"] = message
        self.items.append(SimpleNamespace(**kwargs))


class ManualCrankEngineSpy:
    def __init__(self):
        self.calls = []

    def queue_manual_crank_it_up(self, results, sponsor_name="", track_info=None):
        self.calls.append((results, sponsor_name, track_info))
        return True


def test_camera_update_overlay_refresh_only_for_lineup():
    assert should_update_overlay_for_camera_update(SimpleNamespace(role="lineup"))
    assert not should_update_overlay_for_camera_update(SimpleNamespace(role="story"))
    assert not should_update_overlay_for_camera_update(SimpleNamespace(role="home"))
    assert not should_update_overlay_for_camera_update(SimpleNamespace(role=""))


class ProducerOverlaySpy:
    def __init__(self):
        self.styles = []
        self.events = []
        self.holder_id = ""
        self.holder_name = ""
        self.producer_notes = []
        self.incident_reviews = []
        self.interviews = []
        self.race_control_audit = []
        self.race_event_log = []

    def set_leaderboard_style(self, style):
        self.styles.append(style)
        return style

    def add_producer_event(self, **kwargs):
        self.events.append(kwargs)

    def claim_camera_control(self, client_id, producer_name="Producer"):
        if self.holder_id and self.holder_id != client_id:
            return False, f"Camera control is held by {self.holder_name}."
        self.holder_id = client_id
        self.holder_name = producer_name
        return True, f"{producer_name} has camera control."

    def release_camera_control(self, client_id):
        if self.holder_id and self.holder_id != client_id:
            return False, f"Camera control is held by {self.holder_name}."
        self.holder_id = ""
        self.holder_name = ""
        return True, "Camera control released."

    def camera_control_allows(self, client_id):
        return not self.holder_id or self.holder_id == client_id

    def camera_control_holder_name(self):
        return self.holder_name or "another producer"

    def add_producer_note(self, message, payload=None):
        clean_payload = dict(payload or {})
        clean_payload.pop("message", None)
        item = SimpleNamespace(message=message, **clean_payload)
        self.producer_notes.append(item)
        return item

    def add_incident_review(self, message, payload=None):
        clean_payload = dict(payload or {})
        clean_payload.pop("message", None)
        item = SimpleNamespace(message=message, **clean_payload)
        self.incident_reviews.append(item)
        return item

    def add_interview_queue_item(self, payload=None):
        item = SimpleNamespace(
            message=(payload or {}).get("message", ""),
            driver_name=(payload or {}).get("driver_name", ""),
        )
        self.interviews.append(item)
        return item

    def add_race_control_audit(self, message, payload=None):
        clean_payload = dict(payload or {})
        clean_payload.pop("message", None)
        item = SimpleNamespace(message=message, **clean_payload)
        self.race_control_audit.append(item)
        return item

    def add_race_event_log(self, title, message, payload=None, kind="race_event", status="logged"):
        item = SimpleNamespace(
            title=title,
            message=message,
            kind=kind,
            status=status,
            **dict(payload or {}),
        )
        self.race_event_log.append(item)
        return item

    def update_control_room_item_status(self, collection_name, item_id, status):
        return SimpleNamespace(id=item_id, status=status)


class CameraSpy:
    def __init__(self):
        self.mode = "auto"
        self.preferred_group = "TV1"
        self.focused = []

    def manual_focus_car(self, car_idx, group_name, source):
        self.focused.append((car_idx, group_name))
        return SimpleNamespace(
            status="switched",
            reason="manual",
            car_idx=car_idx,
            car_number="7",
            group_name=group_name,
        )

    def manual_focus_home(self, source):
        self.focused.append(("leader", "home"))
        return SimpleNamespace(
            status="switched",
            reason="leader",
            car_idx=1,
            car_number="1",
            group_name="TV Mixed",
        )


class ReplaySpy:
    def __init__(self):
        self.manual_started = 0
        self.manual_ended = 0
        self.reset_count = 0

    def begin_manual_control(self):
        self.manual_started += 1

    def end_manual_control(self):
        self.manual_ended += 1

    def reset(self):
        self.reset_count += 1


class RaceIntelligenceStub:
    def __init__(self, movers):
        self.movers = movers

    def get_biggest_movers(self, limit=5):
        return self.movers[:limit]


def mover(car_idx, gained):
    return SimpleNamespace(
        car_idx=car_idx,
        positions_gained=gained,
        current_position=4,
        car_number="24",
        driver_name="Dean Marsh",
        starting_position=9,
    )


def engine_with_movers(*movers):
    return SimpleNamespace(race_intelligence=RaceIntelligenceStub(list(movers)))


def item(category="race_story", target=24, message="Driver has gained positions."):
    return SimpleNamespace(
        category=category,
        camera_target_car_idx=target,
        message=message,
    )


def test_pit_updates_do_not_show_overlay_graphic():
    overlay = OverlaySpy()

    show_overlay_feature(
        item(category="caution_pit_summary", target=None),
        overlay,
        source=SimpleNamespace(get_results=lambda: []),
        engine=SimpleNamespace(),
    )

    assert overlay.stat_panels == []


def test_green_pit_cycle_update_shows_recent_stop_overlay():
    overlay = OverlaySpy()
    pit_state = SimpleNamespace(
        car_idx=4,
        car_number="24",
        driver_name="Dean Marsh",
        last_pit_lap=30,
        pit_entry_position=8,
        on_pit_road=False,
        last_pit_lane_seconds=42.0,
        last_pit_stop_seconds=7.0,
    )
    engine = SimpleNamespace(
        pit_strategy_detector=SimpleNamespace(driver_states={4: pit_state})
    )
    source = SimpleNamespace(
        get_lap=lambda: 34,
        get_results=lambda: [{"CarIdx": 4, "Position": 6}],
    )

    show_overlay_feature(
        item(category="green_pit_cycle_update", target=None),
        overlay,
        source=source,
        engine=engine,
    )

    panel = overlay.stat_panels[0]
    assert panel["kind"] == "green_pit_cycle"
    assert panel["title"] == "Green Flag Pit Cycle"
    assert panel["rows"][0]["value"] == "4 lap tires"
    assert "tires 4 laps old" in panel["rows"][0]["detail"]
    assert panel["minimum_interval"] == 30.0


def test_race_recap_overlay_shows_three_quarter_summary():
    overlay = OverlaySpy()
    race_state = SimpleNamespace(
        current_lap=60,
        total_laps=80,
        caution_count=2,
    )
    mover_summary = SimpleNamespace(
        car_idx=3,
        car_number="3",
        driver_name="Mover Driver",
        positions_gained=7,
        positions_lost=0,
    )
    drop_summary = SimpleNamespace(
        car_idx=4,
        car_number="4",
        driver_name="Fading Driver",
        positions_gained=0,
        positions_lost=5,
    )
    engine = SimpleNamespace(
        race_intelligence=SimpleNamespace(
            get_race_state=lambda: race_state,
            get_biggest_movers=lambda limit=1: [mover_summary],
            get_fading_drivers=lambda limit=1: [drop_summary],
        ),
        lead_change_count=3,
        fastest_lap_tracker=SimpleNamespace(
            fastest_car_idx=7,
            fastest_time=31.234,
            format_lap_time=lambda value: f"{value:.3f}",
        ),
    )
    source = SimpleNamespace(
        get_driver_lookup=lambda: {
            7: {"name": "Fast Driver", "number": "7"},
        }
    )

    show_overlay_feature(
        item(category="race_recap", target=None),
        overlay,
        source=source,
        engine=engine,
    )

    panel = overlay.stat_panels[0]
    assert panel["kind"] == "race_recap"
    assert panel["title"] == "Race Recap"
    assert panel["duration"] == 24.0
    assert panel["minimum_interval"] == 600.0
    labels = [row["label"] for row in panel["rows"]]
    assert labels == [
        "Distance",
        "Cautions",
        "Lead Changes",
        "Fastest Lap",
        "Biggest Mover",
        "Biggest Drop",
    ]
    assert panel["rows"][3]["value"] == "31.234"
    assert panel["rows"][3]["detail"] == "#7 Fast Driver"
    assert panel["rows"][4]["value"] == "+7"
    assert panel["rows"][4]["detail"] == "#3 Mover Driver"


def test_post_race_overlay_shows_end_cap_summary():
    overlay = OverlaySpy()
    race_state = SimpleNamespace(
        current_lap=80,
        total_laps=80,
        caution_count=4,
    )
    mover_summary = SimpleNamespace(
        car_idx=3,
        car_number="3",
        driver_name="Mover Driver",
        positions_gained=9,
        positions_lost=0,
    )
    engine = SimpleNamespace(
        race_intelligence=SimpleNamespace(
            get_race_state=lambda: race_state,
            get_biggest_movers=lambda limit=1: [mover_summary],
        ),
        lead_change_count=5,
        fastest_lap_tracker=SimpleNamespace(
            fastest_car_idx=7,
            fastest_time=31.234,
            format_lap_time=lambda value: f"{value:.3f}",
        ),
    )
    source = SimpleNamespace(
        get_results=lambda: [
            {"CarIdx": 1, "Position": 1, "LapsComplete": 80, "LapsLed": 34},
            {"CarIdx": 2, "Position": 2, "LapsComplete": 80, "LapsLed": 12},
            {"CarIdx": 7, "Position": 3, "LapsComplete": 79, "LapsLed": 0},
        ],
        get_driver_lookup=lambda: {
            1: {"name": "Winner Driver", "number": "1"},
            2: {"name": "Runner Up", "number": "2"},
            7: {"name": "Fast Driver", "number": "7"},
        },
    )

    show_overlay_feature(
        item(category="post_race", target=None),
        overlay,
        source=source,
        engine=engine,
    )

    panel = overlay.stat_panels[0]
    assert panel["kind"] == "race_end_cap"
    assert panel["title"] == "Race Recap"
    assert panel["subtitle"] == "Unofficial finish and key race notes"
    assert panel["duration"] == 300.0
    assert overlay.featured[0]["driver_name"] == "Winner Driver"
    assert overlay.featured[0]["position"] == 1
    labels = [row["label"] for row in panel["rows"]]
    assert labels == [
        "Winner",
        "Podium",
        "Race Story",
        "Most Laps Led",
        "Lead Lap Finishers",
        "Fastest Lap",
        "Biggest Mover",
    ]
    assert panel["rows"][0]["detail"] == "Winner Driver"
    assert "1st #1 Winner Driver" in panel["rows"][1]["detail"]
    assert panel["rows"][2]["value"] == "4Y / 5L"
    assert panel["rows"][3]["value"] == "34"
    assert panel["rows"][3]["detail"] == "#1 Winner Driver"
    assert panel["rows"][4]["value"] == "2/3"
    assert panel["rows"][5]["value"] == "31.234"
    assert panel["rows"][6]["value"] == "+9"


def test_producer_pit_road_rows_include_service_guess_and_tire_age():
    pit_state = SimpleNamespace(
        car_idx=4,
        car_number="24",
        driver_name="Dean Marsh",
        on_pit_road=False,
        last_pit_lap=30,
        pit_entry_position=8,
        pit_exit_position=5,
        last_pit_position_gain=3,
        last_pit_lane_seconds=38.0,
        last_pit_stop_seconds=6.5,
    )
    engine = SimpleNamespace(
        pit_strategy_detector=SimpleNamespace(driver_states={4: pit_state})
    )
    source = SimpleNamespace(
        get_lap=lambda: 36,
        get_results=lambda: [{"CarIdx": 4, "Position": 4, "LapsComplete": 36}],
    )

    rows = build_producer_pit_road_rows(source, engine)

    assert rows[0]["last_pit_lap"] == 30
    assert rows[0]["laps_since_pit"] == 6
    assert rows[0]["pit_lane_seconds"] == 38.0
    assert rows[0]["pit_stop_seconds"] == 6.5
    assert rows[0]["service_guess"] == "Possible two-tire or fuel-only track-position stop"
    assert rows[0]["position_summary"] == "in P8 / out P5 / +3 on pit road"


def test_director_suggestions_prioritize_leader_battle_mover_and_pits():
    state = {
        "leaderboard": [
            {
                "position": 1,
                "car_idx": 1,
                "car_number": "10",
                "driver_name": "Leader",
                "interval": "Leader",
                "position_delta": 0,
            },
            {
                "position": 2,
                "car_idx": 2,
                "car_number": "2",
                "driver_name": "Close Battle",
                "interval": "+0.42",
                "position_delta": 1,
            },
            {
                "position": 5,
                "car_idx": 5,
                "car_number": "55",
                "driver_name": "Big Mover",
                "interval": "+4.2",
                "position_delta": 7,
            },
        ],
        "pit_road": [
            {
                "status": "On pit road",
                "car_idx": 9,
                "car_number": "99",
                "driver_name": "Pit Stop",
            }
        ],
    }

    suggestions = build_director_suggestions(state)

    assert [item["title"] for item in suggestions] == [
        "Leader Story",
        "Closest Battle",
        "Big Mover",
        "Pit Road",
    ]
    assert suggestions[1]["car_idx"] == 2
    assert suggestions[2]["car_idx"] == 5


def test_biggest_movers_graphic_does_not_show_for_routine_position_gain():
    engine = engine_with_movers(mover(24, 3))

    assert should_show_movers_graphic(item(target=24), engine) is False


def test_biggest_movers_graphic_requires_target_to_be_top_mover():
    engine = engine_with_movers(mover(10, 8), mover(11, 7), mover(12, 6), mover(24, 9))

    assert should_show_movers_graphic(item(target=24), engine) is False


def test_biggest_movers_graphic_uses_shared_long_cooldown():
    overlay = OverlaySpy()
    engine = engine_with_movers(mover(24, 6))

    show_overlay_feature(item(target=24), overlay, engine=engine)

    assert overlay.stat_panels[0]["kind"] == "biggest_movers"
    assert overlay.stat_panels[0]["dedupe_key"] == "biggest_movers"
    assert overlay.stat_panels[0]["minimum_interval"] == 180.0


def test_points_standings_story_shows_top_twenty_graphic():
    overlay = OverlaySpy()
    source = SimpleNamespace(
        get_driver_lookup=lambda: {
            index: {
                "name": f"Driver {index}",
                "number": str(index),
                "league_stats_by_scope": [
                    {
                        "stats_scope": "season",
                        "points_position": str(index),
                        "points_to_next": str(index * 2),
                        "wins": "1" if index == 1 else "0",
                    }
                ],
            }
            for index in range(1, 24)
        }
    )

    show_overlay_feature(
        item(category="race_stat:points_standings:2", target=1),
        overlay,
        source=source,
    )

    panel = overlay.stat_panels[0]
    assert panel["kind"] == "points_standings"
    assert panel["title"] == "Championship Standings"
    assert panel["dedupe_key"] == "points_standings"
    assert len(panel["rows"]) == 20
    assert panel["rows"][0]["value"] == "1st"
    assert panel["rows"][0]["label"] == "#1 Driver 1"
    assert "2 pts to next" in panel["rows"][0]["detail"]


def test_race_event_log_records_pass_with_session_lap_and_camera():
    overlay = ProducerOverlaySpy()
    source = SimpleNamespace(
        get_session_type=lambda: "Race",
        get_lap=lambda: 42,
        get_current_session_num=lambda: 2,
        get_session_time=lambda: 765.4,
        get_driver_lookup=lambda: {
            24: {"name": "Dean Marsh", "number": "24"},
        },
    )
    broadcast_item = SimpleNamespace(
        category="race_story",
        dedupe_key="pass:dean marsh:24:made the pass",
        message="Dean Marsh completes the pass for fifth.",
        camera_target_car_idx=24,
    )
    camera_decision = SimpleNamespace(car_idx=24, car_number="24", group_name="TV2")

    log_race_event_for_item(broadcast_item, overlay, source, camera_decision)

    event = overlay.race_event_log[0]
    assert event.title == "Pass / Position"
    assert event.kind == "pass"
    assert event.session_type == "Race"
    assert event.session_lap == 42
    assert event.driver_name == "Dean Marsh"
    assert event.car_number == "24"
    assert event.camera_group == "TV2"
    assert event.replay_session_num == 2
    assert event.replay_session_time == 765.4


def test_race_event_log_records_incident_replay_metadata():
    overlay = ProducerOverlaySpy()
    source = SimpleNamespace(
        get_session_type=lambda: "Race",
        get_lap=lambda: 66,
        get_driver_lookup=lambda: {
            14: {"name": "Nick Hunt", "number": "14"},
        },
    )
    broadcast_item = SimpleNamespace(
        category="incident",
        message="Nick Hunt may have crashed.",
        camera_target_car_idx=14,
        camera_incident_group="Far Chase",
        replay_session_num=2,
        replay_session_time=1234.5,
    )

    log_race_event_for_item(broadcast_item, overlay, source, None)

    event = overlay.race_event_log[0]
    assert event.title == "Incident"
    assert event.kind == "incident"
    assert event.status == "needs review"
    assert event.camera_group == "Far Chase"
    assert event.replay_session_num == 2
    assert event.replay_session_time == 1234.5


def test_sponsor_mention_graphic_pops_for_rgc_and_autism():
    overlay = OverlaySpy()
    message = (
        "Tonight's coverage is presented by RGC Motorsports. "
        "Autism Awareness is about understanding and acceptance."
    )

    show_overlay_feature(item(category="sponsor_read", target=None, message=message), overlay)

    presentation = overlay.special_presentations[0]
    assert presentation["kind"] == "sponsor_bug"
    assert presentation["duration"] == 5.0
    assert "RGC Motorsports" in presentation["title"]
    assert "Autism Awareness" in presentation["title"]
    assert "/assets/rgc_motorsports.png" in presentation["graphics"]
    assert "/assets/autism_awareness.png" in presentation["graphics"]


def test_sponsor_commercial_plays_after_sponsor_read(monkeypatch):
    import app

    overlay = OverlaySpy()
    monkeypatch.setattr(app, "RACE_SPONSOR_VIDEOS", {"RGC Motorsports": "/assets/rgc_ad.mp4"})

    shown = show_sponsor_commercial_if_available(
        item(category="sponsor_read", target=None, message="Presented by RGC Motorsports."),
        overlay,
    )

    assert shown is True
    presentation = overlay.special_presentations[0]
    assert presentation["kind"] == "sponsor_commercial"
    assert presentation["video_url"] == "/assets/rgc_ad.mp4"
    assert presentation["duration"] == 60.0


def test_sponsor_commercial_reserves_broadcast_queue(monkeypatch):
    import app

    overlay = OverlaySpy()
    calls = []
    engine = SimpleNamespace(
        broadcast_queue=SimpleNamespace(
            reserve_busy_seconds=lambda seconds: calls.append(seconds)
        )
    )
    monkeypatch.setattr(app, "RACE_SPONSOR_VIDEOS", {"RGC Motorsports": "/assets/rgc_ad.mp4"})

    reserved = reserve_sponsor_commercial_if_needed(
        item(category="sponsor_read", target=None, message="Presented by RGC Motorsports."),
        overlay,
        engine,
    )

    assert reserved is True
    assert calls == [60.0]
    assert overlay.special_presentations[0]["kind"] == "sponsor_commercial"


def test_producer_command_can_queue_manual_crank_it_up():
    overlay = ProducerOverlaySpy()
    engine = ManualCrankEngineSpy()
    source = SimpleNamespace(get_results=lambda: [{"CarIdx": 1, "Position": 1}])

    handle_producer_command(
        "producer_crank_it_up",
        {"sponsor_name": "RGC Motorsports"},
        overlay,
        source=source,
        engine=engine,
        booth=None,
        camera_director=None,
    )

    assert engine.calls == [([{"CarIdx": 1, "Position": 1}], "RGC Motorsports", None)]
    assert overlay.events[0]["title"] == "Crank It Up"
    assert "Queued" in overlay.events[0]["message"]


def test_producer_command_queues_manual_sponsor_read(monkeypatch):
    import app

    overlay = ProducerOverlaySpy()
    queue = QueueSpy()
    engine = SimpleNamespace(broadcast_queue=queue)
    monkeypatch.setattr(app, "MANUAL_SPONSOR_INDEX", 0)
    monkeypatch.setattr(app, "configured_sponsor_names", lambda: ["RGC Motorsports"])
    monkeypatch.setattr(app, "RACE_SPONSOR_VIDEOS", {"RGC Motorsports": "/assets/rgc_ad.mp4"})

    handle_producer_command(
        "producer_sponsor_commercial",
        {},
        overlay,
        source=None,
        engine=engine,
        booth=None,
        camera_director=None,
    )

    assert queue.items[0].category == "sponsor_read"
    assert "RGC Motorsports" in queue.items[0].message
    assert overlay.events[0]["title"] == "Sponsor"
    assert "commercial" in overlay.events[0]["message"].lower()


def test_producer_command_can_switch_leaderboard_style():
    overlay = ProducerOverlaySpy()

    handle_producer_command(
        "leaderboard_ticker",
        {},
        overlay,
        source=None,
        engine=None,
        booth=None,
        camera_director=None,
    )

    assert overlay.styles == ["ticker"]
    assert overlay.events[0]["title"] == "Overlay"
    assert "ticker" in overlay.events[0]["message"]

    handle_producer_command(
        "leaderboard_flo",
        {},
        overlay,
        source=None,
        engine=None,
        booth=None,
        camera_director=None,
    )

    assert overlay.styles[-1] == "flo"


def test_manual_camera_follow_disables_auto_camera():
    overlay = ProducerOverlaySpy()
    camera = CameraSpy()
    replay = ReplaySpy()

    handle_producer_command(
        "camera_follow_driver",
        {"car_idx": 7, "group_name": "TV1"},
        overlay,
        source=SimpleNamespace(),
        engine=None,
        booth=None,
        camera_director=camera,
        replay_director=replay,
    )

    assert camera.mode == "off"
    assert camera.focused == [(7, "TV1")]
    assert replay.manual_started == 1
    assert any("Auto camera disabled" in event["message"] for event in overlay.events)


def test_manual_camera_follow_is_blocked_when_another_producer_has_control():
    overlay = ProducerOverlaySpy()
    camera = CameraSpy()
    overlay.claim_camera_control("producer-a", "Lee")

    handle_producer_command(
        "camera_follow_driver",
        {"client_id": "producer-b", "producer_name": "Helper", "car_idx": 7, "group_name": "TV1"},
        overlay,
        source=SimpleNamespace(),
        engine=None,
        booth=None,
        camera_director=camera,
    )

    assert camera.focused == []
    assert any("held by Lee" in event["message"] for event in overlay.events)


def test_producer_replay_speed_controls_source():
    overlay = ProducerOverlaySpy()
    speeds = []
    slow_flags = []

    def set_replay_speed(speed, slow_motion=False):
        speeds.append(speed)
        slow_flags.append(slow_motion)
        return True

    source = SimpleNamespace(set_replay_speed=set_replay_speed)
    camera = CameraSpy()
    replay = ReplaySpy()

    handle_producer_command(
        "replay_reverse",
        {},
        overlay,
        source=source,
        engine=None,
        booth=None,
        camera_director=camera,
        replay_director=replay,
    )
    handle_producer_command(
        "replay_slow_motion",
        {},
        overlay,
        source=source,
        engine=None,
        booth=None,
        camera_director=camera,
        replay_director=replay,
    )
    handle_producer_command(
        "replay_fast_play",
        {},
        overlay,
        source=source,
        engine=None,
        booth=None,
        camera_director=camera,
        replay_director=replay,
    )

    assert speeds == [-1, 1, 2]
    assert slow_flags == [False, True, False]
    assert replay.manual_started == 3
    assert all(event["kind"] == "replay" for event in overlay.events)


def test_producer_replay_reverse_and_fast_forward_cycle_three_speeds():
    overlay = ProducerOverlaySpy()
    speeds = []

    def set_replay_speed(speed, slow_motion=False):
        speeds.append(speed)
        return True

    source = SimpleNamespace(set_replay_speed=set_replay_speed)
    camera = CameraSpy()
    replay = ReplaySpy()

    for command in (
        "replay_reverse",
        "replay_reverse",
        "replay_reverse",
        "replay_reverse",
        "replay_normal_speed",
        "replay_fast_play",
        "replay_fast_play",
        "replay_fast_play",
        "replay_fast_play",
    ):
        handle_producer_command(
            command,
            {},
            overlay,
            source=source,
            engine=None,
            booth=None,
            camera_director=camera,
            replay_director=replay,
        )

    assert speeds == [-1, -2, -4, -4, 1, 2, 4, 8, 8]


def test_race_event_review_jumps_replay_without_following_driver():
    overlay = ProducerOverlaySpy()
    seeks = []
    pauses = []

    def seek_replay_session_time(session_num, session_time):
        seeks.append((session_num, session_time))
        return True

    source = SimpleNamespace(
        seek_replay_session_time=seek_replay_session_time,
        pause_replay=lambda: pauses.append(True) or True,
    )
    camera = CameraSpy()
    replay = ReplaySpy()

    handle_producer_command(
        "race_event_review",
        {
            "client_id": "producer-a",
            "producer_name": "Lee",
            "car_idx": 24,
            "session_lap": 51,
            "replay_session_num": 2,
            "replay_session_time": 1234.5,
            "pre_roll_seconds": 15,
        },
        overlay,
        source=source,
        engine=None,
        booth=None,
        camera_director=camera,
        replay_director=replay,
    )

    assert seeks == [(2, 1219.5)]
    assert pauses == [True]
    assert camera.mode == "off"
    assert camera.focused == []
    assert replay.manual_started == 1
    assert any("Loaded review lap 51" in event["message"] for event in overlay.events)


def test_race_event_review_falls_back_to_frame_rewind_when_seek_fails():
    overlay = ProducerOverlaySpy()
    rewinds = []
    return_live_calls = []

    source = SimpleNamespace(
        seek_replay_session_time=lambda *_: False,
        get_session_time=lambda: 1250.0,
        return_to_live=lambda: return_live_calls.append(True) or True,
        rewind_replay_frames=lambda frames: rewinds.append(frames) or True,
        pause_replay=lambda: True,
    )
    camera = CameraSpy()
    replay = ReplaySpy()

    handle_producer_command(
        "race_event_review",
        {
            "client_id": "producer-a",
            "producer_name": "Lee",
            "session_lap": 51,
            "replay_session_num": 2,
            "replay_session_time": 1234.5,
            "pre_roll_seconds": 15,
        },
        overlay,
        source=source,
        engine=None,
        booth=None,
        camera_director=camera,
        replay_director=replay,
    )

    assert return_live_calls == [True]
    assert rewinds == [1830]
    assert camera.focused == []
    assert any("frame rewind" in event["message"] for event in overlay.events)


def test_race_event_note_marks_event_log_item_for_review():
    overlay = ProducerOverlaySpy()
    overlay.add_race_event_log(
        "Incident",
        "Possible contact.",
        {"car_number": "34", "driver_name": "T.J. Lee"},
        kind="incident",
    )

    def update_race_event_log_item(item_id, status=None, note=None, producer_name=""):
        event = overlay.race_event_log[0]
        event.status = status
        event.message = f"{event.message} | Review note: {note}"
        event.created_by = producer_name
        return event

    overlay.update_race_event_log_item = update_race_event_log_item

    handle_producer_command(
        "race_event_note",
        {
            "item_id": 1,
            "status": "needs review",
            "note": "Check if the 34 came down.",
            "producer_name": "Race Control",
        },
        overlay,
        source=SimpleNamespace(),
        engine=None,
        booth=None,
        camera_director=CameraSpy(),
    )

    assert overlay.race_event_log[0].status == "needs review"
    assert "Check if the 34 came down." in overlay.race_event_log[0].message
    assert any("Marked event for review" in event["message"] for event in overlay.events)


def test_replay_return_live_restores_auto_camera_and_leader():
    overlay = ProducerOverlaySpy()
    camera = CameraSpy()
    camera.mode = "off"
    camera.replay_active = True
    replay = ReplaySpy()
    source = SimpleNamespace(return_to_live=lambda: True)

    handle_producer_command(
        "replay_return_live",
        {},
        overlay,
        source=source,
        engine=None,
        booth=None,
        camera_director=camera,
        replay_director=replay,
    )

    assert camera.mode == "auto"
    assert camera.replay_active is False
    assert camera.focused == [("leader", "home")]
    assert replay.reset_count == 1
    assert replay.manual_ended == 1


def test_producer_control_room_commands_update_overlay_lists():
    overlay = ProducerOverlaySpy()

    handle_producer_command(
        "producer_note_add",
        {
            "message": "Remind booth to mention stage points.",
            "car_idx": 34,
            "driver_name": "T.J. Lee",
        },
        overlay,
        source=SimpleNamespace(),
        engine=None,
        booth=None,
        camera_director=SimpleNamespace(),
    )
    handle_producer_command(
        "incident_review_add",
        {"message": "Review turn-four contact.", "car_number": "34"},
        overlay,
        source=SimpleNamespace(),
        engine=None,
        booth=None,
        camera_director=SimpleNamespace(),
    )
    handle_producer_command(
        "interview_queue_add",
        {"driver_name": "Race Winner"},
        overlay,
        source=SimpleNamespace(),
        engine=None,
        booth=None,
        camera_director=SimpleNamespace(),
    )

    assert overlay.producer_notes[0].message == "Remind booth to mention stage points."
    assert overlay.incident_reviews[0].message == "Review turn-four contact."
    assert overlay.interviews[0].driver_name == "Race Winner"
    assert [event["title"] for event in overlay.events] == [
        "Producer Note",
        "Incident Review",
        "Interview Queue",
    ]


def test_sponsor_mention_detection_is_message_based():
    assert sponsor_mentions_for_message("Thanks to RGC Motorsports.") == [
        "RGC Motorsports"
    ]
    assert sponsor_mentions_for_message("Supporting autism families.") == [
        "Autism Awareness"
    ]


def test_sponsor_graphics_use_expected_defaults():
    assert sponsor_graphics_for_mentions(
        ["RGC Motorsports", "Autism Awareness"]
    ) == [
        "/assets/rgc_motorsports.png",
        "/assets/autism_awareness.png",
    ]


def test_sponsor_names_can_be_split_from_profile_style_value():
    assert split_sponsor_names("Bob's Auto Parts; Autism Awareness | RGC Motorsports") == [
        "Bob's Auto Parts",
        "Autism Awareness",
        "RGC Motorsports",
    ]


def test_sponsor_graphic_matching_uses_configured_brand_graphics(monkeypatch):
    import app

    monkeypatch.setattr(
        app,
        "OVERLAY_BRAND_GRAPHICS",
        [
            "/assets/bobs_auto_parts.png",
            "/assets/autism_awareness.png",
        ],
    )

    assert find_brand_graphic_for_name("Bob's Auto Parts") == "/assets/bobs_auto_parts.png"


def test_crank_it_up_graphics_use_configured_sponsor_logo(monkeypatch):
    import app

    monkeypatch.setattr(app, "CRANK_IT_UP_SPONSOR_NAME", "Sponsor Two")
    monkeypatch.setattr(app, "CRANK_IT_UP_SPONSOR_GRAPHIC", "")
    monkeypatch.setattr(app, "RACE_SPONSOR_GRAPHICS", {"Sponsor Two": "/assets/sponsor_two.png"})

    assert app.crank_it_up_graphics() == [
        "/assets/sponsor_two.png",
        "/assets/crank_it_up.png",
    ]


def test_featured_driver_image_uses_manual_league_image_only():
    assert build_featured_driver_image({"car_image": "/assets/custom_driver.png"}) == "/assets/custom_driver.png"


def test_featured_driver_image_can_use_iracing_render_cache_fallback(monkeypatch):
    import app

    monkeypatch.setattr(app, "USE_IRACING_RENDERED_CAR_IMAGES", True)
    monkeypatch.setattr(app, "build_sim_racing_apps_car_render_info", lambda driver: {})
    monkeypatch.setattr(
        app,
        "build_iracing_render_image_url",
        lambda driver: "http://127.0.0.1:32034/pk_car.png?number=34",
    )

    assert build_featured_driver_image({"number": "34"}) == (
        "http://127.0.0.1:32034/pk_car.png?number=34"
    )


def test_featured_driver_image_prefers_sim_racing_apps_live_render(monkeypatch):
    import app

    monkeypatch.setattr(app, "USE_IRACING_RENDERED_CAR_IMAGES", True)
    monkeypatch.setattr(
        app,
        "build_sim_racing_apps_car_render_info",
        lambda driver: {
            "image_url": "http://127.0.0.1/SIMRacingApps/iRacing/pk_car.png?car=34",
            "number_style": {"color": "#ffffff", "background": "#000000"},
        },
    )
    monkeypatch.setattr(
        app,
        "build_iracing_render_image_url",
        lambda driver: "http://127.0.0.1:32034/pk_car.png?number=34",
    )

    assert build_featured_driver_image({"car_idx": 34, "number": "34"}) == (
        "http://127.0.0.1/SIMRacingApps/iRacing/pk_car.png?car=34"
    )
    assert build_featured_driver_render_info({"car_idx": 34, "number": "34"})["number_style"] == {
        "color": "#ffffff",
        "background": "#000000",
    }


def test_featured_driver_image_keeps_last_good_sim_racing_apps_render(monkeypatch):
    import app

    monkeypatch.setattr(app, "USE_IRACING_RENDERED_CAR_IMAGES", True)
    app._FEATURED_DRIVER_RENDER_INFO_CACHE.clear()
    calls = {"count": 0}

    def render_info(driver):
        calls["count"] += 1
        if calls["count"] == 1:
            return {
                "image_url": "http://127.0.0.1/SIMRacingApps/iRacing/pk_car.png?car=34",
                "number_style": {"color": "#ffffff", "background": "#000000"},
            }
        return {}

    monkeypatch.setattr(app, "build_sim_racing_apps_car_render_info", render_info)
    monkeypatch.setattr(app, "build_iracing_render_image_url", lambda driver: "")

    first = build_featured_driver_render_info({"car_idx": 34, "number": "34", "name": "T.J. Lee"})
    second = build_featured_driver_render_info({"car_idx": 34, "number": "34", "name": "T.J. Lee"})

    assert first == second
    assert second["image_url"].endswith("pk_car.png?car=34")


def test_opening_intro_driver_image_does_not_use_stale_render_cache(monkeypatch):
    import app

    monkeypatch.setattr(app, "USE_IRACING_RENDERED_CAR_IMAGES", True)
    monkeypatch.setattr(app, "build_sim_racing_apps_car_render_info", lambda driver: {})
    monkeypatch.setattr(
        app,
        "build_iracing_render_image_url",
        lambda driver: "http://127.0.0.1:32034/pk_car.png?stale=pole-car",
    )

    assert build_featured_driver_render_info(
        {"car_idx": 34, "number": "34"},
        require_live_render_match=True,
    ) == {"image_url": "", "number_style": {}}


def test_opening_intro_keeps_number_style_but_drops_generic_live_car_render(monkeypatch):
    import app

    monkeypatch.setattr(app, "USE_IRACING_RENDERED_CAR_IMAGES", True)
    monkeypatch.setattr(
        app,
        "build_sim_racing_apps_car_render_info",
        lambda driver: {
            "image_url": "http://127.0.0.1/SIMRacingApps/iRacing/pk_car.png?car=I34",
            "number_style": {"color": "#ffffff", "background": "#000000"},
        },
    )

    assert build_featured_driver_render_info(
        {"car_idx": 34, "number": "34"},
        require_live_render_match=True,
    ) == {
        "image_url": "",
        "number_style": {"color": "#ffffff", "background": "#000000"},
    }


def test_opening_intro_allows_paint_specific_live_car_render(monkeypatch):
    import app

    monkeypatch.setattr(app, "USE_IRACING_RENDERED_CAR_IMAGES", True)
    monkeypatch.setattr(
        app,
        "build_sim_racing_apps_car_render_info",
        lambda driver: {
            "image_url": (
                "http://127.0.0.1/SIMRacingApps/iRacing/pk_car.png?"
                "carPath=stockcars2%5Ccamaro2019&carCustPaint=car_num_90223.tga"
            ),
            "number_style": {"color": "#ffffff", "background": "#000000"},
        },
    )

    info = build_featured_driver_render_info(
        {"car_idx": 34, "number": "34"},
        require_live_render_match=True,
    )

    assert "carCustPaint" in info["image_url"]
    assert info["number_style"] == {"color": "#ffffff", "background": "#000000"}


def test_featured_driver_story_for_official_races_uses_country_only():
    driver = {
        "name": "T.J. Lee",
        "club": "Ohio",
        "country": "United States",
        "sponsor": "RGC Motorsports",
    }

    assert build_featured_driver_country(driver) == "United States"
    assert build_featured_driver_profile(driver) == ""
    assert (
        build_featured_driver_story(driver)
        == "United States"
    )


def test_featured_driver_country_normalizes_codes_and_iracing_clubs():
    assert build_featured_driver_country({"country": "USA"}) == "United States"
    assert build_featured_driver_country({"flair_name": "United States"}) == "United States"
    assert build_featured_driver_country({"FlairName": "Brazil"}) == "Brazil"
    assert build_featured_driver_country({"flair_country_code": "US"}) == "United States"
    assert build_featured_driver_country({"ClubName": "Ohio"}) == "Ohio, United States"
    assert build_featured_driver_country({"club": "Ontario"}) == "Ontario, Canada"


def test_featured_driver_story_for_league_races_can_use_extra_profile_details():
    driver = {
        "name": "T.J. Lee",
        "country": "United States",
        "team_name": "RGC Motorsports",
        "hometown": "Richmond",
        "state": "VA",
        "sponsor": "Autism Awareness",
    }

    assert build_featured_driver_country(driver) == "United States"
    assert build_featured_driver_profile(driver) == "RGC Motorsports • Richmond, VA"
    assert build_featured_driver_story(driver) == "RGC Motorsports • Richmond, VA"


def test_featured_driver_position_info_includes_gap_to_next_without_speed():
    info = featured_driver_position_info(
        34,
        [
            {"CarIdx": 7, "Position": 1, "Time": 0.0},
            {"CarIdx": 12, "Position": 2, "Time": 0.8},
            {
                "CarIdx": 34,
                "Position": 3,
                "Time": 1.25,
                "StartingPosition": 8,
                "Speed": 78.2,
            },
        ],
    )

    assert info["position"] == 3
    assert info["starting_position"] == 8
    assert info["position_delta"] == 5
    assert info["interval"] == "+0.45 to next"
    assert info["speed"] == ""


def test_featured_driver_position_info_includes_multiclass_position():
    info = featured_driver_position_info(
        34,
        [
            {"CarIdx": 7, "Position": 1, "Time": 0.0},
            {"CarIdx": 34, "Position": 2, "Time": 0.5},
            {"CarIdx": 12, "Position": 3, "Time": 1.0},
        ],
        driver_lookup={
            7: {"name": "Prototype Leader", "number": "7", "car_class_id": "p2", "car_class_short_name": "LMP2"},
            34: {"name": "GT Leader", "number": "34", "car_class_id": "gt3", "car_class_short_name": "GT3"},
            12: {"name": "GT Two", "number": "12", "car_class_id": "gt3", "car_class_short_name": "GT3"},
        },
    )

    assert info["position"] == 2
    assert info["class_name"] == "GT3"
    assert info["class_position"] == 1
    assert info["class_size"] == 2


def test_featured_driver_position_info_can_use_grid_position_as_start_for_intro():
    info = featured_driver_position_info(
        34,
        [
            {"CarIdx": 7, "Position": 0, "Time": 0.0},
            {"CarIdx": 34, "Position": 1, "Time": 0.5},
        ],
        use_position_as_start=True,
        include_interval=False,
    )

    assert info["position"] == 2
    assert info["starting_position"] == 2
    assert info["interval"] == ""
    assert info["speed"] == ""


def test_opening_field_rundown_driver_card_uses_starting_grid_and_country():
    overlay = FeaturedDriverOverlaySpy()
    camera_decision = SimpleNamespace(
        status="switched",
        car_idx=34,
        car_number="34",
    )
    source = SimpleNamespace(
        get_driver_lookup=lambda: {
            34: {
                "name": "T.J. Lee",
                "number": "34",
                "country": "United States",
            }
        },
        get_results=lambda: [],
        get_starting_grid=lambda: [
            {"CarIdx": 12, "Position": 0},
            {"CarIdx": 34, "Position": 1},
        ],
    )

    update_overlay_featured_driver(
        overlay,
        item(category="opening_field_rundown_2", target=34),
        source,
        camera_decision,
    )

    assert overlay.featured[0]["position"] == 2
    assert overlay.featured[0]["starting_position"] == 2
    assert overlay.featured[0]["country"] == "United States"
    assert overlay.featured[0]["story"] == ""
    assert overlay.featured[0]["speed"] == ""
    assert overlay.featured[0]["car_image_url"] == ""


def test_opening_field_rundown_driver_card_updates_when_camera_step_fails():
    overlay = FeaturedDriverOverlaySpy()
    camera_decision = SimpleNamespace(
        status="failed",
        car_idx=34,
        car_number="",
    )
    source = SimpleNamespace(
        get_driver_lookup=lambda: {
            34: {
                "name": "T.J. Lee",
                "number": "34",
                "country": "United States",
            }
        },
        get_results=lambda: [],
        get_starting_grid=lambda: [
            {"CarIdx": 12, "Position": 0},
            {"CarIdx": 34, "Position": 1},
        ],
    )

    update_overlay_focused_driver(
        overlay,
        source,
        camera_decision,
        opening_intro=True,
    )

    assert overlay.featured[0]["car_number"] == "34"
    assert overlay.featured[0]["driver_name"] == "T.J. Lee"
    assert overlay.featured[0]["position"] == 2
    assert overlay.featured[0]["country"] == "United States"
    assert overlay.featured[0]["car_image_url"] == ""


def test_opening_field_rundown_forces_number_only_card_even_with_live_car_image(monkeypatch):
    import app

    monkeypatch.setattr(
        app,
        "build_featured_driver_render_info",
        lambda driver, require_live_render_match=False: {
            "image_url": (
                "http://127.0.0.1/SIMRacingApps/iRacing/pk_car.png?"
                "carPath=stockcars%5Cfordmustang2022&carCustPaint=car_num_371788.tga"
            ),
            "number_style": {"color": "#ffffff", "background": "#111111"},
        },
    )
    overlay = FeaturedDriverOverlaySpy()
    camera_decision = SimpleNamespace(
        status="switched",
        car_idx=34,
        car_number="34",
    )
    source = SimpleNamespace(
        get_driver_lookup=lambda: {
            34: {
                "name": "T.J. Lee",
                "number": "34",
                "country": "United States",
            }
        },
        get_results=lambda: [],
        get_starting_grid=lambda: [{"CarIdx": 34, "Position": 0}],
    )

    update_overlay_focused_driver(
        overlay,
        source,
        camera_decision,
        opening_intro=True,
    )

    assert overlay.featured[0]["car_image_url"] == ""
    assert overlay.featured[0]["number_style"] == {
        "color": "#ffffff",
        "background": "#111111",
    }


def test_long_green_rundown_forces_number_only_card_even_with_live_car_image(monkeypatch):
    import app

    monkeypatch.setattr(
        app,
        "build_featured_driver_render_info",
        lambda driver, require_live_render_match=False: {
            "image_url": (
                "http://127.0.0.1/SIMRacingApps/iRacing/pk_car.png?"
                "carPath=stockcars%5Cfordmustang2022&carCustPaint=car_num_371788.tga"
            ),
            "number_style": {"color": "#ffee00", "background": "#222222"},
        },
    )
    overlay = FeaturedDriverOverlaySpy()
    camera_decision = SimpleNamespace(
        status="switched",
        car_idx=34,
        car_number="34",
    )
    source = SimpleNamespace(
        get_driver_lookup=lambda: {
            34: {
                "name": "T.J. Lee",
                "number": "34",
                "country": "United States",
            }
        },
        get_results=lambda: [
            {"CarIdx": 34, "Position": 4, "StartingPosition": 9, "Time": 4.2},
        ],
        get_starting_grid=lambda: [{"CarIdx": 34, "Position": 8}],
    )

    update_overlay_featured_driver(
        overlay,
        item(category="long_green_field_rundown_5", target=34),
        source,
        camera_decision,
    )

    assert overlay.featured[0]["position"] == 4
    assert overlay.featured[0]["starting_position"] == 9
    assert overlay.featured[0]["car_image_url"] == ""
    assert overlay.featured[0]["number_style"] == {
        "color": "#ffee00",
        "background": "#222222",
    }
