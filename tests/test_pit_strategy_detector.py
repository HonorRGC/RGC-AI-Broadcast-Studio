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


def test_green_flag_pit_stop_after_start_remains_strategy_story():
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
    events = detector.analyze(
        results=results,
        driver_lookup=drivers,
        pit_road_status=[True],
        current_lap=11,
        under_caution=False,
    )

    assert len(events) == 1
    assert events[0].event_type == "PIT_STOP"
    assert "under green" in events[0].message


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
