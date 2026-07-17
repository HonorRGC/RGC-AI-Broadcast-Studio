from types import SimpleNamespace

from app import (
    build_featured_driver_image,
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


class ProducerOverlaySpy:
    def __init__(self):
        self.styles = []
        self.events = []

    def set_leaderboard_style(self, style):
        self.styles.append(style)
        return style

    def add_producer_event(self, **kwargs):
        self.events.append(kwargs)


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

    handle_producer_command(
        "camera_follow_driver",
        {"car_idx": 7, "group_name": "TV1"},
        overlay,
        source=SimpleNamespace(),
        engine=None,
        booth=None,
        camera_director=camera,
    )

    assert camera.mode == "off"
    assert camera.focused == [(7, "TV1")]
    assert any("Auto camera disabled" in event["message"] for event in overlay.events)


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


def test_featured_driver_image_does_not_auto_use_trading_paints_fields():
    assert (
        build_featured_driver_image(
            {
                "cust_id": "251830",
                "car_path": "stockcars2 camaro2019",
            }
        )
        == ""
    )
