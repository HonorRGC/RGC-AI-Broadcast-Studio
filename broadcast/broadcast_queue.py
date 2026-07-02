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
        self.busy_until = 0.0
        self.minimum_gap_seconds = 2.5

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
        return time.time() >= self.busy_until

    def estimate_speech_seconds(self, message):
        words = len(str(message).split())
        return max(5.0, min(45.0, words / 2.45))

    def next_item(self):
        if not self.items or not self.can_speak():
            return None

        now = time.time()
        ready_items = [item for item in self.items if item.ready_at <= now]

        if not ready_items:
            return None

        protected_ready = [item for item in ready_items if item.protected]

        if protected_ready:
            selected = protected_ready[0]
        else:
            ready_items.sort(key=lambda item: item.priority, reverse=True)
            selected = ready_items[0]

        self.items.remove(selected)

        speech_time = self.estimate_speech_seconds(selected.message)
        self.busy_until = now + speech_time + self.minimum_gap_seconds

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