from production.race_insight_director import RaceInsightDirector
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
    second = director.long_green_insight(state, current_lap=28)

    assert first is not None
    assert second is not None
    assert first.category != second.category


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

