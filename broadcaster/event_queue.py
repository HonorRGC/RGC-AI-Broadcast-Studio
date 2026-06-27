class EventQueue:
    def __init__(self):
        self.events = []

    def add(self, event):
        if event:
            self.events.append(event)
            self.events.sort(key=lambda e: e.importance, reverse=True)

    def next_event(self):
        if self.events:
            return self.events.pop(0)
        return None

    def get_next(self):
        return self.next_event()

    def has_events(self):
        return len(self.events) > 0

    def clear(self):
        self.events = []