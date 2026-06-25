class EventQueue:

    def __init__(self):
        self.queue = []

    def add(self, event):
        self.queue.append(event)

    def has_events(self):
        return len(self.queue) > 0

    def next_event(self):
        if self.queue:
            return self.queue.pop(0)
        return None