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


def test_pack_wreck_needs_multiple_cars():
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
