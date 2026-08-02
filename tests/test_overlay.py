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
            cause="Autism Awareness",
            series="RGC Cup Series",
            leaderboard_style="ticker",
        )
    )

    state = builder.build_from_telemetry(OverlayTelemetry()).to_dict()

    assert state["event"]["title"] == "RGC 80 at Nashville"
    assert state["event"]["sponsor"] == "Lee Family Racing"
    assert state["event"]["cause"] == "Autism Awareness"
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
    assert "state.producer_leaderboard || state.leaderboard || []" in PRODUCER_HTML
    assert "max-height: calc(100vh - 280px)" not in PRODUCER_HTML


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
    assert leaderboard[2]["interval"] == "+1.60"


def test_overlay_leaderboard_can_include_live_number_style(monkeypatch):
    import production.overlay as overlay_module

    monkeypatch.setattr(overlay_module, "sim_racing_apps_session_car_count", lambda: 3)
    monkeypatch.setattr(
        overlay_module,
        "build_sim_racing_apps_car_render_info",
        lambda driver: {
            "number_style": {
                "color": "#ffffff",
                "background": "#000000",
                "outline": "#777777",
            }
        },
    )

    state = OverlayStateBuilder().build_from_telemetry(OverlayTelemetry()).to_dict()

    assert state["leaderboard"][0]["number_style"] == {
        "color": "#ffffff",
        "background": "#000000",
        "outline": "#777777",
    }
    assert "numberStyleAttribute" in OVERLAY_HTML
    assert 'class="ticker-num" style="${numberStyleAttribute' in OVERLAY_HTML


def test_overlay_leaderboard_keeps_last_good_number_style(monkeypatch):
    import production.overlay as overlay_module

    calls = {"count": 0}

    def render_info(driver):
        calls["count"] += 1
        if calls["count"] <= 3:
            return {
                "number_style": {
                    "color": "#ffffff",
                    "background": "#000000",
                }
            }
        return {}

    monkeypatch.setattr(overlay_module, "build_sim_racing_apps_car_render_info", render_info)
    builder = OverlayStateBuilder()

    first = builder.build_from_telemetry(OverlayTelemetry()).to_dict()
    second = builder.build_from_telemetry(OverlayTelemetry()).to_dict()

    assert first["leaderboard"][0]["number_style"] == {
        "color": "#ffffff",
        "background": "#000000",
    }
    assert second["leaderboard"][0]["number_style"] == {
        "color": "#ffffff",
        "background": "#000000",
    }


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


def test_overlay_leaderboard_includes_multiclass_position():
    class MulticlassTelemetry(OverlayTelemetry):
        def get_results(self):
            return [
                {"CarIdx": 1, "Position": 0, "LapsComplete": 12},
                {"CarIdx": 2, "Position": 1, "LapsComplete": 12},
                {"CarIdx": 3, "Position": 2, "LapsComplete": 12},
                {"CarIdx": 4, "Position": 3, "LapsComplete": 12},
            ]

        def get_driver_lookup(self):
            return {
                1: {"name": "Prototype Leader", "number": "1", "car_class_id": "p2", "car_class_short_name": "LMP2"},
                2: {"name": "GT Leader", "number": "21", "car_class_id": "gt3", "car_class_short_name": "GT3"},
                3: {"name": "Prototype Two", "number": "2", "car_class_id": "p2", "car_class_short_name": "LMP2"},
                4: {"name": "GT Two", "number": "22", "car_class_id": "gt3", "car_class_short_name": "GT3"},
            }

    state = OverlayStateBuilder().build_from_telemetry(MulticlassTelemetry()).to_dict()

    assert state["leaderboard"][0]["class_name"] == "LMP2"
    assert state["leaderboard"][0]["class_position"] == 1
    assert state["leaderboard"][1]["class_name"] == "GT3"
    assert state["leaderboard"][1]["class_position"] == 1
    assert state["leaderboard"][3]["class_position"] == 2
    assert "entry.class_position" in OVERLAY_HTML


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


def test_overlay_lap_history_renders_as_solid_status_runs():
    assert "compactLapHistoryRuns" in OVERLAY_HTML
    assert "segment.style.flexGrow" in OVERLAY_HTML
    assert "gap: 0;" in OVERLAY_HTML
    assert "border-radius: 999px;" in OVERLAY_HTML


