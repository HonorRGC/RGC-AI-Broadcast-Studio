from production.overlay import (
    PRODUCER_HTML,
    OVERLAY_HTML,
    OverlayEventConfig,
    OverlayServer,
    OverlayStateBuilder,
)


class OverlayTelemetry:
    def get_results(self):
        return [
            {"CarIdx": 7, "Position": 1, "LapsComplete": 12, "Time": 0.0},
            {"CarIdx": 3, "Position": 0, "LapsComplete": 12, "Time": 0.8},
            {"CarIdx": 9, "Position": 2, "LapsComplete": 12, "Time": 1.6},
        ]

    def get_driver_lookup(self):
        return {
            3: {"name": "Austin Peterson", "number": "77"},
            7: {"name": "Dean Marsh", "number": "24"},
            9: {"name": "Christian Abbate", "number": "09"},
        }

    def get_track_info(self):
        return {"track_name": "Nashville Superspeedway"}

    def get_session_type(self):
        return "Race"

    def get_lap(self):
        return 0

    def get_total_laps(self):
        return 80

    def get_session_flags(self):
        return 0

    def get_session_time_remaining(self):
        return 0.0


def test_overlay_state_includes_title_sponsor_track_and_lap():
    builder = OverlayStateBuilder(
        event_config=OverlayEventConfig(
            title="RGC 80 at Nashville",
            sponsor="Lee Family Racing",
            series="RGC Cup Series",
            leaderboard_style="ticker",
        )
    )

    state = builder.build_from_telemetry(OverlayTelemetry()).to_dict()

    assert state["event"]["title"] == "RGC 80 at Nashville"
    assert state["event"]["sponsor"] == "Lee Family Racing"
    assert state["event"]["series"] == "RGC Cup Series"
    assert state["event"]["leaderboard_style"] == "ticker"
    assert state["track_name"] == "Nashville Superspeedway"
    assert state["lap"] == 12
    assert state["total_laps"] == 80


def test_brand_graphic_can_show_in_any_session():
    assert "const src = pickRotatingGraphic(graphics || [], 4.5);" in OVERLAY_HTML
    assert "const isRace =" not in OVERLAY_HTML


def test_producer_html_includes_camera_control_handoff():
    assert "take-camera-control-button" in PRODUCER_HTML
    assert "release-camera-control-button" in PRODUCER_HTML
    assert "producer-share-link" in PRODUCER_HTML


def test_producer_html_includes_race_control_panel():
    assert "Race Control" in PRODUCER_HTML
    assert "race-admin-button" in PRODUCER_HTML
    assert 'data-race-action="throw_yellow"' in PRODUCER_HTML
    assert 'data-race-action="clear_penalty"' in PRODUCER_HTML


def test_overlay_server_camera_control_claim_release_state():
    server = OverlayServer()

    ok, message = server.claim_camera_control("producer-a", "Lee")
    assert ok is True
    assert "Lee" in message
    assert server.camera_control_allows("producer-a") is True
    assert server.camera_control_allows("producer-b") is False

    ok, message = server.release_camera_control("producer-a")
    assert ok is True
    assert "released" in message
    assert server.camera_control_allows("producer-b") is True


def test_overlay_share_url_prefers_tailscale_ip_for_remote_helper(monkeypatch):
    monkeypatch.setattr(OverlayServer, "tailscale_ip", staticmethod(lambda: "100.90.80.70"))
    monkeypatch.setattr(OverlayServer, "local_lan_ip", staticmethod(lambda: "192.168.1.44"))

    server = OverlayServer(host="0.0.0.0", port=8765)

    assert server.producer_url == "http://127.0.0.1:8765/producer"
    assert server.producer_share_url == "http://100.90.80.70:8765/producer"


def test_overlay_leaderboard_sorts_and_formats_zero_based_positions():
    state = OverlayStateBuilder().build_from_telemetry(OverlayTelemetry()).to_dict()

    leaderboard = state["leaderboard"]

    assert [entry["position"] for entry in leaderboard] == [1, 2, 3]
    assert leaderboard[0]["driver_name"] == "Austin Peterson"
    assert leaderboard[0]["car_number"] == "77"
    assert leaderboard[1]["driver_name"] == "Dean Marsh"
    assert leaderboard[2]["interval"] == "+1.6"


