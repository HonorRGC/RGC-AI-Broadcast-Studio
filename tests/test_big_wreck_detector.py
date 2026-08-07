from production.incident_detector import IncidentDetector


def test_pack_wreck_breaks_through_soft_incident_suppression():
    detector = IncidentDetector()
    drivers = {
        index: {"name": f"Driver {index + 1}", "number": str(index + 1)}
        for index in range(5)
    }
    first_results = [
        {"CarIdx": index, "Position": index + 1, "Incidents": 0}
        for index in range(5)
    ]
    second_results = [
        {"CarIdx": 0, "Position": 8, "Incidents": 0},
        {"CarIdx": 1, "Position": 9, "Incidents": 0},
        {"CarIdx": 2, "Position": 10, "Incidents": 0},
        {"CarIdx": 3, "Position": 11, "Incidents": 0},
        {"CarIdx": 4, "Position": 5, "Incidents": 0},
    ]

    detector.analyze(
        results=first_results,
        driver_lookup=drivers,
        current_lap=12,
        lap_dist_pct_status=[0.50, 0.51, 0.52, 0.53, 0.54],
        est_time_status=[20.0, 20.2, 20.4, 20.6, 20.8],
        pit_road_status=[False] * 5,
        suppress_soft_events=True,
    )
    events = detector.analyze(
        results=second_results,
        driver_lookup=drivers,
        current_lap=12,
        lap_dist_pct_status=[0.49, 0.50, 0.51, 0.52, 0.54],
        est_time_status=[22.0, 22.2, 22.4, 22.6, 20.8],
        pit_road_status=[False] * 5,
        suppress_soft_events=True,
    )

    assert len(events) == 1
    assert events[0].trouble_type == "pack wreck"
    assert "Big trouble in the pack" in events[0].message
    assert events[0].importance == 10


def test_single_car_position_loss_is_not_called_trouble():
    detector = IncidentDetector()
    drivers = {0: {"name": "Solo Driver", "number": "7"}}

    detector.analyze(
        results=[{"CarIdx": 0, "Position": 1, "Incidents": 0}],
        driver_lookup=drivers,
        current_lap=5,
        lap_dist_pct_status=[0.50],
        est_time_status=[20.0],
        pit_road_status=[False],
        suppress_soft_events=True,
    )
    events = detector.analyze(
        results=[{"CarIdx": 0, "Position": 8, "Incidents": 0}],
        driver_lookup=drivers,
        current_lap=5,
        lap_dist_pct_status=[0.49],
        est_time_status=[24.0],
        pit_road_status=[False],
        suppress_soft_events=True,
    )

    assert events == []


def test_serious_single_car_moment_breaks_through_soft_suppression():
    detector = IncidentDetector()
    drivers = {0: {"name": "Solo Driver", "number": "7"}}

    detector.analyze(
        results=[{"CarIdx": 0, "Position": 3, "Incidents": 0}],
        driver_lookup=drivers,
        current_lap=18,
        lap_dist_pct_status=[0.70],
        est_time_status=[20.0],
        track_surface_status=[3],
        pit_road_status=[False],
        suppress_soft_events=True,
    )
    events = detector.analyze(
        results=[{"CarIdx": 0, "Position": 8, "Incidents": 0}],
        driver_lookup=drivers,
        current_lap=18,
        lap_dist_pct_status=[0.67],
        est_time_status=[24.0],
        track_surface_status=[0],
        pit_road_status=[False],
        suppress_soft_events=True,
    )

    assert len(events) == 1
    assert events[0].trouble_type == "loss of control"
    assert "Trouble for Solo Driver" in events[0].message
    assert events[0].car_idx == 0


def test_road_course_mode_calls_serious_local_trouble():
    detector = IncidentDetector()
    drivers = {0: {"name": "Road Racer", "number": "12"}}

    detector.analyze(
        results=[{"CarIdx": 0, "Position": 3, "Incidents": 0}],
        driver_lookup=drivers,
        current_lap=18,
        lap_dist_pct_status=[0.70],
        est_time_status=[20.0],
        track_surface_status=[3],
        pit_road_status=[False],
        road_course_mode=True,
    )
    events = detector.analyze(
        results=[{"CarIdx": 0, "Position": 3, "Incidents": 0}],
        driver_lookup=drivers,
        current_lap=18,
        lap_dist_pct_status=[0.69],
        est_time_status=[22.0],
        track_surface_status=[0],
        pit_road_status=[False],
        road_course_mode=True,
    )

    assert len(events) == 1
    assert events[0].trouble_type == "loss of control"
    assert "Trouble for Road Racer" in events[0].message


def test_green_flag_pit_exit_does_not_create_pack_wreck():
    detector = IncidentDetector()
    drivers = {
        index: {"name": f"Driver {index + 1}", "number": str(index + 1)}
        for index in range(5)
    }
    initial_results = [
        {"CarIdx": index, "Position": index + 1, "Incidents": 0}
        for index in range(5)
    ]
    pit_results = [
        {"CarIdx": index, "Position": index + 1, "Incidents": 0}
        for index in range(5)
    ]
    exit_results = [
        {"CarIdx": index, "Position": index + 12, "Incidents": 0}
        for index in range(5)
    ]

    detector.analyze(
        results=initial_results,
        driver_lookup=drivers,
        current_lap=30,
        lap_dist_pct_status=[0.80, 0.81, 0.82, 0.83, 0.84],
        est_time_status=[30.0, 30.2, 30.4, 30.6, 30.8],
        pit_road_status=[False] * 5,
        suppress_soft_events=True,
    )
    detector.analyze(
        results=pit_results,
        driver_lookup=drivers,
        current_lap=31,
        lap_dist_pct_status=[0.90, 0.91, 0.92, 0.93, 0.94],
        est_time_status=[35.0, 35.2, 35.4, 35.6, 35.8],
        pit_road_status=[True] * 5,
        suppress_soft_events=True,
    )
    events = detector.analyze(
        results=exit_results,
        driver_lookup=drivers,
        current_lap=32,
        lap_dist_pct_status=[0.10, 0.11, 0.12, 0.13, 0.14],
        est_time_status=[60.0, 60.2, 60.4, 60.6, 60.8],
        pit_road_status=[False] * 5,
        suppress_soft_events=True,
    )

    assert events == []
