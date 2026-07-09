from production.overlay import OVERLAY_HTML, OverlayEventConfig, OverlayStateBuilder


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
        )
    )

    state = builder.build_from_telemetry(OverlayTelemetry()).to_dict()

    assert state["event"]["title"] == "RGC 80 at Nashville"
    assert state["event"]["sponsor"] == "Lee Family Racing"
    assert state["event"]["series"] == "RGC Cup Series"
    assert state["track_name"] == "Nashville Superspeedway"
    assert state["lap"] == 12
    assert state["total_laps"] == 80


def test_overlay_leaderboard_sorts_and_formats_zero_based_positions():
    state = OverlayStateBuilder().build_from_telemetry(OverlayTelemetry()).to_dict()

    leaderboard = state["leaderboard"]

    assert [entry["position"] for entry in leaderboard] == [1, 2, 3]
    assert leaderboard[0]["driver_name"] == "Austin Peterson"
    assert leaderboard[0]["car_number"] == "77"
    assert leaderboard[1]["driver_name"] == "Dean Marsh"
    assert leaderboard[2]["interval"] == "+1.6"


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


def test_overlay_shows_laps_down_before_time_gap():
    class LappedTelemetry(OverlayTelemetry):
        def get_results(self):
            return [
                {"CarIdx": 3, "Position": 0, "LapsComplete": 20, "Time": 0.0},
                {"CarIdx": 7, "Position": 1, "LapsComplete": 19, "Time": 4.2},
                {"CarIdx": 9, "Position": 2, "LapsComplete": 18, "Time": 9.9},
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


def test_crank_it_up_overlay_has_visible_speaker_elements():
    assert "crank-speaker-left" in OVERLAY_HTML
    assert "crank-speaker-right" in OVERLAY_HTML
    assert ".special-presentation.crank_it_up .crank-speaker" in OVERLAY_HTML


def test_overlay_has_center_session_clock():
    assert 'id="session-center"' in OVERLAY_HTML
    assert "buildSessionCenterLine" in OVERLAY_HTML
    assert "formatClock" in OVERLAY_HTML


def test_race_sponsor_banner_is_compact():
    assert ".special-presentation.race_sponsors" in OVERLAY_HTML
    assert "height: 112px" in OVERLAY_HTML
    assert "width: min(660px, 100%)" in OVERLAY_HTML


def test_crank_it_up_overlay_uses_logo_and_racing_speaker_style():
    assert ".special-presentation.crank_it_up .ceremony-logo" in OVERLAY_HTML
    assert "repeating-linear-gradient" in OVERLAY_HTML
    assert "clip-path" in OVERLAY_HTML