def test_overlay_leaderboard_includes_producer_driver_stats():
    class StatsTelemetry(OverlayTelemetry):
        def get_results(self):
            return [
                {
                    "CarIdx": 3,
                    "Position": 1,
                    "LapsComplete": 42,
                    "Time": 0.0,
                    "StartingPosition": 8,
                    "LapsLed": 6,
                    "Incidents": 4,
                    "LastPitLap": 31,
                    "LastPitStopSeconds": 7.4,
                    "LastPitLaneSeconds": 42.1,
                    "FastestTime": 30.125,
                },
                {
                    "CarIdx": 7,
                    "Position": 0,
                    "LapsComplete": 42,
                    "Time": 0.0,
                    "StartingPosition": 1,
                },
            ]

    state = OverlayStateBuilder().build_from_telemetry(StatsTelemetry()).to_dict()
    entry = next(driver for driver in state["leaderboard"] if driver["car_idx"] == 3)

    assert entry["starting_position"] == 8
    assert entry["position_delta"] == 6
    assert entry["laps_led"] == 6
    assert entry["incidents"] == 4
    assert entry["last_pit_lap"] == 31
    assert entry["last_pit_stop_seconds"] == 7.4
    assert entry["last_pit_lane_seconds"] == 42.1
    assert entry["fastest_lap"] == "30.125"
    assert entry["producer_note"].startswith("Big mover:")


def test_overlay_remembers_starting_grid_for_producer_stats():
    class GridTelemetry(OverlayTelemetry):
        def __init__(self):
            self.lap = 0
            self.results = [
                {"CarIdx": 3, "Position": 0, "LapsComplete": 0},
                {"CarIdx": 7, "Position": 1, "LapsComplete": 0},
                {"CarIdx": 9, "Position": 2, "LapsComplete": 0},
            ]

        def get_lap(self):
            return self.lap

        def get_results(self):
            return self.results

        def get_starting_grid(self):
            return [
                {"CarIdx": 3, "Position": 0},
                {"CarIdx": 7, "Position": 1},
                {"CarIdx": 9, "Position": 2},
            ]

    telemetry = GridTelemetry()
    builder = OverlayStateBuilder()
    builder.build_from_telemetry(telemetry)

    telemetry.lap = 10
    telemetry.results = [
        {"CarIdx": 9, "Position": 0, "LapsComplete": 10},
        {"CarIdx": 3, "Position": 1, "LapsComplete": 10},
        {"CarIdx": 7, "Position": 2, "LapsComplete": 10},
    ]
    state = builder.build_from_telemetry(telemetry).to_dict()
    entry = next(driver for driver in state["leaderboard"] if driver["car_idx"] == 7)

    assert entry["starting_position"] == 2
    assert entry["position_delta"] == -1


def test_overlay_uses_qualifying_as_late_start_fallback_for_producer_stats():
    class LateStartTelemetry(OverlayTelemetry):
        def get_lap(self):
            return 24

        def get_results(self):
            return [
                {"CarIdx": 9, "Position": 0, "LapsComplete": 24},
                {"CarIdx": 3, "Position": 1, "LapsComplete": 24},
                {"CarIdx": 7, "Position": 2, "LapsComplete": 24},
            ]

        def get_qualifying_results(self):
            return [
                {"CarIdx": 3, "Position": 0},
                {"CarIdx": 7, "Position": 1},
                {"CarIdx": 9, "Position": 2},
            ]

    state = OverlayStateBuilder().build_from_telemetry(LateStartTelemetry()).to_dict()
    entry = next(driver for driver in state["leaderboard"] if driver["car_idx"] == 9)

    assert entry["starting_position"] == 3
    assert entry["position_delta"] == 2


def test_overlay_marks_green_flag_state():
    class GreenTelemetry(OverlayTelemetry):
        def get_session_flags(self):
            return 0x00000004

    state = OverlayStateBuilder().build_from_telemetry(GreenTelemetry()).to_dict()

    assert state["green"] is True
    assert state["caution"] is False


