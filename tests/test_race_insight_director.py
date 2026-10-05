from production.race_insight_director import RaceInsightDirector
from production.league_manager import ScoringRule, ScoringSystem, save_scoring_system
from production.race_state_tracker import RaceState


def test_long_green_insight_waits_for_real_long_run():
    director = RaceInsightDirector(seed=1)
    state = RaceState(
        current_lap=8,
        total_laps=80,
        laps_remaining=72,
        green_lap_count=8,
        is_green=True,
    )

    assert director.long_green_insight(state, current_lap=8) is None

    state.green_lap_count = 12
    insight = director.long_green_insight(state, current_lap=12)

    assert insight is not None
    assert insight.category.startswith("race_insight:")
    assert any(
        keyword in insight.message.lower()
        for keyword in ("tire", "fuel", "throttle", "draft")
    )


def test_long_green_insights_do_not_repeat_topics():
    director = RaceInsightDirector(seed=2)
    state = RaceState(
        current_lap=20,
        total_laps=80,
        laps_remaining=60,
        green_lap_count=20,
        is_green=True,
    )

    first = director.long_green_insight(state, current_lap=20)
    too_soon = director.long_green_insight(state, current_lap=28)
    second = director.long_green_insight(state, current_lap=36)
    third = director.long_green_insight(state, current_lap=52)

    assert first is not None
    assert too_soon is None
    assert second is not None
    assert first.category != second.category
    assert third is None


def test_non_draft_long_green_insight_does_not_use_draft_fuel_save():
    director = RaceInsightDirector(seed=10)
    director.used_topics.update(
        {"tire_wear_entry", "tire_wear_exit", "fuel_save_lift"}
    )
    state = RaceState(
        current_lap=20,
        total_laps=80,
        laps_remaining=60,
        green_lap_count=20,
        is_green=True,
    )

    insight = director.long_green_insight(
        state,
        current_lap=20,
        track_info={"track_name": "Martinsville Speedway"},
    )

    assert insight is None


def test_draft_track_long_green_insight_can_use_draft_fuel_save():
    director = RaceInsightDirector(seed=10)
    director.used_topics.update(
        {"tire_wear_entry", "tire_wear_exit", "fuel_save_lift"}
    )
    state = RaceState(
        current_lap=20,
        total_laps=80,
        laps_remaining=60,
        green_lap_count=20,
        is_green=True,
    )

    insight = director.long_green_insight(
        state,
        current_lap=20,
        track_info={"track_name": "Daytona International Speedway"},
    )

    assert insight is not None
    assert insight.category == "race_insight:fuel_save_draft"


def test_late_caution_insight_explains_short_run_sprint():
    director = RaceInsightDirector(seed=3)
    state = RaceState(
        current_lap=73,
        total_laps=80,
        laps_remaining=7,
        is_caution=True,
    )

    insight = director.caution_insight(state)

    assert insight is not None
    assert "sprint" in insight.message.lower() or "track position" in insight.message.lower()


def test_late_caution_insights_do_not_repeat_all_used_topics():
    director = RaceInsightDirector(seed=4)
    state = RaceState(
        current_lap=73,
        total_laps=80,
        laps_remaining=7,
        is_caution=True,
    )

    first = director.caution_insight(state)
    second = director.caution_insight(state)
    third = director.caution_insight(state)

    assert first is not None
    assert second is not None
    assert first.category != second.category
    assert third is None


def test_race_stat_filler_prefers_non_battle_topic_during_quiet_run():
    director = RaceInsightDirector(seed=5)
    state = RaceState(
        current_lap=12,
        total_laps=80,
        laps_remaining=68,
        green_lap_count=8,
        is_green=True,
    )
    results = [
        {"CarIdx": 1, "Position": 0, "Time": 0.0},
        {"CarIdx": 2, "Position": 1, "Time": 0.3},
        {"CarIdx": 3, "Position": 2, "Time": 2.0},
    ]
    drivers = {
        1: {"name": "Austin Peterson", "number": "77"},
        2: {"name": "Dean Marsh", "number": "24"},
        3: {"name": "Eric Hudec", "number": "14"},
    }

    insight = director.race_stat_filler(results, drivers, state, current_lap=12)

    assert insight is not None
    assert insight.category.startswith("race_stat:leader_pace")
    assert "battle" not in insight.message.lower()
    assert insight.camera_target_car_idx == 1
    assert insight.participant_car_indices == (1,)


def test_race_stat_filler_finds_biggest_mover_without_close_battle():
    director = RaceInsightDirector(seed=6)
    state = RaceState(
        current_lap=18,
        total_laps=80,
        laps_remaining=62,
        green_lap_count=12,
        is_green=True,
    )
    results = [
        {"CarIdx": 1, "Position": 0, "Time": 0.0, "StartingPosition": 1},
        {"CarIdx": 2, "Position": 1, "Time": 2.0, "StartingPosition": 8},
        {"CarIdx": 3, "Position": 2, "Time": 4.0, "StartingPosition": 3},
    ]
    drivers = {
        1: {"name": "Austin Peterson", "number": "77"},
        2: {"name": "Dean Marsh", "number": "24"},
        3: {"name": "Eric Hudec", "number": "14"},
    }

    insight = director.race_stat_filler(results, drivers, state, current_lap=18)

    assert insight is not None
    assert insight.category.startswith("race_stat:biggest_mover")
    assert "started 8th" in insight.message
    assert "2nd" in insight.message
    assert insight.camera_target_car_idx == 2


