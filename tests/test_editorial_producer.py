import time

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