def test_overlay_marks_green_when_race_is_underway_without_held_green_flag():
    state = OverlayStateBuilder().build_from_telemetry(OverlayTelemetry()).to_dict()

    assert state["green"] is True
    assert state["caution"] is False


def test_overlay_does_not_mark_practice_as_green_from_lap_data():
    class PracticeTelemetry(OverlayTelemetry):
        def get_session_type(self):
            return "Practice"

    state = OverlayStateBuilder().build_from_telemetry(PracticeTelemetry()).to_dict()

    assert state["green"] is False


def test_overlay_caution_overrides_green_highlight():
    class CautionTelemetry(OverlayTelemetry):
        def get_session_flags(self):
            return 0x00000008

    state = OverlayStateBuilder().build_from_telemetry(CautionTelemetry()).to_dict()

    assert state["green"] is False
    assert state["caution"] is True


def test_overlay_tracks_green_and_caution_laps_for_race_bar():
    class MutableTelemetry(OverlayTelemetry):
        flags = 0
        lap = 1

        def get_lap(self):
            return self.lap

        def get_results(self):
            return [{"CarIdx": 3, "Position": 0, "LapsComplete": self.lap}]

        def get_session_flags(self):
            return self.flags

    telemetry = MutableTelemetry()
    builder = OverlayStateBuilder()

    telemetry.lap = 1
    telemetry.flags = 0x00000004
    builder.build_from_telemetry(telemetry)
    telemetry.lap = 2
    telemetry.flags = 0x00000008
    state = builder.build_from_telemetry(telemetry).to_dict()

    assert state["lap_history"][0] == {"lap": 1, "status": "green"}
    assert state["lap_history"][1] == {"lap": 2, "status": "caution"}


def test_overlay_shows_time_gap_during_start_finish_lap_transition():
    class LapTransitionTelemetry(OverlayTelemetry):
        def get_results(self):
            return [
                {"CarIdx": 3, "Position": 0, "LapsComplete": 20, "Time": 0.0, "LapDistPct": 0.02},
                {"CarIdx": 7, "Position": 1, "LapsComplete": 19, "Time": 4.2, "LapDistPct": 0.98},
                {"CarIdx": 9, "Position": 2, "LapsComplete": 19, "Time": 9.9, "LapDistPct": 0.96},
            ]

    state = OverlayStateBuilder().build_from_telemetry(LapTransitionTelemetry()).to_dict()

    assert state["leaderboard"][1]["interval"] == "+4.2"
    assert state["leaderboard"][2]["interval"] == "+9.9"


def test_overlay_shows_computed_laps_down_when_car_is_truly_lapped():
    class LappedTelemetry(OverlayTelemetry):
        def get_results(self):
            return [
                {"CarIdx": 3, "Position": 0, "LapsComplete": 20, "Time": 0.0, "LapDistPct": 0.55},
                {"CarIdx": 7, "Position": 1, "LapsComplete": 19, "Time": 4.2, "LapDistPct": 0.20},
                {"CarIdx": 9, "Position": 2, "LapsComplete": 18, "Time": 9.9, "LapDistPct": 0.80},
            ]

    state = OverlayStateBuilder().build_from_telemetry(LappedTelemetry()).to_dict()

    assert state["leaderboard"][1]["interval"] == "-1 lap"
    assert state["leaderboard"][2]["interval"] == "-2 laps"


def test_overlay_shows_explicit_laps_down_before_time_gap():
    class LappedTelemetry(OverlayTelemetry):
        def get_results(self):
            return [
                {"CarIdx": 3, "Position": 0, "LapsComplete": 20, "Time": 0.0},
                {"CarIdx": 7, "Position": 1, "LapsComplete": 19, "Time": 4.2, "LapsBehind": 1},
                {"CarIdx": 9, "Position": 2, "LapsComplete": 18, "Time": 9.9, "LapsBehind": 2},
            ]

    state = OverlayStateBuilder().build_from_telemetry(LappedTelemetry()).to_dict()

    assert state["leaderboard"][1]["interval"] == "-1 lap"
    assert state["leaderboard"][2]["interval"] == "-2 laps"


