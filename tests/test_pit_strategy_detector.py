from production.pit_strategy_detector import PitStrategyDetector


def test_car_on_pit_road_at_start_is_reported_as_pit_road_start():
    detector = PitStrategyDetector()
    results = [{"CarIdx": 0, "Position": 12, "LapsComplete": 0}]
    drivers = {0: {"name": "Driver One", "number": "11"}}

    events = detector.analyze(
        results=results,
        driver_lookup=drivers,
        pit_road_status=[True],
        current_lap=0,
        under_caution=False,
    )

    assert len(events) == 1
    assert events[0].event_type == "PIT_ROAD_START"
    assert "starting this race from pit road" in events[0].message
    assert "penalty" in events[0].message


def test_pit_road_starter_does_not_repeat_as_green_strategy_stop():
    detector = PitStrategyDetector()
    results = [{"CarIdx": 0, "Position": 12, "LapsComplete": 0}]
    drivers = {0: {"name": "Driver One", "number": "11"}}

    detector.analyze(
        results=results,
        driver_lookup=drivers,
        pit_road_status=[True],
        current_lap=0,
        under_caution=False,
    )
    repeated = detector.analyze(
        results=results,
        driver_lookup=drivers,
        pit_road_status=[True],
        current_lap=1,
        under_caution=False,
    )

    assert repeated == []


def test_green_flag_pit_stop_waits_until_stop_is_complete():
    detector = PitStrategyDetector()
    results = [{"CarIdx": 0, "Position": 5, "LapsComplete": 10}]
    drivers = {0: {"name": "Driver One", "number": "11"}}

    detector.analyze(
        results=results,
        driver_lookup=drivers,
        pit_road_status=[False],
        current_lap=10,
        under_caution=False,
    )
    entry_events = detector.analyze(
        results=results,
        driver_lookup=drivers,
        pit_road_status=[True],
        current_lap=11,
        under_caution=False,
    )

    assert len(entry_events) == 1
    assert entry_events[0].event_type == "PIT_STOP"
    assert "pit road under green" in entry_events[0].message.lower()

    events = detector.analyze(
        results=results,
        driver_lookup=drivers,
        pit_road_status=[False],
        current_lap=11,
        under_caution=False,
    )

    assert len(events) == 1
    assert events[0].event_type == "PIT_STOP_COMPLETE"
    assert "cycles off pit road" in events[0].message


def test_pit_detector_remembers_position_when_car_enters_pit_road():
    detector = PitStrategyDetector()
    drivers = {0: {"name": "Driver One", "number": "11"}}

    detector.analyze(
        results=[{"CarIdx": 0, "Position": 5, "LapsComplete": 10}],
        driver_lookup=drivers,
        pit_road_status=[False],
        current_lap=10,
        under_caution=False,
    )
    detector.analyze(
        results=[{"CarIdx": 0, "Position": 4, "LapsComplete": 11}],
        driver_lookup=drivers,
        pit_road_status=[True],
        current_lap=11,
        under_caution=False,
    )

    assert detector.driver_states[0].pit_entry_position == 4


def test_pit_detector_tracks_pit_lane_and_estimated_service_time():
    detector = PitStrategyDetector()
    drivers = {0: {"name": "Driver One", "number": "11"}}

    detector.analyze(
        results=[{"CarIdx": 0, "Position": 5, "LapsComplete": 10}],
        driver_lookup=drivers,
        pit_road_status=[False],
        current_lap=10,
        under_caution=False,
        session_time=100.0,
        lap_dist_pct=[0.1000],
    )
    detector.analyze(
        results=[{"CarIdx": 0, "Position": 4, "LapsComplete": 11}],
        driver_lookup=drivers,
        pit_road_status=[True],
        current_lap=11,
        under_caution=False,
        session_time=110.0,
        lap_dist_pct=[0.2000],
    )
    detector.analyze(
        results=[{"CarIdx": 0, "Position": 4, "LapsComplete": 11}],
        driver_lookup=drivers,
        pit_road_status=[True],
        current_lap=11,
        under_caution=False,
        session_time=115.0,
        lap_dist_pct=[0.20002],
    )
    detector.analyze(
        results=[{"CarIdx": 0, "Position": 4, "LapsComplete": 11}],
        driver_lookup=drivers,
        pit_road_status=[False],
        current_lap=11,
        under_caution=False,
        session_time=132.0,
        lap_dist_pct=[0.2500],
    )

    state = detector.driver_states[0]
    assert state.last_pit_lane_seconds == 22.0
    assert state.last_pit_stop_seconds == 5.0


