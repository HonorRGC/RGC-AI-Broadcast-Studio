from production.overlay import OverlayEventConfig, OverlayStateBuilder


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
        kind="national_anthem",
        title="Please Rise",
        subtitle="For the National Anthem",
        duration=90,
    )

    server.update_from_telemetry(OverlayTelemetry())
    state = server.current_state_dict()

    assert state["special_presentation"]["kind"] == "national_anthem"
    assert state["special_presentation"]["title"] == "Please Rise"
