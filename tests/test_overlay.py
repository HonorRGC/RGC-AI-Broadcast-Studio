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
        return 12

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
