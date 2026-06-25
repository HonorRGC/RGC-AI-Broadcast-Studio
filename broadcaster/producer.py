class Producer:
    def __init__(self):
        self.minimum_importance = 6

    def choose_event(self, queue):
        while queue.has_events():
            event = queue.next_event()

            if event.importance >= self.minimum_importance:
                return event

        return None