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


def test_live_telemetry_exposes_camera_groups_and_switches_by_car_number():
    class FakeIR(dict):
        def __init__(self):
            super().__init__(
                CameraInfo={
                    "Groups": [{"GroupNum": 4, "GroupName": "TV1"}]
                }
            )
            self.commands = []

        def cam_switch_num(self, car_number, group_number, camera_number):
            self.commands.append((car_number, group_number, camera_number))
            return 1

    telemetry = IRacingTelemetry.__new__(IRacingTelemetry)
    telemetry.ir = FakeIR()

    assert telemetry.get_camera_groups()[0]["GroupName"] == "TV1"
    assert telemetry.switch_camera_to_car("14", 4) is True
    assert telemetry.ir.commands == [("14", 4, 0)]


def test_live_telemetry_detects_replay_delay_and_returns_to_live_edge():
    class FakeIR(dict):
        def __init__(self):
            super().__init__(ReplayFrameNum=1000, ReplayFrameNumEnd=1600)
            self.replay_commands = []

        def replay_search(self, mode):
            self.replay_commands.append(("search", mode))
            return 1

        def replay_set_play_speed(self, speed):
            self.replay_commands.append(("speed", speed))
            return 1

        def replay_search_session_time(self, session_num, session_time_ms):
            self.replay_commands.append(
                ("session_time", session_num, session_time_ms)
            )
            return 1

    telemetry = IRacingTelemetry.__new__(IRacingTelemetry)
    telemetry.ir = FakeIR()

    assert telemetry.is_replay_at_live_edge() is False
    assert telemetry.return_to_live() is True
    assert telemetry.ir.replay_commands[-1] == ("speed", 1)
    assert telemetry.seek_replay_session_time(2, 45.5) is True
    assert ("session_time", 2, 45500) in telemetry.ir.replay_commands


def test_live_results_include_the_player_incident_total():
    telemetry = IRacingTelemetry.__new__(IRacingTelemetry)
    telemetry.ir = {
        "SessionNum": 1,
        "PlayerCarIdx": 3,
        "PlayerCarMyIncidentCount": 4,
        "SessionInfo": {
            "Sessions": [
                {
                    "SessionNum": 1,
                    "SessionType": "Race",
                    "ResultsPositions": [
                        {"CarIdx": 3, "Position": 1},
                        {"CarIdx": 7, "Position": 2},
                    ],
                }
            ]
        },
    }

    results = telemetry.get_results()

    assert results[0]["Incidents"] == 4
    assert "Incidents" not in results[1]