def test_overlay_shows_time_gap_during_start_finish_lap_transition():
    class LapTransitionTelemetry(OverlayTelemetry):
        def get_results(self):
            return [
                {"CarIdx": 3, "Position": 0, "LapsComplete": 20, "Time": 0.0, "LapDistPct": 0.02},
                {"CarIdx": 7, "Position": 1, "LapsComplete": 19, "Time": 4.2, "LapDistPct": 0.98},
                {"CarIdx": 9, "Position": 2, "LapsComplete": 19, "Time": 9.9, "LapDistPct": 0.96},
            ]

    state = OverlayStateBuilder().build_from_telemetry(LapTransitionTelemetry()).to_dict()

    assert state["leaderboard"][1]["interval"] == "+4.20"
    assert state["leaderboard"][2]["interval"] == "+9.90"


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
    class FullFieldTelemetry(OverlayTelemetry):
        def get_results(self):
            return [
                {"CarIdx": car_idx, "Position": car_idx + 1, "LapsComplete": 10}
                for car_idx in range(25)
            ]

        def get_driver_lookup(self):
            return {
                car_idx: {"name": f"Driver {car_idx + 1}", "number": str(car_idx + 1)}
                for car_idx in range(25)
            }

    first_state = OverlayStateBuilder(clock=lambda: 0).build_from_telemetry(
        FullFieldTelemetry()
    ).to_dict()
    second_state = OverlayStateBuilder(clock=lambda: 8).build_from_telemetry(
        FullFieldTelemetry()
    ).to_dict()
    first_window = first_state["leaderboard"]
    second_window = second_state["leaderboard"]

    assert [entry["position"] for entry in first_window[:15]] == list(range(1, 16))
    assert [entry["position"] for entry in second_window[:15]] == list(range(1, 16))
    assert [entry["position"] for entry in first_window[15:]] == [16, 17, 18, 19, 20]
    assert [entry["position"] for entry in second_window[15:]] == [21, 22, 23, 24, 25]
    assert len(first_window) == 20
    assert len(second_window) == 20
    assert len(first_state["producer_leaderboard"]) == 25
    assert [entry["position"] for entry in first_state["producer_leaderboard"]] == list(
        range(1, 26)
    )


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
        video_url="/assets/rgc_ad.mp4",
        duration=28,
    )
    state = server.current_state_dict()

    assert state["special_presentation"]["kind"] == "crank_it_up"
    assert state["special_presentation"]["graphics"] == [
        "/assets/rgc_motorsports.png",
        "/assets/crank_it_up.png",
    ]
    assert state["special_presentation"]["video_url"] == "/assets/rgc_ad.mp4"


def test_crank_it_up_presentation_hides_featured_driver_card():
    from production.overlay import OverlayServer

    server = OverlayServer()
    server.show_featured_driver(
        car_number="34",
        driver_name="T.J. Lee",
        car_idx=34,
        duration=30,
    )
    assert server.current_state_dict()["featured_driver"]["driver_name"] == "T.J. Lee"

    server.show_special_presentation(
        kind="crank_it_up",
        title="Crank It Up",
        subtitle="Presented by RGC Motorsports",
        graphics=["/assets/rgc_motorsports.png", "/assets/crank_it_up.png"],
        duration=28,
    )

    state = server.current_state_dict()
    assert state["special_presentation"]["kind"] == "crank_it_up"
    assert state["featured_driver"] is None

    server.show_featured_driver(
        car_number="24",
        driver_name="Another Driver",
        car_idx=24,
        duration=30,
    )
    assert server.current_state_dict()["featured_driver"] is None


def test_overlay_can_clear_special_presentation_immediately():
    from production.overlay import OverlayServer

    server = OverlayServer()
    server.show_special_presentation(
        kind="sponsor_commercial",
        title="RGC Motorsports",
        subtitle="Commercial Break",
        video_url="/assets/rgc_ad.mp4",
        duration=60,
    )

    server.clear_special_presentation()

    assert server.current_state_dict()["special_presentation"] is None


def test_commercial_video_clears_overlay_when_playback_ends():
    assert "/overlay/clear-special-presentation" in OVERLAY_HTML
    assert 'video.addEventListener("ended", clearCommercialPresentationFromVideo)' in OVERLAY_HTML
    assert "installCommercialVideoHandlers();" in OVERLAY_HTML
    assert "shouldHideDriverCardForPresentation" in OVERLAY_HTML
    assert "presentation.kind === \"crank_it_up\"" in OVERLAY_HTML


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


