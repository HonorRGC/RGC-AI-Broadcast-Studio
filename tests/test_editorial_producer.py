import time
from types import SimpleNamespace

from production.editorial_producer import EditorialItem, EditorialProducer


def test_recent_driver_story_is_held_to_avoid_repetitive_commentary():
    producer = EditorialProducer()
    producer.recent_driver_mentions["david lin"] = time.time()
    item = EditorialItem(
        story_type="top_five_charge",
        headline="Another move forward",
        summary="David Lin is moving forward.",
        priority=8,
        driver_name="David Lin",
    )

    assert producer.can_air(item) is False


def test_urgent_lead_change_can_bypass_driver_repeat_hold():
    producer = EditorialProducer()
    producer.recent_driver_mentions["david lin"] = time.time()
    item = EditorialItem(
        story_type="lead_change",
        headline="New leader",
        summary="David Lin takes the lead.",
        priority=10,
        driver_name="David Lin",
    )

    assert producer.can_air(item) is True


def test_late_race_holds_normal_mover_stories_to_prioritize_leaders():
    producer = EditorialProducer()
    item = EditorialItem(
        story_type="top_five_charge",
        headline="Mover story",
        summary="A driver is moving forward.",
        priority=8,
        driver_name="Mover",
    )
    producer.add_item(item)
    producer.submit_to_timeline(item)
    producer.timeline.stories[producer.build_story_id(item)].created_time -= 20

    decision = producer.choose_next_item(
        race_state=SimpleNamespace(laps_remaining=3)
    )

    assert decision.decision_type.value == "HOLD"
    assert "leaders" in decision.reason


def test_late_race_allows_lead_battle_stories():
    producer = EditorialProducer()
    item = EditorialItem(
        story_type="battle_for_lead",
        headline="Lead fight",
        summary="The top two are nose to tail.",
        priority=8,
        driver_name="Leader",
    )
    producer.add_item(item)
    producer.submit_to_timeline(item)

    decision = producer.choose_next_item(
        race_state=SimpleNamespace(laps_remaining=3)
    )

    assert decision.decision_type.value == "AIR_NOW"


def test_routine_driver_story_is_held_after_airtime_limit():
    producer = EditorialProducer()
    producer.driver_normal_story_counts["tyler peacock"] = 2
    item = EditorialItem(
        story_type="momentum",
        headline="Another Tyler progress update",
        summary="Tyler Peacock is still moving forward.",
        priority=7,
        driver_name="Tyler Peacock",
    )
    producer.add_item(item)
    producer.submit_to_timeline(item)
    producer.timeline.stories[producer.build_story_id(item)].created_time -= 20

    decision = producer.choose_next_item()

    assert decision.decision_type.value == "HOLD"
    assert "airtime" in decision.reason


def test_urgent_driver_story_bypasses_airtime_limit():
    producer = EditorialProducer()
    producer.driver_normal_story_counts["tyler peacock"] = 2
    item = EditorialItem(
        story_type="lead_change",
        headline="Tyler takes the lead",
        summary="Tyler Peacock has taken the race lead.",
        priority=10,
        driver_name="Tyler Peacock",
    )
    producer.add_item(item)
    producer.submit_to_timeline(item)

    decision = producer.choose_next_item()

    assert decision.decision_type.value == "AIR_NOW"


def test_restart_settling_holds_routine_pressure_battle():
    producer = EditorialProducer()
    item = EditorialItem(
        story_type="live_pressure_battle",
        headline="Pressure for seventh",
        summary="The trailing car is close in scoring.",
        priority=8,
        participant_car_indices=(7, 8),
    )
    producer.add_item(item)
    producer.submit_to_timeline(item)

    decision = producer.choose_next_item(
        race_state=SimpleNamespace(laps_remaining=40, restart_count=1, green_lap_count=2)
    )

    assert decision.decision_type.value == "HOLD"
    assert "restart" in decision.reason.lower()


def test_restart_settling_allows_verified_side_by_side_action():
    producer = EditorialProducer()
    item = EditorialItem(
        story_type="live_side_by_side",
        headline="Side by side for seventh",
        summary="Two cars are physically alongside.",
        priority=9,
        participant_car_indices=(7, 8),
    )
    producer.add_item(item)
    producer.submit_to_timeline(item)

    decision = producer.choose_next_item(
        race_state=SimpleNamespace(laps_remaining=40, restart_count=1, green_lap_count=2)
    )

    assert decision.decision_type.value == "AIR_NOW"


def test_routine_battle_budget_spaces_calls_apart():
    producer = EditorialProducer()
    producer.last_battle_aired_at = time.time()
    item = EditorialItem(
        story_type="battle_for_top_ten",
        headline="Developing fight for ninth",
        summary="A verified close interval is developing.",
        priority=7,
        participant_car_indices=(9, 10),
    )
    producer.add_item(item)
    producer.submit_to_timeline(item)

    decision = producer.choose_next_item(
        race_state=SimpleNamespace(laps_remaining=40, restart_count=0, green_lap_count=12)
    )

    assert decision.decision_type.value == "HOLD"
    assert "cooling down" in decision.reason.lower()
