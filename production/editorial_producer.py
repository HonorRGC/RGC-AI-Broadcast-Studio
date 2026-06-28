import time
from dataclasses import dataclass, field
from typing import List, Optional


@dataclass
class EditorialStory:
    story_type: str
    headline: str
    summary: str
    priority: int
    source: str = "unknown"
    driver_name: str = ""
    car_number: str = ""
    created_at: float = field(default_factory=time.time)
    last_updated_at: float = field(default_factory=time.time)
    aired: bool = False


class EditorialProducer:
    """
    EditorialProducer decides which story deserves airtime.

    It does not generate commentary.
    It does not speak.
    It does not control voices.

    It only answers:
    What should the broadcast care about right now?
    """

    def __init__(self):
        self.active_stories: List[EditorialStory] = []
        self.max_active_stories = 5
        self.story_lifetime_seconds = 45

    def submit_story(
        self,
        story_type,
        headline,
        summary,
        priority,
        source="unknown",
        driver_name="",
        car_number="",
    ):
        story = EditorialStory(
            story_type=story_type,
            headline=headline,
            summary=summary,
            priority=priority,
            source=source,
            driver_name=driver_name,
            car_number=car_number,
        )

        self.active_stories.append(story)
        self.cleanup_stories()
        self.active_stories.sort(key=lambda item: item.priority, reverse=True)

        if len(self.active_stories) > self.max_active_stories:
            self.active_stories = self.active_stories[:self.max_active_stories]

        return story

    def submit_race_story(self, race_story):
        if race_story is None:
            return None

        return self.submit_story(
            story_type=getattr(race_story, "story_type", "race_story"),
            headline=getattr(race_story, "headline", ""),
            summary=getattr(race_story, "summary", ""),
            priority=getattr(race_story, "priority", 5),
            source="story_detector",
            driver_name=getattr(race_story, "driver_name", ""),
            car_number=getattr(race_story, "car_number", ""),
        )

    def submit_pit_event(self, pit_event):
        if pit_event is None:
            return None

        priority = getattr(pit_event, "importance", 8)

        if getattr(pit_event, "under_caution", False):
            story_type = "yellow_flag_pit_strategy"
            priority = max(priority, 8)
        else:
            story_type = "green_flag_pit_strategy"
            priority = max(priority, 9)

        return self.submit_story(
            story_type=story_type,
            headline="Pit strategy is starting to develop.",
            summary=getattr(pit_event, "message", ""),
            priority=priority,
            source="pit_strategy_detector",
            driver_name=getattr(pit_event, "driver_name", ""),
            car_number=getattr(pit_event, "car_number", ""),
        )

    def choose_story(self) -> Optional[EditorialStory]:
        self.cleanup_stories()

        available = [
            story for story in self.active_stories
            if not story.aired
        ]

        if not available:
            return None

        available.sort(key=lambda item: item.priority, reverse=True)
        story = available[0]
        story.aired = True

        return story

    def peek_top_story(self) -> Optional[EditorialStory]:
        self.cleanup_stories()

        if not self.active_stories:
            return None

        self.active_stories.sort(key=lambda item: item.priority, reverse=True)
        return self.active_stories[0]

    def cleanup_stories(self):
        now = time.time()

        self.active_stories = [
            story for story in self.active_stories
            if now - story.last_updated_at <= self.story_lifetime_seconds
        ]

    def clear(self):
        self.active_stories = []