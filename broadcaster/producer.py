class Producer:
    def __init__(self):
        self.minimum_importance = 6

    def should_broadcast(self, event):
        return event.importance >= self.minimum_importance