def test_overlay_leaderboard_keeps_top_15_and_cycles_final_5():
    results = [
        {"CarIdx": car_idx, "Position": car_idx + 1, "LapsComplete": 10}
        for car_idx in range(25)
    ]
    drivers = {
        car_idx: {"name": f"Driver {car_idx + 1}", "number": str(car_idx + 1)}
        for car_idx in range(25)
    }

    first_window = OverlayStateBuilder(clock=lambda: 0).build_leaderboard(
        results, drivers
    )
    second_window = OverlayStateBuilder(clock=lambda: 8).build_leaderboard(
        results, drivers
    )

    assert [entry.position for entry in first_window[:15]] == list(range(1, 16))
    assert [entry.position for entry in second_window[:15]] == list(range(1, 16))
    assert [entry.position for entry in first_window[15:]] == [16, 17, 18, 19, 20]
    assert [entry.position for entry in second_window[15:]] == [21, 22, 23, 24, 25]
    assert len(first_window) == 20
    assert len(second_window) == 20


def test_overlay_state_includes_practice_session_countdown():
    class PracticeTelemetry(OverlayTelemetry):
        def get_session_type(self):
            return "Practice"

        def get_session_time_remaining(self):
            return 754.6

    state = OverlayStateBuilder().build_from_telemetry(PracticeTelemetry()).to_dict()

    assert state["session_type"] == "Practice"
    assert state["session_time_remaining"] == 754.6


def test_overlay_state_includes_qualifying_session_countdown():
    class QualifyingTelemetry(OverlayTelemetry):
        def get_session_type(self):
            return "Lone Qualify"

        def get_session_time_remaining(self):
            return 245

    state = OverlayStateBuilder().build_from_telemetry(QualifyingTelemetry()).to_dict()

    assert state["session_time_remaining"] == 245


def test_overlay_keeps_qualifying_board_until_race_results_arrive():
    class QualifyingTelemetry(OverlayTelemetry):
        def get_session_type(self):
            return "Qualifying"

        def get_results(self):
            return [
                {
                    "CarIdx": 3,
                    "Position": 0,
                    "LapsComplete": 0,
                    "FastestTime": 30.125,
                }
            ]

    class EarlyRaceTelemetry(OverlayTelemetry):
        def get_results(self):
            return []

    builder = OverlayStateBuilder()
    qualifying = builder.build_from_telemetry(QualifyingTelemetry()).to_dict()
    early_race = builder.build_from_telemetry(EarlyRaceTelemetry()).to_dict()

    assert qualifying["leaderboard"][0]["interval"] == "30.125"
    assert early_race["session_type"] == "Race"
    assert early_race["leaderboard"] == qualifying["leaderboard"]


def test_overlay_preserves_special_presentation():
    from production.overlay import OverlayServer

    server = OverlayServer()
    server.show_special_presentation(
        kind="rgc_anthem",
        title="RGC Anthem",
        subtitle="Presented by RGC Motorsports",
        duration=90,
    )

    server.update_from_telemetry(OverlayTelemetry())
    state = server.current_state_dict()

    assert state["special_presentation"]["kind"] == "rgc_anthem"
    assert state["special_presentation"]["title"] == "RGC Anthem"
    assert state["special_presentation"]["graphics"]


def test_overlay_special_presentation_updates_state_immediately():
    from production.overlay import OverlayServer

    server = OverlayServer()

    server.show_special_presentation(
        kind="crank_it_up",
        title="Crank It Up",
        subtitle="Presented by RGC Motorsports",
        graphics=["/assets/rgc_motorsports.png", "/assets/crank_it_up.png"],
        duration=28,
    )
    state = server.current_state_dict()

    assert state["special_presentation"]["kind"] == "crank_it_up"
    assert state["special_presentation"]["graphics"] == [
        "/assets/rgc_motorsports.png",
        "/assets/crank_it_up.png",
    ]


