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


def test_non_draft_oval_single_file_avoids_draft_train_language():
    detector = FormationDetector()

    stories = detector.analyze(
        results=results(6),
        driver_lookup=drivers(6),
        lap_dist_pct_status=[0.5000, 0.5040, 0.5080, 0.5120, 0.5160, 0.5200],
        pit_road_status=[False] * 6,
        current_lap=5,
        track_info={"track_name": "Nashville Superspeedway", "track_type": "oval"},
    )

    assert stories[0].story_type == "formation_single_file"
    assert "single-file rhythm" in stories[0].summary
    assert "draft train" not in stories[0].summary.lower()


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


def test_non_draft_oval_two_wide_avoids_big_draft_run_language():
    detector = FormationDetector()

    stories = detector.analyze(
        results=results(6),
        driver_lookup=drivers(6),
        lap_dist_pct_status=[0.5000, 0.5008, 0.5060, 0.5069, 0.5120, 0.5128],
        pit_road_status=[False] * 6,
        current_lap=5,
        track_info={"track_name": "Pocono Raceway", "track_type": "oval"},
    )

    assert stories[0].story_type == "formation_two_wide"
    assert "doubled up" in stories[0].summary
    assert "draft can start" not in stories[0].summary.lower()


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


def test_detects_multiple_draft_packs_with_gap():
    detector = FormationDetector()
    race_results = results(8)
    race_results[3]["Time"] = 4.2

    stories = detector.analyze(
        results=race_results,
        driver_lookup=drivers(8),
        lap_dist_pct_status=[
            0.5000,
            0.5060,
            0.5120,
            0.5900,
            0.5960,
            0.6020,
            0.7200,
            0.7260,
        ],
        pit_road_status=[False] * 8,
        current_lap=12,
        track_info={"track_name": "Daytona International Speedway", "track_type": "oval"},
    )

    assert stories[0].story_type == "formation_multiple_packs"
    assert "lead pack has 3 cars" in stories[0].summary
    assert "second pack starts around 4th" in stories[0].summary
    assert "4.2 seconds" in stories[0].summary
    assert stories[0].primary_car_idx == 3


def test_multiple_pack_story_is_limited_to_true_draft_tracks():
    detector = FormationDetector()

    stories = detector.analyze(
        results=results(8),
        driver_lookup=drivers(8),
        lap_dist_pct_status=[
            0.5000,
            0.5060,
            0.5120,
            0.5900,
            0.5960,
            0.6020,
            0.7200,
            0.7260,
        ],
        pit_road_status=[False] * 8,
        current_lap=12,
        track_info={"track_name": "Pocono Raceway", "track_type": "oval"},
    )

    assert stories == []


def test_multiple_pack_story_has_longer_cooldown():
    detector = FormationDetector()
    payload = dict(
        results=results(8),
        driver_lookup=drivers(8),
        lap_dist_pct_status=[
            0.5000,
            0.5060,
            0.5120,
            0.5900,
            0.5960,
            0.6020,
            0.7200,
            0.7260,
        ],
        pit_road_status=[False] * 8,
        track_info={"track_name": "Talladega Superspeedway", "track_type": "oval"},
    )

    assert detector.analyze(current_lap=12, **payload)
    assert detector.analyze(current_lap=16, **payload) == []
    assert detector.analyze(current_lap=20, **payload)


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
