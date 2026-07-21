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
    build_producer_pit_road_rows,
    find_brand_graphic_for_name,
    handle_producer_command,
    split_sponsor_names,
    should_show_movers_graphic,
    show_overlay_feature,
    sponsor_graphics_for_mentions,
    sponsor_mentions_for_message,
)


class OverlaySpy:
    def __init__(self):
        self.stat_panels = []
        self.special_presentations = []

    def show_stat_panel(self, **kwargs):
        self.stat_panels.append(kwargs)
        return True

    def show_special_presentation(self, **kwargs):
        self.special_presentations.append(kwargs)


class FeaturedDriverOverlaySpy:
    def __init__(self):
        self.featured = []

    def show_featured_driver(self, **kwargs):
        self.featured.append(kwargs)


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