def test_overlay_preserves_stat_panel():
    from production.overlay import OverlayServer

    server = OverlayServer()
    shown = server.show_stat_panel(
        kind="biggest_movers",
        title="Biggest Movers",
        subtitle="Positions gained",
        rows=[{"label": "#24 Dean Marsh", "value": "+7", "detail": "Started 12th"}],
        duration=90,
    )

    server.update_from_telemetry(OverlayTelemetry())
    state = server.current_state_dict()

    assert shown is True
    assert state["stat_panel"]["kind"] == "biggest_movers"
    assert state["stat_panel"]["rows"][0]["value"] == "+7"


def test_crank_it_up_overlay_has_animated_hero_graphic():
    assert "crank-speaker-left" in OVERLAY_HTML
    assert "crank-speaker-right" in OVERLAY_HTML
    assert "crankSidePulse" in OVERLAY_HTML
    assert "setCrankSideGraphic" in OVERLAY_HTML


def test_overlay_has_center_session_clock():
    assert 'id="session-center"' in OVERLAY_HTML
    assert "buildSessionCenterLine" in OVERLAY_HTML
    assert "formatClock" in OVERLAY_HTML


def test_overlay_has_optional_ticker_leaderboard_and_compact_lap_bar():
    assert 'id="ticker-leaderboard"' in OVERLAY_HTML
    assert "normalizeLeaderboardStyle" in OVERLAY_HTML
    assert "renderTickerLeaderboard" in OVERLAY_HTML
    assert "leaderboard-ticker-mode" in OVERLAY_HTML
    assert "const maxSegments = 54" in OVERLAY_HTML
    assert "min-width: 0;" in OVERLAY_HTML
    assert "body.leaderboard-ticker-mode .special-presentation.race_sponsors" in OVERLAY_HTML
    assert "top: 174px" in OVERLAY_HTML


def test_race_sponsor_presentation_is_right_side_square():
    assert ".special-presentation.race_sponsors" in OVERLAY_HTML
    assert "right: 48px" in OVERLAY_HTML
    assert "width: 264px" in OVERLAY_HTML
    assert "height: 264px" in OVERLAY_HTML
    assert "grid-template-columns: 1fr" in OVERLAY_HTML


def test_sponsor_bug_overlay_is_compact_popup():
    assert ".special-presentation.sponsor_bug" in OVERLAY_HTML
    assert 'presentation.kind === "sponsor_bug"' in OVERLAY_HTML


def test_featured_driver_card_includes_position_line():
    from production.overlay import OverlayServer

    server = OverlayServer()
    server.show_featured_driver(
        car_number="34",
        driver_name="T.J. Lee",
        story="RGC Motorsports",
        position=4,
        starting_position=12,
        position_delta=8,
    )

    featured = server.current_state_dict()["featured_driver"]

    assert featured["position"] == 4
    assert featured["starting_position"] == 12
    assert featured["position_delta"] == 8
    assert "buildDriverCardPositionLine" in OVERLAY_HTML
    assert 'id="driver-card-position"' in OVERLAY_HTML


def test_crank_it_up_overlay_uses_logo_and_racing_speaker_style():
    assert ".special-presentation.crank_it_up .ceremony-logo" in OVERLAY_HTML
    assert "repeating-linear-gradient" in OVERLAY_HTML
    assert "drop-shadow(0 0 18px" in OVERLAY_HTML


def test_crank_it_up_graphics_default_to_sponsor_then_side_icon():
    from app import crank_it_up_graphics

    assert crank_it_up_graphics() == [
        "/assets/rgc_motorsports.png",
        "/assets/crank_it_up.png",
    ]


def test_overlay_server_has_paint_preview_route(tmp_path):
    from production.overlay import OverlayServer

    server = OverlayServer()
    server.paint_preview_dir = tmp_path
    handler = server.make_handler()

    assert hasattr(handler, "send_paint_preview")


def test_overlay_server_exposes_producer_assist_url():
    from production.overlay import OverlayServer

    server = OverlayServer()

    assert server.producer_url == "http://127.0.0.1:8765/producer"