def test_overlay_has_session_clock_above_sponsor_card():
    assert 'id="session-center"' in OVERLAY_HTML
    assert 'id="session-center" class="session-center hidden"></div>' in OVERLAY_HTML
    assert "left: 50%;" in OVERLAY_HTML
    assert "body.leaderboard-ticker-mode .session-center" in OVERLAY_HTML
    assert "body.leaderboard-flo-mode .session-center" in OVERLAY_HTML
    assert "top: 188px" in OVERLAY_HTML
    assert "buildSessionCenterLine" in OVERLAY_HTML
    assert "formatClock" in OVERLAY_HTML


def test_overlay_has_top_center_under_caution_badge():
    assert 'id="caution-status" class="caution-status hidden">Under Caution</div>' in OVERLAY_HTML
    assert "body.leaderboard-ticker-mode .caution-status" in OVERLAY_HTML
    assert 'document.getElementById("caution-status").classList.toggle("hidden", !state.caution)' in OVERLAY_HTML


def test_overlay_has_optional_ticker_leaderboard_and_compact_lap_bar():
    assert 'id="ticker-leaderboard"' in OVERLAY_HTML
    assert 'id="flo-leaderboard"' in OVERLAY_HTML
    assert 'id="flo-sponsor-logo"' in OVERLAY_HTML
    assert 'id="flo-series-logo"' in OVERLAY_HTML
    assert 'id="flo-row-second"' in OVERLAY_HTML
    assert 'id="flo-row-cycle" class="flo-row flo-row-cycle"' in OVERLAY_HTML
    assert "flo-row-cycle .flo-entry" in OVERLAY_HTML
    assert 'content: "CYCLE"' in OVERLAY_HTML
    assert "ticker-reset" in OVERLAY_HTML
    assert "Back to Leader" in OVERLAY_HTML
    assert "#d7bd55" not in OVERLAY_HTML
    assert "grid-template-columns: 210px minmax(0, 1fr) 210px" in OVERLAY_HTML
    assert "max-width: 184px" in OVERLAY_HTML
    assert 'setText("flo-series-text", event.series || event.sponsor || "RGC AI")' in OVERLAY_HTML
    assert 'id="ticker-label"' in OVERLAY_HTML
    assert 'id="leaderboard-series"' in OVERLAY_HTML
    assert 'id="cause-line"' in OVERLAY_HTML
    assert "normalizeLeaderboardStyle" in OVERLAY_HTML
    assert "renderTickerLeaderboard" in OVERLAY_HTML
    assert "renderFloLeaderboard" in OVERLAY_HTML
    assert "setLeaderboardSeries" in OVERLAY_HTML
    assert '${series} - Leaderboard' not in OVERLAY_HTML
    assert 'setText("ticker-label", "Leaderboard")' in OVERLAY_HTML
    assert "animation: tickerScroll 62s linear infinite" in OVERLAY_HTML
    assert "font-size: 14px;" in OVERLAY_HTML
    assert "min-width: 50px;" in OVERLAY_HTML
    assert "border-left: 0;" in OVERLAY_HTML
    assert "background: transparent;" in OVERLAY_HTML
    assert "leaderboard-ticker-mode" in OVERLAY_HTML
    assert "leaderboard-flo-mode" in OVERLAY_HTML
    assert "compactLapHistoryRuns" in OVERLAY_HTML
    assert "segment.style.flexGrow" in OVERLAY_HTML
    assert "min-width: 0;" in OVERLAY_HTML
    assert "body.leaderboard-ticker-mode .special-presentation.race_sponsors" in OVERLAY_HTML
    assert "top: 226px" in OVERLAY_HTML
    assert "body.leaderboard-flo-mode .special-presentation.race_sponsors" in OVERLAY_HTML
    assert "top: 242px" in OVERLAY_HTML
    assert "body.leaderboard-ticker-mode .special-presentation.sponsor_bug" in OVERLAY_HTML
    assert "top: 224px" in OVERLAY_HTML
    assert "body.leaderboard-flo-mode .special-presentation.sponsor_bug" in OVERLAY_HTML


