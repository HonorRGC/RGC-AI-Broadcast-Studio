from production.league_manager import (
    LeagueProfile,
    PointsAdjustment,
    RaceResult,
    RaceResultEntry,
    ScheduleEvent,
    ScoringRule,
    ScoringSystem,
    active_iracing_league_snapshot,
    calculate_standings,
    default_scoring_system,
    load_league_profile,
    load_schedule,
    load_scoring_system,
    save_league_profile,
    save_schedule,
    save_scoring_system,
    score_race_result,
)


class FakeIRacing:
    def __getitem__(self, key):
        return {
            "WeekendInfo": {
                "LeagueID": 1234,
                "LeagueName": "RGC Test League",
                "SeasonName": "Season One",
                "TrackDisplayName": "Michigan International Speedway",
                "TrackConfigName": "Oval",
            },
            "SessionInfo": {"Sessions": [{"SessionName": "Race", "SessionLaps": "80"}]},
        }[key]


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


def test_league_profile_and_schedule_round_trip(tmp_path):
    profile_path = tmp_path / "league.json"
    schedule_path = tmp_path / "schedule.json"
    profile = LeagueProfile("Test League", "TL", "Season One", 1234)
    events = [ScheduleEvent(2, "10-02-2026", "Texas", "Oval", 100), ScheduleEvent(1, "09-25-2026", "Daytona", "Oval", 80)]

    save_league_profile(profile_path, profile)
    save_schedule(schedule_path, events)

    assert load_league_profile(profile_path) == profile
    assert [event.round_number for event in load_schedule(schedule_path)] == [1, 2]


def test_timed_road_race_schedule_supports_session_times():
    event = ScheduleEvent(
        round_number=3,
        event_date="10-09-2026",
        event_name="Road America 60",
        track_name="Road America",
        configuration="Full Course",
        car_type="GT3",
        duration_minutes=60,
        practice_time="6:00 PM",
        qualifying_time="7:00 PM",
        race_time="7:15 PM",
    )

    event.validate()


def test_active_iracing_snapshot_reads_league_and_race_details():
    snapshot = active_iracing_league_snapshot(FakeIRacing())

    assert snapshot == {
        "league_id": 1234,
        "league_name": "RGC Test League",
        "season_name": "Season One",
        "track_name": "Michigan International Speedway",
        "configuration": "Oval",
        "laps": 80,
    }


def test_race_results_score_bonuses_and_build_standings():
    scoring = ScoringSystem(
        name="League",
        finish_points={1: 40, 2: 35},
        bonus_rules=[ScoringRule("Pole", 1), ScoringRule("Fastest Lap", 1), ScoringRule("Led a Lap", 1), ScoringRule("Most Laps Led", 1), ScoringRule("Incident Free", 1)],
    )
    first = RaceResult(1, "Opener", "Daytona", [
        RaceResultEntry(1, "Alex Driver", "7", 2, 80, 50, 30.1, 0),
        RaceResultEntry(2, "Sam Racer", "12", 1, 80, 30, 30.2, 2),
    ])
    second = RaceResult(2, "Round Two", "Texas", [
        RaceResultEntry(1, "Sam Racer", "12", 2, 100, 60, 29.5, 0),
        RaceResultEntry(2, "Alex Driver", "7", 1, 100, 40, 29.7, 1),
    ])

    standings = calculate_standings([score_race_result(first, scoring), score_race_result(second, scoring)])

    assert len(standings) == 2
    assert standings[0]["starts"] == 2
    assert standings[0]["wins"] == 1
    assert standings[0]["top_fives"] == 2
    assert standings[0]["average_finish"] == 1.5


def test_scored_result_preserves_breakdown_and_manual_adjustment():
    scoring = ScoringSystem(
        name="League",
        finish_points={1: 40},
        bonus_rules=[ScoringRule("Led a Lap", 2)],
    )
    result = RaceResult(1, "Opener", "Daytona", [
        RaceResultEntry(
            1,
            "Winner",
            "7",
            laps_led=10,
            manual_adjustment=-3,
            adjustment_reason="Post-race review",
        ),
    ])

    score_race_result(result, scoring)

    entry = result.entries[0]
    assert entry.position_points == 40
    assert entry.bonus_points == 2
    assert entry.penalty_points == 0
    assert entry.manual_adjustment == -3
    assert entry.points == 39
    active_iracing_league_snapshot,
    load_league_profile,
    load_schedule,
    save_league_profile,
    save_schedule,
