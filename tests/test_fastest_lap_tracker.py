from production.fastest_lap_tracker import FastestLapTracker


def test_fastest_lap_tracker_announces_new_race_best():
    tracker = FastestLapTracker()
    drivers = {
        7: {"name": "Austin Peterson", "number": "77"},
        24: {"name": "Dean Marsh", "number": "24"},
    }

    first = tracker.analyze(
        [
            {"CarIdx": 7, "FastestTime": 31.245},
            {"CarIdx": 24, "FastestTime": 31.100},
        ],
        drivers,
        current_lap=3,
    )
    repeat = tracker.analyze(
        [
            {"CarIdx": 7, "FastestTime": 31.245},
            {"CarIdx": 24, "FastestTime": 31.100},
        ],
        drivers,
        current_lap=4,
    )
    improved = tracker.analyze(
        [
            {"CarIdx": 7, "FastestTime": 30.950},
            {"CarIdx": 24, "FastestTime": 31.100},
        ],
        drivers,
        current_lap=5,
    )

    assert first.car_idx == 24
    assert "Dean Marsh" in first.message
    assert "31.100" in first.message
    assert repeat is None
    assert improved.car_idx == 7
    assert "30.950" in improved.message


def test_fastest_lap_tracker_waits_until_race_has_laps():
    tracker = FastestLapTracker()

    event = tracker.analyze(
        [{"CarIdx": 7, "FastestTime": 31.245}],
        {7: {"name": "Austin Peterson", "number": "77"}},
        current_lap=1,
    )

    assert event is None