def test_overlay_title_branding_is_larger_and_more_polished():
    assert "max-width: 220px" in OVERLAY_HTML
    assert "max-height: 58px" in OVERLAY_HTML
    assert "height: 84px" in OVERLAY_HTML
    assert "grid-template-columns: minmax(205px, 315px) minmax(360px, 1fr) minmax(320px, 430px)" in OVERLAY_HTML
    assert ".cause-line" in OVERLAY_HTML
    assert 'class="title-center"' in OVERLAY_HTML
    assert 'class="event-meta title-right"' in OVERLAY_HTML
    assert 'class="track-pill"' in OVERLAY_HTML
    assert ".leaderboard-series" in OVERLAY_HTML


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
        country="United States",
        position=4,
        starting_position=12,
        position_delta=8,
        interval="+0.45 to next",
        speed="175 mph",
        number_style={
            "color": "#FFFFFF",
            "background": "#000000",
            "outline": "#777777",
            "font_family": "Arial",
            "font_style": "italic",
            "unsafe": "nope",
        },
    )

    featured = server.current_state_dict()["featured_driver"]

    assert featured["position"] == 4
    assert featured["country"] == "United States"
    assert featured["starting_position"] == 12
    assert featured["position_delta"] == 8
    assert featured["interval"] == "+0.45 to next"
    assert featured["speed"] == "175 mph"
    assert featured["number_style"] == {
        "color": "#ffffff",
        "background": "#000000",
        "outline": "#777777",
        "font_family": "Arial",
        "font_style": "italic",
    }
    assert "buildDriverCardPositionLine" in OVERLAY_HTML
    assert "pieces.push(driver.speed)" not in OVERLAY_HTML
    assert "buildDriverCardRankLine" in OVERLAY_HTML
    assert 'id="driver-card-position"' in OVERLAY_HTML
    assert 'id="driver-card-country"' in OVERLAY_HTML
    assert ".driver-card-country" in OVERLAY_HTML
    assert ".driver-card-flag" in OVERLAY_HTML
    assert ".driver-card-country-text" in OVERLAY_HTML
    assert "renderDriverCardCountry" in OVERLAY_HTML
    assert "https://flagcdn.com/w40/" in OVERLAY_HTML
    assert "onerror=\"this.remove()\"" in OVERLAY_HTML
    assert "formatDriverCountry" in OVERLAY_HTML
    assert "countryFlag" in OVERLAY_HTML
    assert "countryCodeFromNameOrCode" in OVERLAY_HTML
    assert "flagEmojiFromCode" in OVERLAY_HTML
    assert '"united states": "US"' in OVERLAY_HTML
    assert '"brazil": "BR"' in OVERLAY_HTML
    assert "🇺🇸" in OVERLAY_HTML
    assert 'id="driver-card-position-rank"' in OVERLAY_HTML
    assert 'id="driver-card-car-img"' in OVERLAY_HTML
    assert "image.onerror" in OVERLAY_HTML
    assert ".driver-card-image.image-loading" in OVERLAY_HTML
    assert 'image.removeAttribute("src")' in OVERLAY_HTML
    assert "image.dataset.currentKey !== imageKey" in OVERLAY_HTML
    assert "applyDriverCardNumberStyle" in OVERLAY_HTML
    assert ".driver-card-image.image-failed" in OVERLAY_HTML


def test_featured_driver_card_proxies_iracing_render_urls():
    from production.overlay import OverlayServer, is_safe_iracing_render_url

    raw_url = "http://127.0.0.1:32034/pk_car.png?size=2&carPath=stockcars%5Cchevy&number=34"
    assert is_safe_iracing_render_url(raw_url)

    server = OverlayServer()
    server.show_featured_driver(
        car_number="34",
        driver_name="T.J. Lee",
        car_image_url=raw_url,
    )

    featured = server.current_state_dict()["featured_driver"]
    assert featured["car_image_url"].startswith("/iracing-render?url=")
    assert "pk_car.png" in featured["car_image_url"]


def test_featured_driver_card_proxies_sim_racing_apps_render_urls():
    from production.overlay import OverlayServer, is_safe_iracing_render_url

    raw_url = "http://127.0.0.1/SIMRacingApps/iRacing/pk_car.png?carCustPaint=C%3A%5Cpaint%5Ccar.tga"
    assert is_safe_iracing_render_url(raw_url)

    server = OverlayServer()
    server.show_featured_driver(
        car_number="34",
        driver_name="T.J. Lee",
        car_idx=12,
        car_image_url=raw_url,
    )

    featured = server.current_state_dict()["featured_driver"]
    assert featured["car_idx"] == 12
    assert featured["car_image_url"].startswith("/iracing-render?url=")
    assert "SIMRacingApps" in featured["car_image_url"]
    assert 'image.removeAttribute("src");' in OVERLAY_HTML


