import time


class BroadcastQueue:
    def __init__(self):
        self.items = []
        self.last_spoken_time = 0
        self.minimum_gap_seconds = 10

    def add(self, commentary):
        self.items.append(commentary)

    def has_items(self):
        return len(self.items) > 0

    def can_speak(self):
        return time.time() - self.last_spoken_time >= self.minimum_gap_seconds

    def next_commentary(self):
        if self.items and self.can_speak():
            self.last_spoken_time = time.time()
            return self.items.pop(0)

        return None