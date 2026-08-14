import time


class BoothFollowupDirector:
    """Creates short booth handoff lines after selected lead-announcer stories.

    These are intentionally small. The goal is not another full call; it is the
    color analyst adding a racing thought so the booth sounds like a team.
    """

    FOLLOW_UP_TYPES = {
        "battle",
        "battle_for_lead",
        "battle_for_top_five",
        "battle_for_top_ten",
        "biggest_mover",
        "lead_change",
        "momentum",
        "side_by_side",
        "three_car_battle",
        "top_five_charge",
    }

    def __init__(self):
        self.last_follow_up_by_key = {}
        self.minimum_repeat_seconds = 120

    def follow_up_for(self, item, race_state=None):
        if not item:
            return None
        if str(getattr(item, "speaker", "") or "") != "lead":
            return None

        laps_remaining = self.safe_int(getattr(race_state, "laps_remaining", 0))
        if 0 < laps_remaining <= 10:
            return None

        story_type = str(getattr(item, "story_type", "") or "")
        if story_type not in self.FOLLOW_UP_TYPES:
            return None

        priority = self.safe_int(getattr(item, "priority", 0))
        if priority < 8:
            return None

        key = self.story_key(item)
        now = time.time()
        if now - self.last_follow_up_by_key.get(key, 0.0) < self.minimum_repeat_seconds:
            return None

        line = self.build_line(story_type, race_state)
        if not line:
            return None

        self.last_follow_up_by_key[key] = now
        return line

    def build_line(self, story_type, race_state=None):
        laps_remaining = self.safe_int(getattr(race_state, "laps_remaining", 0))
        closing = 0 < laps_remaining <= 10

        if story_type in {"lead_change", "battle_for_lead"}:
            if closing:
                return (
                    "This is where every corner matters now. Clean air is "
                    "important, but one small mistake can bring the challenger "
                    "right back into it."
                )
            return (
                "That is a nice little swing in the race. Now we get to see "
                "whether the leader can stretch it out or if this stays close."
            )

        if story_type in {"battle", "battle_for_top_five", "battle_for_top_ten"}:
            return (
                "That is the kind of fight that makes the middle of a run matter. "
                "Neither driver has to force it yet, but the pressure is starting "
                "to build."
            )

        if story_type in {"side_by_side", "three_car_battle"}:
            return (
                "That is exactly why you show these battles. It may not be for "
                "the lead, but every spot matters when the field is this tight."
            )

        if story_type in {"biggest_mover", "top_five_charge", "momentum"}:
            return (
                "That is real forward progress, and it deserves a little camera "
                "time. Sometimes the best story is not out front; it is the "
                "driver quietly working through the field."
            )

        return None

    @staticmethod
    def story_key(item):
        return ":".join(
            str(part)
            for part in (
                getattr(item, "story_type", ""),
                getattr(item, "driver_name", ""),
                getattr(item, "car_number", ""),
            )
            if part
        )

    @staticmethod
    def safe_int(value, default=0):
        try:
            return int(value)
        except (TypeError, ValueError):
            return default
