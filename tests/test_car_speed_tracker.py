from production.car_speed_tracker import (
    CarSpeedTracker,
    parse_track_length_miles,
    speed_value_to_mph,
)


def test_parse_track_length_miles_accepts_miles_and_kilometers():
    assert parse_track_length_miles("1.50 mi") == 1.5
    assert round(parse_track_length_miles("2.414 km"), 2) == 1.5


def test_speed_value_to_mph_converts_meters_per_second():
    assert round(speed_value_to_mph(78.2)) == 175
    assert round(speed_value_to_mph(181.5)) == 182


def test_car_speed_tracker_estimates_speed_from_lap_distance():
    tracker = CarSpeedTracker()
    tracker.update(
        session_time=10.0,
        lap_dist_pct_by_car_idx=[0.10],
        results=[{"CarIdx": 0, "LapsComplete": 5}],
        track_length_miles=1.5,
    )

    speeds = tracker.update(
        session_time=11.0,
        lap_dist_pct_by_car_idx=[0.13],
        results=[{"CarIdx": 0, "LapsComplete": 5}],
        track_length_miles=1.5,
    )

    assert round(speeds[0]) == 162


def test_car_speed_tracker_handles_lap_wrap():
    tracker = CarSpeedTracker()
    tracker.update(
        session_time=20.0,
        lap_dist_pct_by_car_idx=[0.99],
        results=[{"CarIdx": 0, "LapsComplete": 5}],
        track_length_miles=2.0,
    )

    speeds = tracker.update(
        session_time=21.0,
        lap_dist_pct_by_car_idx=[0.02],
        results=[{"CarIdx": 0, "LapsComplete": 6}],
        track_length_miles=2.0,
    )

    assert round(speeds[0]) == 216
