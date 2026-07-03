from broadcaster.telemetry import IRacingTelemetry


def test_live_telemetry_selects_session_by_live_session_number():
    telemetry = IRacingTelemetry.__new__(IRacingTelemetry)
    telemetry.ir = {
        "SessionNum": 2,
        "SessionInfo": {
            "Sessions": [
                {
                    "SessionNum": 0,
                    "SessionType": "Practice",
                    "SessionLaps": "unlimited",
                    "ResultsPositions": [{"CarIdx": 1, "Position": 1}],
                },
                {
                    "SessionNum": 2,
                    "SessionType": "Race",
                    "SessionLaps": 50,
                    "ResultsPositions": [{"CarIdx": 7, "Position": 1}],
                },
            ]
        },
    }

    assert telemetry.get_session_type() == "Race"
    assert telemetry.get_total_laps() == 50
    assert telemetry.get_results() == [{"CarIdx": 7, "Position": 1}]


def test_starting_grid_falls_back_to_qualifying_results():
    telemetry = IRacingTelemetry.__new__(IRacingTelemetry)
    qualifying_grid = [
        {"CarIdx": index, "Position": index} for index in range(12)
    ]
    telemetry.ir = {
        "SessionNum": 2,
        "QualifyResultsInfo": {"Results": qualifying_grid},
        "SessionInfo": {
            "Sessions": [
                {"SessionNum": 0, "SessionType": "Practice"},
                {"SessionNum": 1, "SessionType": "Qualify"},
                {"SessionNum": 2, "SessionType": "Race", "ResultsPositions": []},
            ]
        },
    }

    assert telemetry.get_starting_grid() == qualifying_grid
