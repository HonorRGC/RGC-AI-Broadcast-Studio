import time


class VoiceDirector:
    def __init__(self):
        self.last_lead_time = 0.0
        self.last_jeff_time = 0.0

        self.jeff_cooldown_seconds = 45
        self.jeff_delay_seconds = 2

    def should_add_jeff(self, event):
        if event is None:
            return False

        event_type = getattr(event, "event_type", "")
        importance = getattr(event, "importance", 0)
        new_position = getattr(event, "new_position", 999)
        positions_gained = getattr(event, "positions_gained_from_start", 0)

        if event_type != "PASS":
            return False

        if not self.jeff_is_off_cooldown():
            return False

        if new_position == 1:
            return True

        if new_position <= 5 and importance >= 8:
            return True

        if positions_gained >= 8:
            return True

        return False

    def jeff_is_off_cooldown(self):
        return time.time() - self.last_jeff_time >= self.jeff_cooldown_seconds

    def mark_lead_spoke(self):
        self.last_lead_time = time.time()

    def mark_jeff_spoke(self):
        self.last_jeff_time = time.time()

    def jeff_delay(self):
        return self.jeff_delay_seconds