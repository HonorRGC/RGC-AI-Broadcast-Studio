from production.penalty_detector import PenaltyDetector


def test_black_flag_for_pit_speeding_is_broadcast():
    detector = PenaltyDetector()
    drivers = {4: {"name": "Fast Driver", "number": "44"}}
    detector.analyze([{"CarIdx": 4, "Position": 1}], drivers)

    events = detector.analyze(
        [
            {
                "CarIdx": 4,
                "Position": 1,
                "SessionFlags": PenaltyDetector.BLACK_FLAG,
                "PenaltyReason": "Speeding on pit road",
            }
        ],
        drivers,
    )

    assert len(events) == 1
    assert events[0].event_type == "black_flag"
    assert "speeding on pit road" in events[0].message


def test_black_flag_for_jump_start_is_broadcast():
    detector = PenaltyDetector()
    drivers = {4: {"name": "Early Driver", "number": "44"}}
    detector.analyze([{"CarIdx": 4, "Position": 1}], drivers)

    events = detector.analyze(
        [
            {
                "CarIdx": 4,
                "Position": 1,
                "SessionFlags": PenaltyDetector.BLACK_FLAG,
                "PenaltyReason": "Jumped the restart",
            }
        ],
        drivers,
    )

    assert len(events) == 1
    assert "jumping the start or restart" in events[0].message


def test_generic_black_flag_is_ignored_without_reason():
    detector = PenaltyDetector()
    drivers = {4: {"name": "Quiet Driver", "number": "44"}}
    detector.analyze([{"CarIdx": 4, "Position": 1}], drivers)

    events = detector.analyze(
        [{"CarIdx": 4, "Position": 1, "SessionFlags": PenaltyDetector.BLACK_FLAG}],
        drivers,
    )

    assert events == []


def test_meatball_flag_is_broadcast():
    detector = PenaltyDetector()
    drivers = {4: {"name": "Damaged Driver", "number": "44"}}
    detector.analyze([{"CarIdx": 4, "Position": 1}], drivers)

    events = detector.analyze(
        [{"CarIdx": 4, "Position": 1, "SessionFlags": PenaltyDetector.REPAIR_FLAG}],
        drivers,
    )

    assert len(events) == 1
    assert events[0].event_type == "meatball"
    assert "required repairs" in events[0].message


def test_penalty_is_not_repeated_while_flag_stays_on():
    detector = PenaltyDetector()
    drivers = {4: {"name": "Fast Driver", "number": "44"}}
    detector.analyze([{"CarIdx": 4, "Position": 1}], drivers)
    car = {
        "CarIdx": 4,
        "Position": 1,
        "SessionFlags": PenaltyDetector.BLACK_FLAG,
        "PenaltyReason": "Speeding on pit road",
    }

    first = detector.analyze([car], drivers)
    second = detector.analyze([car], drivers)

    assert len(first) == 1
    assert second == []