def test_pit_detector_reports_extended_stop_as_likely_damage_repair():
    detector = PitStrategyDetector()
    detector.report_cooldown_seconds = 0
    drivers = {0: {"name": "Driver One", "number": "11"}}

    detector.analyze(
        results=[{"CarIdx": 0, "Position": 5, "LapsComplete": 20}],
        driver_lookup=drivers,
        pit_road_status=[False],
        current_lap=20,
        under_caution=False,
        session_time=100.0,
        lap_dist_pct=[0.1000],
    )
    detector.analyze(
        results=[{"CarIdx": 0, "Position": 5, "LapsComplete": 21}],
        driver_lookup=drivers,
        pit_road_status=[True],
        current_lap=21,
        under_caution=False,
        session_time=110.0,
        lap_dist_pct=[0.2000],
    )
    detector.analyze(
        results=[{"CarIdx": 0, "Position": 5, "LapsComplete": 21}],
        driver_lookup=drivers,
        pit_road_status=[True],
        current_lap=21,
        under_caution=False,
        session_time=140.0,
        lap_dist_pct=[0.20001],
    )
    events = detector.analyze(
        results=[{"CarIdx": 0, "Position": 5, "LapsComplete": 21}],
        driver_lookup=drivers,
        pit_road_status=[False],
        current_lap=21,
        under_caution=False,
        session_time=150.0,
        lap_dist_pct=[0.2500],
    )

    completed = [event for event in events if event.event_type == "PIT_STOP_COMPLETE"]
    assert completed
    assert "extended stop" in completed[0].message
    assert "damage repair" in completed[0].message
    assert "30 seconds stationary" in completed[0].message


def test_pit_detector_reports_quick_stop_as_track_position_move():
    detector = PitStrategyDetector()
    detector.report_cooldown_seconds = 0
    drivers = {0: {"name": "Driver One", "number": "11"}}

    detector.analyze(
        results=[{"CarIdx": 0, "Position": 5, "LapsComplete": 20}],
        driver_lookup=drivers,
        pit_road_status=[False],
        current_lap=20,
        under_caution=False,
        session_time=100.0,
        lap_dist_pct=[0.1000],
    )
    detector.analyze(
        results=[{"CarIdx": 0, "Position": 5, "LapsComplete": 21}],
        driver_lookup=drivers,
        pit_road_status=[True],
        current_lap=21,
        under_caution=False,
        session_time=110.0,
        lap_dist_pct=[0.2000],
    )
    events = detector.analyze(
        results=[{"CarIdx": 0, "Position": 5, "LapsComplete": 21}],
        driver_lookup=drivers,
        pit_road_status=[False],
        current_lap=21,
        under_caution=False,
        session_time=118.0,
        lap_dist_pct=[0.2500],
    )

    completed = [event for event in events if event.event_type == "PIT_STOP_COMPLETE"]
    assert completed
    assert "very quick trip" in completed[0].message
    assert "track-position move" in completed[0].message


def test_pit_detector_mentions_quick_stop_that_gains_track_position():
    detector = PitStrategyDetector()
    detector.report_cooldown_seconds = 0
    drivers = {0: {"name": "Driver One", "number": "11"}}

    detector.analyze(
        results=[{"CarIdx": 0, "Position": 10, "LapsComplete": 40}],
        driver_lookup=drivers,
        pit_road_status=[False],
        current_lap=40,
        under_caution=True,
        session_time=200.0,
        lap_dist_pct=[0.1000],
    )
    detector.analyze(
        results=[{"CarIdx": 0, "Position": 10, "LapsComplete": 41}],
        driver_lookup=drivers,
        pit_road_status=[True],
        current_lap=41,
        under_caution=True,
        session_time=210.0,
        lap_dist_pct=[0.2000],
    )
    events = detector.analyze(
        results=[{"CarIdx": 0, "Position": 6, "LapsComplete": 41}],
        driver_lookup=drivers,
        pit_road_status=[False],
        current_lap=41,
        under_caution=True,
        session_time=218.0,
        lap_dist_pct=[0.2500],
    )

    assert events[0].event_type == "PIT_STOP_COMPLETE"
    assert "two-tire" in events[0].message
    assert "gained 4 spots" in events[0].message


def test_pit_detector_can_report_multiple_completed_stops_from_same_lap():
    detector = PitStrategyDetector()
    detector.report_cooldown_seconds = 0
    drivers = {
        0: {"name": "Driver One", "number": "11"},
        1: {"name": "Driver Two", "number": "22"},
    }

    detector.analyze(
        results=[
            {"CarIdx": 0, "Position": 3, "LapsComplete": 30},
            {"CarIdx": 1, "Position": 4, "LapsComplete": 30},
        ],
        driver_lookup=drivers,
        pit_road_status=[False, False],
        current_lap=30,
        under_caution=False,
        session_time=300.0,
        lap_dist_pct=[0.1000, 0.1200],
    )
    detector.analyze(
        results=[
            {"CarIdx": 0, "Position": 3, "LapsComplete": 31},
            {"CarIdx": 1, "Position": 4, "LapsComplete": 31},
        ],
        driver_lookup=drivers,
        pit_road_status=[True, True],
        current_lap=31,
        under_caution=False,
        session_time=310.0,
        lap_dist_pct=[0.2000, 0.2200],
    )
    events = detector.analyze(
        results=[
            {"CarIdx": 0, "Position": 7, "LapsComplete": 31},
            {"CarIdx": 1, "Position": 8, "LapsComplete": 31},
        ],
        driver_lookup=drivers,
        pit_road_status=[False, False],
        current_lap=31,
        under_caution=False,
        session_time=332.0,
        lap_dist_pct=[0.3000, 0.3200],
    )

    assert [event.event_type for event in events] == [
        "PIT_STOP_COMPLETE",
        "PIT_STOP_COMPLETE",
    ]
    assert {event.driver_name for event in events} == {"Driver One", "Driver Two"}
