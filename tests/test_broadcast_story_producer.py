from types import SimpleNamespace

from production.broadcast_story_producer import BroadcastStoryProducer
from production.editorial_producer import EditorialItem


def test_story_producer_adds_broadcast_angle_and_notes_for_mover():
    producer = BroadcastStoryProducer()
    item = EditorialItem(
        story_type="biggest_mover",
        headline="Big mover",
        summary="The number 24 has gained eight positions.",
        driver_name="Dean Marsh",
        car_number="24",
    )

    producer.frame(
        item,
        race_state=SimpleNamespace(
            moment=SimpleNamespace(value="LONG_GREEN_RUN"),
            green_lap_count=18,
            laps_remaining=40,
        ),
    )

    assert item.broadcast_angle == "quiet charge through traffic"
    assert item.summary == "The number 24 has gained eight positions."
    assert any("long green-flag run" in note for note in item.producer_notes)
    assert any("without saying the label out loud" in note for note in item.producer_notes)
    assert any("not make this only a position-gain read" in note for note in item.producer_notes)


def test_story_producer_discourages_repeating_start_position_for_same_driver():
    producer = BroadcastStoryProducer()
    first = EditorialItem(
        story_type="biggest_mover",
        headline="First mover story",
        summary="First summary.",
        driver_name="Dean Marsh",
        car_number="24",
    )
    second = EditorialItem(
        story_type="top_five_charge",
        headline="Second mover story",
        summary="Second summary.",
        driver_name="Dean Marsh",
        car_number="24",
    )

    producer.frame(first)
    producer.frame(second)

    assert any("Avoid repeating where this driver started" in note for note in second.producer_notes)