def test_featured_driver_card_does_not_proxy_external_images():
    from production.overlay import OverlayServer, is_safe_iracing_render_url

    raw_url = "https://example.com/car.png"
    assert not is_safe_iracing_render_url(raw_url)

    server = OverlayServer()
    server.show_featured_driver(
        car_number="34",
        driver_name="T.J. Lee",
        car_image_url=raw_url,
    )

    featured = server.current_state_dict()["featured_driver"]
    assert featured["car_image_url"] == raw_url


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
    assert hasattr(handler, "send_iracing_render_proxy")


def test_overlay_server_exposes_producer_assist_url():
    from production.overlay import OverlayServer

    server = OverlayServer()

    assert server.producer_url == "http://127.0.0.1:8765/producer"


def test_producer_assist_html_reads_overlay_state():
    assert "RGC Producer Assist" in PRODUCER_HTML
    assert 'fetch("/overlay/state"' in PRODUCER_HTML
    assert 'id="leaderboard-rows"' in PRODUCER_HTML
    assert 'class="left-rail"' in PRODUCER_HTML
    assert 'id="detail-start"' in PRODUCER_HTML
    assert 'id="detail-delta"' in PRODUCER_HTML
    assert 'id="detail-led"' in PRODUCER_HTML
    assert "Possible Incidents" in PRODUCER_HTML
    assert 'id="detail-last-pit"' in PRODUCER_HTML
    assert "formatDelta(driver.position_delta)" in PRODUCER_HTML
    assert "formatPositionDelta(driver.position_delta)" in PRODUCER_HTML
    assert 'return "Even"' in PRODUCER_HTML
    assert "driver.producer_note" in PRODUCER_HTML
    assert 'id="producer-feed"' in PRODUCER_HTML
    assert "renderProducerFeed" in PRODUCER_HTML
    assert 'sendProducerCommand("camera_follow_leader")' in PRODUCER_HTML
    assert 'id="manual-camera-group-select"' in PRODUCER_HTML
    assert 'data-camera-group="Far Chase"' in PRODUCER_HTML
    assert 'data-camera-group="Rear Chase"' in PRODUCER_HTML
    assert 'data-camera-group="Cockpit"' in PRODUCER_HTML
    assert "selectedManualCameraGroup" in PRODUCER_HTML
    assert 'sendProducerCommand(on ? "openai_off" : "openai_on")' in PRODUCER_HTML
    assert 'sendProducerCommand("replay_pause")' in PRODUCER_HTML
    assert 'id="slow-motion-button"' in PRODUCER_HTML
    assert 'sendProducerCommand("replay_reverse")' in PRODUCER_HTML
    assert 'id="jump-back-button"' not in PRODUCER_HTML
    assert 'sendProducerCommand("replay_rewind", { seconds: 10 })' not in PRODUCER_HTML
    assert 'sendProducerCommand("replay_slow_motion")' in PRODUCER_HTML
    assert 'sendProducerCommand("replay_fast_play")' in PRODUCER_HTML
    assert 'id="jump-forward-button"' not in PRODUCER_HTML
    assert 'sendProducerCommand("replay_fast_forward", { seconds: 10 })' not in PRODUCER_HTML
    assert "Manual Show Features" in PRODUCER_HTML
    assert 'id="manual-crank-it-up-button"' in PRODUCER_HTML
    assert 'id="manual-sponsor-button"' in PRODUCER_HTML
    assert 'sendProducerCommand("producer_crank_it_up")' in PRODUCER_HTML
    assert 'sendProducerCommand("producer_sponsor_commercial")' in PRODUCER_HTML
    assert 'id="leaderboard-style-button"' in PRODUCER_HTML
    assert 'id="broadcaster-volume-slider"' in PRODUCER_HTML
    assert 'id="music-volume-slider"' in PRODUCER_HTML
    assert 'sendProducerCommand("set_audio_volume"' in PRODUCER_HTML
    assert '"leaderboard_flo"' in PRODUCER_HTML
    assert "Leaderboard: Flo Top" in PRODUCER_HTML
    assert "Move Camera to Driver" in PRODUCER_HTML
    assert 'id="director-suggestions-list"' in PRODUCER_HTML
    assert "Live booth cues with race data" in PRODUCER_HTML
    assert 'id="producer-note-input"' in PRODUCER_HTML
    assert 'id="incident-review-list"' not in PRODUCER_HTML
    assert 'id="interview-queue-list"' in PRODUCER_HTML
    assert 'id="race-event-log-list"' in PRODUCER_HTML
    assert 'class="panel wide"' in PRODUCER_HTML
    assert 'id="race-control-audit-list"' in PRODUCER_HTML
    assert "event-log-table" in PRODUCER_HTML
    assert "renderRaceEventLog" in PRODUCER_HTML
    assert "reviewRaceEvent" in PRODUCER_HTML
    assert "noteRaceEvent" in PRODUCER_HTML
    assert 'sendProducerCommand("race_event_review"' in PRODUCER_HTML
    assert 'sendProducerCommand("race_event_note"' in PRODUCER_HTML
    assert "Session</div>" in PRODUCER_HTML
    assert "Camera</div>" in PRODUCER_HTML
    assert "Discord Setup" in PRODUCER_HTML


