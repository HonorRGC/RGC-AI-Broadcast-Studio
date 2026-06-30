from dataclasses import dataclass, field
from enum import Enum
import time


class TimelineStatus(Enum):
    NEW = "NEW"
    WAITING = "WAITING"
    READY = "READY"
    AIRED = "AIRED"
    FOLLOW_UP = "FOLLOW_UP"
    EXPIRED = "EXPIRED"


@dataclass
class TimelineStory:
    id: str
    headline: str
    category: str

    priority: int = 5

    speaker: str = "lead"

    created_time: float = field(default_factory=time.time)
    last_aired: float = 0.0

    delay_seconds: float = 0.0
    follow_up_after: float = 25.0
    expire_after: float = 120.0

    air_count: int = 0

    status: TimelineStatus = TimelineStatus.NEW


class EditorialTimeline:

    def __init__(self):
        self.stories = {}

    def submit(self, story: TimelineStory):

        existing = self.stories.get(story.id)

        if existing:
            return

        self.stories[story.id] = story

    def update(self):

        now = time.time()

        for story in self.stories.values():

            age = now - story.created_time

            if story.status == TimelineStatus.NEW:

                if age >= story.delay_seconds:
                    story.status = TimelineStatus.READY

            elif story.status == TimelineStatus.AIRED:

                if (
                    story.air_count == 1
                    and now - story.last_aired >= story.follow_up_after
                ):
                    story.status = TimelineStatus.FOLLOW_UP

                if age >= story.expire_after:
                    story.status = TimelineStatus.EXPIRED

    def next_story(self):

        self.update()

        candidates = []

        for story in self.stories.values():

            if story.status in [
                TimelineStatus.READY,
                TimelineStatus.FOLLOW_UP,
            ]:
                candidates.append(story)

        if not candidates:
            return None

        candidates.sort(
            key=lambda s: (
                -s.priority,
                s.created_time,
            )
        )

        chosen = candidates[0]

        chosen.status = TimelineStatus.AIRED
        chosen.last_aired = time.time()
        chosen.air_count += 1

        return chosen

    def cleanup(self):

        remove = []

        for key, story in self.stories.items():

            if story.status == TimelineStatus.EXPIRED:
                remove.append(key)

        for key in remove:
            del self.stories[key]

    def has_pending(self):

        self.update()

        for story in self.stories.values():

            if story.status in (
                TimelineStatus.READY,
                TimelineStatus.FOLLOW_UP,
            ):
                return True

        return False

    def debug(self):

        print("\nEDITORIAL TIMELINE")
        print("-" * 60)

        for story in self.stories.values():

            print(
                f"{story.headline} | "
                f"{story.status.value} | "
                f"Priority {story.priority} | "
                f"Aired {story.air_count}"
            )