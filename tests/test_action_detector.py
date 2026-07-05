from production.action_detector import ActionDetector


def race_data(count=3):
    results = [
        {"CarIdx": index, "Position": index, "LapsComplete": 5}
        for index in range(count)
    ]
    drivers = {
        index: {"name": name, "number": str(index + 1)}
        for index, name in enumerate(["T.J. Lee", "Alex Driver", "Sam Racer"][:count])
    }
    return results, drivers


def test_detects_side_by_side_cars_and_sets_camera_target():
    results, drivers = race_data(2)
    detector = ActionDetector()

    events = detector.analyze(results, drivers, [0.5000, 0.5007], [False, False], 5)

    assert len(events) == 1
    assert events[0].event_type == "side_by_side"
    assert "T.J. Lee" in events[0].summary
    assert events[0].camera_target_car_idx in events[0].participant_car_indices


def test_three_close_cars_create_one_three_car_battle():
    results, drivers = race_data(3)
    detector = ActionDetector()

    events = detector.analyze(
        results, drivers, [0.5000, 0.5007, 0.5014], [False] * 3, 5
    )

    assert [event.event_type for event in events] == ["three_car_battle"]
    assert events[0].participant_car_indices == (0, 1, 2)


def test_new_driver_is_named_when_joining_an_existing_pair():
    results, drivers = race_data(3)
    detector = ActionDetector()
    detector.analyze(results[:2], drivers, [0.5000, 0.5007, 0.6], [False] * 3, 2)

    events = detector.analyze(
        results, drivers, [0.5000, 0.5007, 0.5014], [False] * 3, 5
    )

    assert "Sam Racer has joined" in events[0].summary
    assert events[0].camera_target_car_idx == 2


def test_uninitialized_zero_distances_do_not_create_false_action():
    results, drivers = race_data(3)

    events = ActionDetector().analyze(results, drivers, [0.0] * 3, [False] * 3, 1)

    assert events == []


def test_cars_on_different_laps_are_not_called_side_by_side():
    results, drivers = race_data(2)
    results[1]["LapsComplete"] = 4

    events = ActionDetector().analyze(
        results, drivers, [0.5000, 0.5007], [False, False], 5
    )

    assert events == []


def test_battle_can_be_called_again_after_the_cars_separate():
    results, drivers = race_data(2)
    detector = ActionDetector()

    first = detector.analyze(results, drivers, [0.5000, 0.5007], [False] * 2, 5)
    held = detector.analyze(results, drivers, [0.5000, 0.5007], [False] * 2, 5)
    detector.analyze(results, drivers, [0.5000, 0.5100], [False] * 2, 5)
    resumed = detector.analyze(results, drivers, [0.6000, 0.6007], [False] * 2, 8)

    assert len(first) == 1
    assert held == []
    assert len(resumed) == 1


def test_action_calls_are_throttled_between_laps():
    results, drivers = race_data(2)
    detector = ActionDetector()

    first = detector.analyze(results, drivers, [0.5000, 0.5007], [False] * 2, 5)
    detector.analyze(results, drivers, [0.5000, 0.5100], [False] * 2, 5)
    too_soon = detector.analyze(results, drivers, [0.6000, 0.6007], [False] * 2, 6)

    assert len(first) == 1
    assert too_soon == []
