import time
from dataclasses import dataclass, field
from enum import Enum
from typing import Dict, List, Optional


class StoryLifecycle(Enum):
    NEW = "NEW"
    ACTIVE = "ACTIVE"
    FOLLOW_UP = "FOLLOW_UP"
    BACKGROUND = "BACKGROUND"
    COMPLETE = "COMPLETE"


@dataclass
class ManagedStory:
    story_id: str
    story_type: str
    driver_name: str
    car_number: str
    car_idx: int

    headline: str
    summary: str
    importance: int

    lifecycle: StoryLifecycle = StoryLifecycle.NEW
    first_seen_lap: int = 0
    last_updated_lap: int = 0
    last_discussed_lap: int = 0

    times_seen: int = 1
    times_discussed: int = 0

    created_at: float = field(default_factory=time.time)
    updated_at: float = field(default_factory=time.time)

    speaker_preference: str = "lead"


class StoryManager:
    """
    Tracks race stories over time.

    StoryEngine discovers stories.
    StoryManager remembers them.
    EditorialProducer decides when to air them.
    """

    def __init__(self):
        self.stories: Dict[str, ManagedStory] = {}
        self.story_expire_laps = 30

    def update(self, race_stories, current_lap=0) -> List[ManagedStory]:
        updated_stories = []

        for story in race_stories or []:
            managed_story = self.add_or_update_story(story, current_lap)
            updated_stories.append(managed_story)

        self.expire_old_stories(current_lap)

        return updated_stories

    def add_or_update_story(self, race_story, current_lap):
        story_id = self.build_story_id(race_story)

        if story_id not in self.stories:
            self.stories[story_id] = ManagedStory(
                story_id=story_id,
                story_type=race_story.story_type,
                driver_name=race_story.driver_name,
                car_number=race_story.car_number,
                car_idx=race_story.car_idx,
                headline=race_story.headline,
                summary=race_story.summary,
                importance=race_story.importance,
                lifecycle=StoryLifecycle.NEW,
                first_seen_lap=current_lap,
                last_updated_lap=current_lap,
                speaker_preference=self.choose_speaker(race_story),
            )
        else:
            managed = self.stories[story_id]
            managed.headline = race_story.headline
            managed.summary = race_story.summary
            managed.importance = max(managed.importance, race_story.importance)
            managed.last_updated_lap = current_lap
            managed.updated_at = time.time()
            managed.times_seen += 1

            if managed.lifecycle == StoryLifecycle.NEW:
                managed.lifecycle = StoryLifecycle.ACTIVE
            elif managed.times_discussed > 0:
                managed.lifecycle = StoryLifecycle.FOLLOW_UP

        return self.stories[story_id]

    def build_story_id(self, race_story):
        return f"{race_story.story_type}:{race_story.car_idx}"

    def choose_speaker(self, race_story):
        if race_story.story_type in [
            "biggest_mover",
            "top_five_charge",
            "momentum",
            "fading_driver",
        ]:
            return "jeff"

        return "lead"

    def get_top_story(self) -> Optional[ManagedStory]:
        available = [
            story for story in self.stories.values()
            if story.lifecycle != StoryLifecycle.COMPLETE
        ]

        if not available:
            return None

        available.sort(
            key=lambda story: (
                story.importance,
                story.times_seen,
                -story.times_discussed,
            ),
            reverse=True,
        )

        return available[0]

    def mark_discussed(self, story_id, current_lap=0):
        story = self.stories.get(story_id)

        if not story:
            return

        story.times_discussed += 1
        story.last_discussed_lap = current_lap
        story.lifecycle = StoryLifecycle.FOLLOW_UP

    def get_active_stories(self):
        return [
            story for story in self.stories.values()
            if story.lifecycle in [
                StoryLifecycle.NEW,
                StoryLifecycle.ACTIVE,
                StoryLifecycle.FOLLOW_UP,
            ]
        ]

    def expire_old_stories(self, current_lap):
        for story in self.stories.values():
            if current_lap <= 0:
                continue

            laps_since_update = current_lap - story.last_updated_lap

            if laps_since_update >= self.story_expire_laps:
                story.lifecycle = StoryLifecycle.COMPLETE

    def clear(self):
        self.stories = {}