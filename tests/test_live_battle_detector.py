from production.live_battle_detector import LiveBattleDetector


def results(count):
    return [
        {"CarIdx": index, "Position": index, "LapsComplete": 12}
        for index in range(count)
    ]


def drivers(count):
    return {
        index: {"name": f"Driver {index + 1}", "number": str(index + 1)}
        for index in range(count)
    }


def test_detects_live_side_by_side_without_declaring_pass():
    detector = LiveBattleDetector()
    payload = dict(
        results=results(4),
        driver_lookup=drivers(4),
        lap_dist_pct_status=[0.5000, 0.5012, 0.5200, 0.5400],
        pit_road_status=[False] * 4,
        current_lap=12,
        total_laps=50,
        green_lap_count=4,
    )

    first = detector.analyze(**payload)
    stories = detector.analyze(**payload)

    assert first == []
    assert stories[0].story_type == "live_side_by_side"
    assert "completed pass" not in stories[0].summary.lower()
    assert any(
        phrase in stories[0].summary.lower()
        for phrase in ("not settled", "good race", "picture can carry", "deserves a look")
    )
    assert stories[0].participant_car_indices == (0, 1)


def test_detects_live_three_wide_before_two_wide():
    detector = LiveBattleDetector()
    payload = dict(
        results=results(5),
        driver_lookup=drivers(5),
        lap_dist_pct_status=[0.5000, 0.5008, 0.5015, 0.5300, 0.5600],
        pit_road_status=[False] * 5,
        current_lap=20,
        total_laps=60,
        green_lap_count=8,
    )

    first = detector.analyze(**payload)
    stories = detector.analyze(**payload)

    assert first == []
    assert stories[0].story_type == "live_three_wide"
    assert stories[0].importance >= 9
    assert stories[0].participant_car_indices == (0, 1, 2)


def test_confident_clear_requires_three_consecutive_ticks():
    detector = LiveBattleDetector()
    payload = dict(
        results=results(3),
        driver_lookup=drivers(3),
        lap_dist_pct_status=[0.5000, 0.5060, 0.5300],
        pit_road_status=[False] * 3,
        current_lap=18,
        total_laps=50,
        green_lap_count=6,
    )

    first = detector.analyze(**payload)
    second = detector.analyze(**payload)
    third = detector.analyze(**payload)

    assert not any(story.story_type == "live_pressure_battle" for story in first)
    assert not any(story.story_type == "live_pressure_battle" for story in second)
    clear_story = next(story for story in third if story.story_type == "live_pressure_battle")
    assert any(
        phrase in clear_story.summary.lower()
        for phrase in ("pressuring", "battle", "company", "worth watching")
    )
    assert "worked past" not in clear_story.summary
    assert "pass looks complete" not in clear_story.summary
    assert "appears to have cleared" not in clear_story.summary


def test_detector_stays_quiet_under_caution_or_pit_road():
    detector = LiveBattleDetector()

    caution_stories = detector.analyze(
        results=results(3),
        driver_lookup=drivers(3),
        lap_dist_pct_status=[0.5000, 0.5008, 0.5015],
        pit_road_status=[False] * 3,
        current_lap=20,
        total_laps=60,
        green_lap_count=0,
    )
    pit_stories = detector.analyze(
        results=results(3),
        driver_lookup=drivers(3),
        lap_dist_pct_status=[0.5000, 0.5008, 0.5015],
        pit_road_status=[False, True, False],
        current_lap=20,
        total_laps=60,
        green_lap_count=5,
    )

    assert caution_stories == []
    assert not any(1 in story.participant_car_indices for story in pit_stories)
