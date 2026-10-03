import time

from production.editorial_timeline import EditorialTimeline, TimelineStory


def test_stale_story_expires_before_it_can_become_ready():
    timeline = EditorialTimeline()
    timeline.submit(
        TimelineStory(
            id="old-pit-stop",
            headline="Old pit stop",
            category="pit_strategy",
            delay_seconds=5,
            expire_after=30,
            created_time=time.time() - 60,
        )
    )

    assert timeline.next_story() is None
    assert timeline.stories == {}
