from production.formation_detector import FormationDetector


def results(count):
    return [
        {"CarIdx": index, "Position": index, "LapsComplete": 5}
        for index in range(count)
    ]


def drivers(count):
    return {
        index: {"name": f"Driver {index + 1}", "number": str(index + 1)}
        for index in range(count)
    }


def test_detects_single_file_draft_train():
    detector = FormationDetector()

    stories = detector.analyze(
        results=results(6),
        driver_lookup=drivers(6),
        lap_dist_pct_status=[0.5000, 0.5040, 0.5080, 0.5120, 0.5160, 0.5200],
        pit_road_status=[False] * 6,
        current_lap=5,
    )

    assert stories[0].story_type == "formation_single_file"
    assert "draft train" in stories[0].summary


def test_detects_two_wide_pack_without_claiming_lane_names():
    detector = FormationDetector()

    stories = detector.analyze(
        results=results(6),
        driver_lookup=drivers(6),
        lap_dist_pct_status=[0.5000, 0.5008, 0.5060, 0.5069, 0.5120, 0.5128],
        pit_road_status=[False] * 6,
        current_lap=5,
    )

    assert stories[0].story_type == "formation_two_wide"
    assert "doubled up" in stories[0].summary
    assert "inside" not in stories[0].summary.lower()
    assert "outside" not in stories[0].summary.lower()


def test_detects_three_wide_pressure():
    detector = FormationDetector()

    stories = detector.analyze(
        results=results(6),
        driver_lookup=drivers(6),
        lap_dist_pct_status=[0.5000, 0.5005, 0.5010, 0.5060, 0.5100, 0.5140],
        pit_road_status=[False] * 6,
        current_lap=5,
    )

    assert stories[0].story_type == "formation_three_wide"
    assert "three-wide pressure" in stories[0].summary
    assert stories[0].participant_car_indices == (0, 1, 2)


def test_formation_detector_cooldown_prevents_repeating_same_call_too_soon():
    detector = FormationDetector()
    payload = dict(
        results=results(6),
        driver_lookup=drivers(6),
        lap_dist_pct_status=[0.5000, 0.5040, 0.5080, 0.5120, 0.5160, 0.5200],
        pit_road_status=[False] * 6,
    )

    assert detector.analyze(current_lap=5, **payload)
    assert detector.analyze(current_lap=6, **payload) == []
    assert detector.analyze(current_lap=10, **payload)