def test_producer_assist_html_reads_overlay_state():
    assert "RGC Producer Assist" in PRODUCER_HTML
    assert 'fetch("/overlay/state"' in PRODUCER_HTML
    assert 'id="leaderboard-rows"' in PRODUCER_HTML
    assert 'id="detail-start"' in PRODUCER_HTML
    assert 'id="detail-delta"' in PRODUCER_HTML
    assert 'id="detail-led"' in PRODUCER_HTML
    assert 'id="detail-last-pit"' in PRODUCER_HTML
    assert "formatDelta(driver.position_delta)" in PRODUCER_HTML
    assert "formatPositionDelta(driver.position_delta)" in PRODUCER_HTML
    assert 'return "Even"' in PRODUCER_HTML
    assert "driver.producer_note" in PRODUCER_HTML
    assert 'id="producer-feed"' in PRODUCER_HTML
    assert "renderProducerFeed" in PRODUCER_HTML
    assert 'sendProducerCommand("camera_follow_leader")' in PRODUCER_HTML
    assert 'sendProducerCommand(on ? "openai_off" : "openai_on")' in PRODUCER_HTML
    assert 'sendProducerCommand("replay_pause")' in PRODUCER_HTML
    assert 'id="leaderboard-style-button"' in PRODUCER_HTML
    assert 'sendProducerCommand(style === "ticker" ? "leaderboard_side" : "leaderboard_ticker")' in PRODUCER_HTML
    assert "Move Camera to Driver" in PRODUCER_HTML
    assert 'id="director-suggestions-list"' in PRODUCER_HTML
    assert 'id="producer-note-input"' in PRODUCER_HTML
    assert 'id="incident-review-list"' in PRODUCER_HTML
    assert 'id="interview-queue-list"' in PRODUCER_HTML
    assert 'id="race-control-audit-list"' in PRODUCER_HTML
    assert "Discord Setup" in PRODUCER_HTML


def test_overlay_server_exposes_producer_feed_in_state():
    from production.overlay import OverlayServer

    server = OverlayServer()
    server.add_producer_event(
        kind="camera",
        title="Camera",
        message="following car #24 on TV1",
    )

    state = server.current_state_dict()

    assert state["producer_feed"][0]["kind"] == "camera"
    assert state["producer_feed"][0]["title"] == "Camera"
    assert state["producer_feed"][0]["message"] == "following car #24 on TV1"


def test_overlay_server_exposes_control_room_state():
    from production.overlay import OverlayServer

    server = OverlayServer()
    server.add_producer_note(
        "Watch the restart line.",
        {"car_idx": 4, "car_number": "24", "driver_name": "Dean Marsh"},
    )
    server.add_incident_review(
        "Review contact in turn two.",
        {"car_idx": 7, "car_number": "7", "driver_name": "Justin Clark"},
    )
    server.add_interview_queue_item(
        {"car_idx": 1, "car_number": "1", "driver_name": "Race Winner"}
    )
    server.add_race_control_audit(
        "Admin command sent.",
        {"ok": True, "producer_name": "Race Control"},
    )
    server.set_director_suggestions(
        [
            {
                "title": "Closest Battle",
                "message": "Cars are within half a second.",
                "car_idx": 7,
            }
        ]
    )

    state = server.current_state_dict()

    assert state["producer_notes"][0]["message"] == "Watch the restart line."
    assert state["incident_reviews"][0]["status"] == "needs review"
    assert state["interview_queue"][0]["driver_name"] == "Race Winner"
    assert state["race_control_audit"][0]["status"] == "sent"
    assert state["director_suggestions"][0]["title"] == "Closest Battle"


def test_overlay_server_queues_producer_commands():
    from production.overlay import OverlayServer

    server = OverlayServer()
    server.enqueue_command("auto_camera_off", {"reason": "human broadcaster"})

    commands = server.drain_commands()

    assert commands[0]["command"] == "auto_camera_off"
    assert commands[0]["payload"] == {"reason": "human broadcaster"}
    assert isinstance(commands[0]["created_at"], float)
    assert server.drain_commands() == []


def test_overlay_server_can_override_leaderboard_style_from_producer():
    from production.overlay import OverlayServer

    server = OverlayServer()
    assert server.current_state_dict()["event"]["leaderboard_style"] == "side"

    selected = server.set_leaderboard_style("ticker")
    state = server.current_state_dict()

    assert selected == "ticker"
    assert state["event"]["leaderboard_style"] == "ticker"
    assert state["control_state"]["leaderboard_style"] == "ticker"
