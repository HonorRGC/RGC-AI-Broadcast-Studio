import time
from dataclasses import dataclass, field
from typing import List


@dataclass
class ScheduledBroadcast:
    priority: int
    message: str
    category: str = "race_commentary"
    protected: bool = False
    speaker: str = "lead"
    delay_seconds: float = 0.0
    created_at: float = field(default_factory=time.time)

    @property
    def ready_at(self):
        return self.created_at + self.delay_seconds


class BroadcastQueue:
    def __init__(self):
        self.items: List[ScheduledBroadcast] = []
        self.last_spoken_time = 0
        self.minimum_gap_seconds = 9

    def add(
        self,
        commentary,
        priority=5,
        category="race_commentary",
        protected=False,
        speaker="lead",
        delay_seconds=0.0,
    ):
        if not commentary:
            return

        self.items.append(
            ScheduledBroadcast(
                priority=priority,
                message=commentary,
                category=category,
                protected=protected,
                speaker=speaker,
                delay_seconds=delay_seconds,
            )
        )

    def has_items(self):
        return len(self.items) > 0

    def can_speak(self):
        return time.time() - self.last_spoken_time >= self.minimum_gap_seconds

    def next_item(self):
        if not self.items or not self.can_speak():
            return None

        now = time.time()
        ready_items = [item for item in self.items if item.ready_at <= now]

        if not ready_items:
            return None

        ready_items.sort(key=lambda item: item.priority, reverse=True)
        selected = ready_items[0]

        self.items.remove(selected)
        self.last_spoken_time = time.time()

        return selected

    def next_commentary(self):
        item = self.next_item()
        if item:
            return item.message
        return None

    def clear_unprotected(self):
        self.items = [item for item in self.items if item.protected]

    def clear_category(self, category):
        self.items = [
            item for item in self.items
            if item.category != category or item.protected
        ]

    def clear_race_chatter(self):
        self.clear_category("race_commentary")
        self.clear_category("color_commentary")