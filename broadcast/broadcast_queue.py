import time
from dataclasses import dataclass, field
from typing import List


@dataclass(order=True)
class ScheduledBroadcast:
    sort_index: int = field(init=False, repr=False)
    priority: int
    message: str = field(compare=False)
    category: str = field(default="race_commentary", compare=False)
    protected: bool = field(default=False, compare=False)
    created_at: float = field(default_factory=time.time, compare=False)

    def __post_init__(self):
        self.sort_index = -self.priority


class BroadcastQueue:
    def __init__(self):
        self.items: List[ScheduledBroadcast] = []
        self.last_spoken_time = 0
        self.minimum_gap_seconds = 10

    def add(self, commentary, priority=5, category="race_commentary", protected=False):
        if not commentary:
            return

        self.items.append(
            ScheduledBroadcast(
                priority=priority,
                message=commentary,
                category=category,
                protected=protected,
            )
        )

        self.items.sort()

    def has_items(self):
        return len(self.items) > 0

    def can_speak(self):
        return time.time() - self.last_spoken_time >= self.minimum_gap_seconds

    def next_commentary(self):
        if self.items and self.can_speak():
            self.last_spoken_time = time.time()
            return self.items.pop(0).message
        return None

    def clear_unprotected(self):
        self.items = [item for item in self.items if item.protected]

    def clear_category(self, category):
        self.items = [item for item in self.items if item.category != category or item.protected]

    def clear_race_chatter(self):
        self.clear_category("race_commentary")

    def force_next(self):
        if self.items:
            self.last_spoken_time = time.time()
            return self.items.pop(0).message
        return None