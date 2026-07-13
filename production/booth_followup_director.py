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
        self.minimum_repeat_seconds = 75

    def follow_up_for(self, item, race_state=None):
        if not item:
            return None
        if str(getattr(item, "speaker", "") or "") != "lead":
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
                    "Yeah, this is where every corner matters now. Clean air is "
                    "important, but one small mistake can bring the challenger "
                    "right back into it."
                )
            return (
                "Yeah, that changes the shape of this run. Clean air matters, "
                "but now the question is whether the pace holds up over the next "
                "few laps."
            )

        if story_type in {"battle", "battle_for_top_five", "battle_for_top_ten"}:
            return (
                "Yeah, this is the kind of fight that can pull more cars into "
                "the picture. If they stay close too long, the pack behind them "
                "starts getting a run."
            )

        if story_type in {"side_by_side", "three_car_battle"}:
            return (
                "Yeah, that is where patience gets tested. When cars are stacked "
                "that close together, one mistimed move can turn a good battle "
                "into a problem in a hurry."
            )

        if story_type in {"biggest_mover", "top_five_charge", "momentum"}:
            return (
                "Yeah, that is real forward progress. The next test is whether "
                "that pace is still there once the tires and traffic start to "
                "even everything back out."
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
