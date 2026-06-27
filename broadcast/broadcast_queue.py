import time


class BroadcastItem:
    def __init__(self, text, priority=50, category="normal"):
        self.text = text
        self.priority = priority
        self.category = category
        self.created_at = time.time()


class BroadcastQueue:
    def __init__(self):
        self.items = []
        self.last_spoken_time = 0
        self.minimum_gap_seconds = 16

    def add(self, text, priority=50, category="normal"):
        self.items.append(BroadcastItem(text, priority, category))
        self.items.sort(key=lambda item: item.priority, reverse=True)

    def clear(self):
        self.items = []

    def clear_normal_items(self):
        self.items = [
            item for item in self.items
            if item.category != "normal"
        ]

    def has_items(self):
        return len(self.items) > 0

    def can_speak(self):
        return time.time() - self.last_spoken_time >= self.minimum_gap_seconds

    def next_commentary(self):
        if self.items and self.can_speak():
            self.last_spoken_time = time.time()
            return self.items.pop(0).text

        return None