from production.league_manager import (
    PointsAdjustment,
    ScoringRule,
    ScoringSystem,
    default_scoring_system,
    load_scoring_system,
    save_scoring_system,
)


def test_custom_scoring_calculates_bonuses_penalties_and_manual_adjustments():
    scoring = ScoringSystem(
        name="Test Points",
        finish_points={1: 50, 2: 45},
        bonus_rules=[ScoringRule("Fastest Lap", 2)],
        penalty_rules=[ScoringRule("Avoidable Contact", 7)],
    )

    result = scoring.calculate(
        2,
        bonus_names=["Fastest Lap"],
        penalty_names=["Avoidable Contact"],
        adjustments=[PointsAdjustment(3, "Admin correction"), (-1, "Late entry")],
    )

    assert result["finish_points"] == 45
    assert result["bonuses"] == [{"amount": 2.0, "reason": "Fastest Lap"}]
    assert result["penalties"] == [{"amount": -7.0, "reason": "Avoidable Contact"}]
    assert result["total"] == 42


def test_scoring_system_round_trips_to_profile_json(tmp_path):
    path = tmp_path / "league" / "test" / "scoring.json"
    scoring = default_scoring_system()

    save_scoring_system(path, scoring)
    loaded = load_scoring_system(path)

    assert loaded.to_dict() == scoring.to_dict()


def test_scoring_validation_rejects_duplicate_and_negative_rules():
    scoring = ScoringSystem(
        name="Bad",
        finish_points={1: 10},
        bonus_rules=[ScoringRule("Pole", 1), ScoringRule("pole", 2)],
        penalty_rules=[ScoringRule("Contact", -5)],
    )

    errors = scoring.validate()

    assert any("Duplicate bonus rule" in error for error in errors)
    assert any("Penalty rule points must be zero or greater" in error for error in errors)
