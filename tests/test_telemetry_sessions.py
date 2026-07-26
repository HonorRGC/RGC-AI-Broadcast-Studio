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


def test_live_telemetry_reads_session_time_remaining_directly():
    telemetry = IRacingTelemetry.__new__(IRacingTelemetry)
    telemetry.ir = {"SessionTimeRemain": 612.4}

    assert telemetry.get_session_time_remaining() == 612.4


def test_live_telemetry_falls_back_to_session_duration_minus_elapsed_time():
    telemetry = IRacingTelemetry.__new__(IRacingTelemetry)
    telemetry.ir = {
        "SessionNum": 0,
        "SessionTime": 120.0,
        "SessionInfo": {
            "Sessions": [
                {
                    "SessionNum": 0,
                    "SessionType": "Practice",
                    "SessionTime": "900 sec",
                },
            ],
        },
    }

    assert telemetry.get_session_time_remaining() == 780.0


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

        def cam_switch_pos(self, position, group_number, camera_number):
            self.commands.append((position, group_number, camera_number))
            return 1

    telemetry = IRacingTelemetry.__new__(IRacingTelemetry)
    telemetry.ir = FakeIR()

    assert telemetry.get_camera_groups()[0]["GroupName"] == "TV1"
    assert telemetry.switch_camera_to_car("14", 4) is True
    assert telemetry.switch_camera_to_incident(4) is True
    assert telemetry.ir.commands[0] == ("14", 4, 0)
    assert telemetry.ir.commands[-1][1:] == (4, 0)


def test_live_telemetry_detects_replay_delay_and_returns_to_live_edge():
    class FakeIR(dict):
        def __init__(self):
            super().__init__(ReplayFrameNum=1000, ReplayFrameNumEnd=1600)
            self.replay_commands = []

        def replay_search(self, mode):
            self.replay_commands.append(("search", mode))
            return 1

        def replay_set_play_position(self, mode, frame_num):
            self.replay_commands.append(("position", mode, frame_num))
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
    assert telemetry.seek_previous_incident(pre_roll_frames=420) is True
    assert telemetry.ir.replay_commands[-3][0] == "search"
    assert telemetry.ir.replay_commands[-2][0] == "position"
    assert telemetry.ir.replay_commands[-2][2] == -420
    assert telemetry.seek_previous_incident_marker() is True
    assert telemetry.ir.replay_commands[-1][0] == "search"
    assert telemetry.rewind_replay_frames(300) is True
    assert telemetry.ir.replay_commands[-2][0] == "position"
    assert telemetry.ir.replay_commands[-2][2] == -300
    assert telemetry.ir.replay_commands[-1] == ("speed", 1)
    assert telemetry.set_replay_speed(-1) is True
    assert telemetry.ir.replay_commands[-1] == ("speed", -1)
    assert telemetry.set_replay_speed(0.5) is True
    assert telemetry.ir.replay_commands[-1] == ("speed", 0.5)


def test_live_telemetry_open_chat_mode_copies_command_and_opens_chat(monkeypatch):
    class FakeIR(dict):
        def __init__(self):
            super().__init__()
            self.chat_commands = []

        def chat_command(self, command):
            self.chat_commands.append(command)
            return 1

    class SenderSpy:
        def __init__(self):
            self.copied = []

        def copy_only(self, command):
            self.copied.append(command)
            return True

    import config
    import production.admin_chat_sender as admin_chat_sender

    sender = SenderSpy()
    monkeypatch.setattr(config, "RACE_ADMIN_SEND_MODE", "open_chat")
    monkeypatch.setattr(
        admin_chat_sender,
        "WindowsAdminChatSender",
        lambda: sender,
    )
    telemetry = IRacingTelemetry.__new__(IRacingTelemetry)
    telemetry.ir = FakeIR()

    assert telemetry.send_admin_chat_command("!yellow") == "chat_opened"
    assert sender.copied == ["!yellow"]
    assert telemetry.ir.chat_commands


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


def test_live_results_include_per_car_incident_counts_when_available():
    telemetry = IRacingTelemetry.__new__(IRacingTelemetry)
    telemetry.ir = {
        "SessionNum": 1,
        "PlayerCarIdx": 99,
        "CarIdxIncidentCount": [0, 4, 0, 6],
        "SessionInfo": {
            "Sessions": [
                {
                    "SessionNum": 1,
                    "SessionType": "Race",
                    "ResultsPositions": [
                        {"CarIdx": 1, "Position": 1},
                        {"CarIdx": 3, "Position": 2},
                    ],
                }
            ]
        },
    }

    results = telemetry.get_results()

    assert results[0]["Incidents"] == 4
    assert results[1]["Incidents"] == 6


def test_live_driver_lookup_exposes_paint_matching_fields():
    telemetry = IRacingTelemetry.__new__(IRacingTelemetry)
    telemetry.ir = {
        "DriverInfo": {
            "Drivers": [
                {
                    "CarIdx": 12,
                    "UserName": "T.J. Lee2",
                    "CarNumber": "34",
                    "UserID": 90223,
                    "CarPath": "stockcars/truck",
                    "CarID": 123,
                    "CarClassID": 456,
                    "CarClassName": "GT3",
                    "CarClassShortName": "GT3",
                    "CarScreenName": "NASCAR Truck",
                    "CarScreenNameShort": "Truck",
                    "Country": "USA",
                    "CountryCode": "US",
                    "CountryName": "United States",
                    "FlairID": 223,
                    "FlairName": "United States",
                    "ClubID": 34,
                    "ClubName": "Ohio",
                    "DivisionName": "Division 2",
                    "LicString": "A 4.99",
                }
            ]
        }
    }

    driver = telemetry.get_driver_lookup()[12]

    assert driver["name"] == "T.J. Lee"
    assert driver["number"] == "34"
    assert driver["cust_id"] == 90223
    assert driver["car_path"] == "stockcars/truck"
    assert driver["car_id"] == 123
    assert driver["car_class_id"] == 456
    assert driver["car_class_name"] == "GT3"
    assert driver["car_class_short_name"] == "GT3"
    assert driver["country"] == "USA"
    assert driver["country_code"] == "US"
    assert driver["country_name"] == "United States"
    assert driver["flair_id"] == 223
    assert driver["flair_name"] == "United States"
    assert driver["club_id"] == 34
    assert driver["club_name"] == "Ohio"
    assert driver["club"] == "Ohio"
    assert driver["division_name"] == "Division 2"
    assert driver["license"] == "A 4.99"
