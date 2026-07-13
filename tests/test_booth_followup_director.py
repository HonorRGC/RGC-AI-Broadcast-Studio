from types import SimpleNamespace

from production.booth_followup_director import BoothFollowupDirector
from production.editorial_producer import EditorialItem


def test_followup_adds_short_color_after_lead_story():
    director = BoothFollowupDirector()
    item = EditorialItem(
        story_type="biggest_mover",
        headline="Driver is moving forward",
        summary="Driver has gained several spots.",
        priority=9,
        speaker="lead",
        driver_name="T.J. Lee",
        car_number="34",
    )

    follow_up = director.follow_up_for(
        item,
        race_state=SimpleNamespace(laps_remaining=40),
    )

    assert follow_up
    assert follow_up.startswith("Yeah,")
    assert "forward progress" in follow_up


def test_followup_does_not_follow_jeff_with_jeff():
    director = BoothFollowupDirector()
    item = EditorialItem(
        story_type="formation_three_wide",
        headline="Three wide",
        summary="Three cars are nearly even.",
        priority=10,
        speaker="jeff",
    )

    assert director.follow_up_for(item) is None
