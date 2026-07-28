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


def test_story_producer_adds_draft_track_restraint_notes():
    producer = BroadcastStoryProducer()
    item = EditorialItem(
        story_type="biggest_mover",
        headline="Driver moving forward",
        summary="The number 24 has gained six positions.",
        driver_name="Dean Marsh",
        car_number="24",
    )

    producer.frame(
        item,
        race_knowledge={
            "track_profile": {
                "style": "pack_draft",
                "label": "pack drafting track",
                "notes": "Pack momentum can matter here.",
            }
        },
    )

    assert any("Use draft/pack/lane language only" in note for note in item.producer_notes)
    assert any("normal driver updates" in note for note in item.producer_notes)


def test_story_producer_prefers_league_track_history_on_draft_tracks():
    producer = BroadcastStoryProducer()
    item = EditorialItem(
        story_type="biggest_mover",
        headline="Driver moving forward",
        summary="The number 34 has gained five positions.",
        driver_name="T.J. Lee",
        car_number="34",
    )

    producer.frame(
        item,
        race_knowledge={
            "track_profile": {
                "style": "pack_draft",
                "label": "pack drafting track",
                "notes": "Pack momentum can matter here.",
            },
            "league_driver_context": [
                (
                    "T.J. Lee in the number 34 stats: last race finish: 1st; "
                    "track starts: 6, track wins: 2, best track finish: 1st"
                )
            ],
        },
    )

    assert any("Verified league stats are available" in note for note in item.producer_notes)
    assert any("track-history" in note for note in item.producer_notes)
    assert any("generic draft-track reference" in note for note in item.producer_notes)
