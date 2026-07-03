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
