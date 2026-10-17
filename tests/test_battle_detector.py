from production.battle_detector import BattleDetector


def test_zero_gap_is_not_treated_as_a_real_battle():
    detector = BattleDetector()
    results = [
        {"CarIdx": 1, "Position": 1, "Time": 0.0},
        {"CarIdx": 2, "Position": 2, "Time": 0.0},
    ]

    assert detector.analyze(results, {}) == []


def test_positive_close_gap_can_create_a_battle():
    detector = BattleDetector()
    results = [
        {"CarIdx": 1, "Position": 1, "Time": 0.0},
        {"CarIdx": 2, "Position": 2, "Time": 0.25},
    ]

    battles = detector.analyze(results, {})

    assert len(battles) == 1
    assert battles[0].gap == 0.25