def test_producer_assist_prioritizes_live_control_room_panels():
    suggestions_index = PRODUCER_HTML.index("<h3>Director Suggestions</h3>")
    focus_index = PRODUCER_HTML.index("<h3>Current Broadcast Focus</h3>")
    pit_road_index = PRODUCER_HTML.index("<h3>Pit Road / Strategy</h3>")
    camera_index = PRODUCER_HTML.index('id="follow-driver-button"')
    race_control_index = PRODUCER_HTML.index("<h3>Race Control</h3>")
    interview_index = PRODUCER_HTML.index("<h3>Interview Queue</h3>")
    event_log_index = PRODUCER_HTML.index("<h3>Race Event Log</h3>")
    audit_index = PRODUCER_HTML.index("<h3>Race Control Audit</h3>")
    discord_index = PRODUCER_HTML.index("<h3>Discord Setup</h3>")

    assert suggestions_index < focus_index < pit_road_index < camera_index < race_control_index
    assert pit_road_index < interview_index < event_log_index
    assert event_log_index < audit_index < discord_index
    assert "button-row control-grid" in PRODUCER_HTML
    assert "panel full priority" in PRODUCER_HTML


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
    server.add_race_event_log(
        "Pit Road",
        "The 34 has entered pit road.",
        {
            "car_idx": 34,
            "car_number": "34",
            "driver_name": "T.J. Lee",
            "session_type": "Race",
            "session_lap": 51,
            "camera_group": "TV2",
            "replay_session_num": 2,
            "replay_session_time": 1234.5,
        },
        kind="pit",
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
    assert state["race_event_log"][0]["title"] == "Pit Road"
    assert state["race_event_log"][0]["kind"] == "pit"
    assert state["race_event_log"][0]["session_type"] == "Race"
    assert state["race_event_log"][0]["session_lap"] == 51
    assert state["race_event_log"][0]["camera_group"] == "TV2"
    assert state["race_event_log"][0]["replay_session_num"] == 2
    assert state["race_event_log"][0]["replay_session_time"] == 1234.5
    assert state["race_event_log"][1]["title"] == "Race Control"
    assert state["director_suggestions"][0]["title"] == "Closest Battle"


def test_overlay_server_can_mark_race_event_log_item_for_review():
    from production.overlay import OverlayServer

    server = OverlayServer()
    event = server.add_race_event_log(
        "Incident",
        "Possible contact in turn three.",
        {"car_number": "34", "driver_name": "T.J. Lee"},
        kind="incident",
    )

    server.update_race_event_log_item(
        event.id,
        status="needs review",
        note="Check if the 34 came down.",
        producer_name="Race Control",
    )
    state = server.current_state_dict()

    assert state["race_event_log"][0]["status"] == "needs review"
    assert "Review note: Check if the 34 came down." in state["race_event_log"][0]["message"]
    assert state["race_event_log"][0]["created_by"] == "Race Control"


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

    selected = server.set_leaderboard_style("flo")
    state = server.current_state_dict()

    assert selected == "flo"
    assert state["event"]["leaderboard_style"] == "flo"
    assert state["control_state"]["leaderboard_style"] == "flo"