def test_race_stat_filler_uses_league_track_context_before_generic_mover():
    director = RaceInsightDirector(seed=8)
    state = RaceState(
        current_lap=18,
        total_laps=80,
        laps_remaining=62,
        green_lap_count=12,
        is_green=True,
    )
    results = [
        {"CarIdx": 1, "Position": 0, "Time": 0.0, "StartingPosition": 1},
        {"CarIdx": 2, "Position": 1, "Time": 2.0, "StartingPosition": 6},
        {"CarIdx": 3, "Position": 2, "Time": 4.0, "StartingPosition": 3},
    ]
    drivers = {
        1: {"name": "Austin Peterson", "number": "77"},
        2: {
            "name": "Dean Marsh",
            "number": "24",
            "league_stats_by_scope": [
                {
                    "stats_scope": "season",
                    "track_starts": "4",
                    "track_wins": "1",
                    "points_position": "3",
                }
            ],
            "league_profile": {
                "driving_style": "patient long-run driver",
                "location": "Lebanon, Tennessee",
            },
        },
        3: {"name": "Eric Hudec", "number": "14"},
    }

    insight = director.race_stat_filler(results, drivers, state, current_lap=18)

    assert insight is not None
    assert insight.category.startswith("race_stat:driver_context")
    assert "strong at this track" in insight.message
    assert "Dean Marsh" in insight.message
    assert insight.speaker == "jeff"
    assert insight.camera_target_car_idx == 2


def test_race_stat_filler_can_reset_championship_standings():
    director = RaceInsightDirector(seed=9)
    state = RaceState(
        current_lap=22,
        total_laps=80,
        laps_remaining=58,
        green_lap_count=14,
        is_green=True,
    )
    results = [
        {"CarIdx": 1, "Position": 0, "Time": 0.0},
        {"CarIdx": 2, "Position": 1, "Time": 2.0},
        {"CarIdx": 3, "Position": 2, "Time": 4.0},
    ]
    drivers = {
        1: {
            "name": "T.J. Lee",
            "number": "34",
            "league_stats_by_scope": [{"stats_scope": "season", "points_position": "1"}],
        },
        2: {
            "name": "Dean Marsh",
            "number": "24",
            "league_stats_by_scope": [{"stats_scope": "season", "points_position": "2"}],
        },
        3: {
            "name": "Austin Peterson",
            "number": "77",
            "league_stats_by_scope": [{"stats_scope": "season", "points_position": "3"}],
        },
    }

    insight = director.race_stat_filler(results, drivers, state, current_lap=22)

    assert insight is not None
    assert insight.category.startswith("race_stat:points_standings")
    assert "championship picture" in insight.message
    assert "T.J. Lee" in insight.message
    assert insight.camera_target_car_idx == 1

    second = director.race_stat_filler(results, drivers, state, current_lap=30)
    assert second is None or not second.category.startswith("race_stat:points_standings")


def test_championship_call_projects_live_swing_and_configured_win_bonus(tmp_path):
    scoring_path = tmp_path / "scoring.json"
    save_scoring_system(
        scoring_path,
        ScoringSystem(
            finish_points={1: 40, 2: 35, 3: 34},
            bonus_rules=[ScoringRule("Race Win", 10)],
        ),
    )
    director = RaceInsightDirector(seed=9, scoring_path=scoring_path)
    state = RaceState(
        current_lap=22, total_laps=80, laps_remaining=58,
        green_lap_count=14, is_green=True,
    )
    results = [
        {"CarIdx": 2, "Position": 0, "Time": 0.0},
        {"CarIdx": 1, "Position": 1, "Time": 1.0},
        {"CarIdx": 3, "Position": 2, "Time": 2.0},
    ]
    drivers = {
        1: {"name": "Points Leader", "number": "1", "league_stats_by_scope": [
            {"stats_scope": "season", "points_position": "1", "points": "100"}
        ]},
        2: {"name": "Title Challenger", "number": "2", "league_stats_by_scope": [
            {"stats_scope": "season", "points_position": "2", "points": "95", "points_to_next": "5"}
        ]},
        3: {"name": "Third Driver", "number": "3", "league_stats_by_scope": [
            {"stats_scope": "season", "points_position": "3", "points": "80"}
        ]},
    }

    insight = director.race_stat_filler(results, drivers, state, current_lap=22)

    assert "championship fight" in insight.message
    assert "10-point win bonus" in insight.message
    assert "unofficial" in insight.message.lower()


def test_race_stat_filler_waits_for_green_run():
    director = RaceInsightDirector(seed=7)
    state = RaceState(
        current_lap=6,
        total_laps=80,
        laps_remaining=74,
        green_lap_count=5,
        is_green=True,
    )
    results = [
        {"CarIdx": 1, "Position": 0, "Time": 0.0},
        {"CarIdx": 2, "Position": 1, "Time": 0.2},
    ]

    assert director.race_stat_filler(results, {}, state, current_lap=6) is None
