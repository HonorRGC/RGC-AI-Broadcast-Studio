from dataclasses import dataclass

from helpers.position_formatter import PositionFormatter


@dataclass(frozen=True)
class StorylineEvent:
    story_type: str
    headline: str
    summary: str
    priority: int = 7
    speaker: str = "jeff"
    camera_target_car_idx: int | None = None
    participant_car_indices: tuple[int, ...] = ()
    driver_name: str = ""
    car_number: str = ""


class StorylineDirector:
    """
    Turns race memory into broadcast stories.

    This is the layer that lets the booth connect dots from earlier in the
    event: recoveries, fades, pit-cycle consequences, and race-long arcs.
    """

    def __init__(self):
        self.sent_topics = {}

    def analyze(self, driver_memory, race_state=None, current_lap=0):
        if not driver_memory or current_lap < 8:
            return []
        if race_state and not getattr(race_state, "is_green", False):
            return []

        records = list(getattr(driver_memory, "records", {}).values())
        if not records:
            return []

        events = []
        recovery = self.detect_recovery(records, current_lap)
        if recovery:
            events.append(recovery)

        fade = self.detect_fade(records, current_lap)
        if fade:
            events.append(fade)

        pit_cycle = self.detect_pit_cycle_story(records, current_lap)
        if pit_cycle:
            events.append(pit_cycle)

        return events[:2]

    def detect_recovery(self, records, current_lap):
        candidates = []
        for record in records:
            if self.safe_int(record.laps_recorded) < 5:
                continue
            current = self.safe_int(record.current_position)
            worst = self.safe_int(record.worst_position)
            best = self.safe_int(record.best_position)
            if current <= 0 or worst <= 0:
                continue
            recovered = worst - current
            if recovered >= 5 and current <= 12:
                candidates.append((recovered, current, best, record))

        if not candidates:
            return None

        recovered, current, best, record = max(candidates, key=lambda item: item[0])
        topic = ("recovery", record.car_idx)
        if self.was_recently_sent(topic, current_lap, 18):
            return None

        current_text = PositionFormatter.ordinal(current)
        worst_text = PositionFormatter.ordinal(record.worst_position)
        message = (
            f"Keep an eye on {record.driver_name} in the number {record.car_number}. "
            f"Earlier in this race, they were back in {worst_text}, but now they "
            f"have recovered to {current_text}. That is the kind of race-long climb "
            "that can get missed if you only watch the front."
        )
        self.mark_sent(topic, current_lap)
        return StorylineEvent(
            story_type="race_recovery",
            headline=message,
            summary=message,
            priority=7 if current > 5 else 8,
            speaker="jeff",
            camera_target_car_idx=record.car_idx,
            participant_car_indices=(record.car_idx,),
            driver_name=record.driver_name,
            car_number=record.car_number,
        )

    def detect_fade(self, records, current_lap):
        candidates = []
        for record in records:
            if self.safe_int(record.laps_recorded) < 5:
                continue
            current = self.safe_int(record.current_position)
            best = self.safe_int(record.best_position)
            if current <= 0 or best <= 0:
                continue
            lost = current - best
            if lost >= 5 and best <= 6:
                candidates.append((lost, current, best, record))

        if not candidates:
            return None

        lost, current, best, record = max(candidates, key=lambda item: item[0])
        topic = ("fade", record.car_idx)
        if self.was_recently_sent(topic, current_lap, 18):
            return None

        current_text = PositionFormatter.ordinal(current)
        best_text = PositionFormatter.ordinal(best)
        message = (
            f"{record.driver_name} has gone the wrong direction after running as "
            f"high as {best_text}. The number {record.car_number} is now shown "
            f"{current_text}, so Jeff will be watching whether that is handling, "
            "traffic, tire falloff, or just the rhythm of this run going away."
        )
        self.mark_sent(topic, current_lap)
        return StorylineEvent(
            story_type="race_fade",
            headline=message,
            summary=message,
            priority=7,
            speaker="jeff",
            camera_target_car_idx=record.car_idx,
            participant_car_indices=(record.car_idx,),
            driver_name=record.driver_name,
            car_number=record.car_number,
        )

    def detect_pit_cycle_story(self, records, current_lap):
        candidates = []
        for record in records:
            if self.safe_int(record.pit_stops) <= 0:
                continue
            last_pit_lap = self.safe_int(record.last_pit_lap)
            if last_pit_lap <= 0 or current_lap - last_pit_lap < 3:
                continue
            current = self.safe_int(record.current_position)
            best = self.safe_int(record.best_position)
            worst = self.safe_int(record.worst_position)
            if current <= 0:
                continue
            swing = max(abs(current - best), abs(worst - current))
            if swing >= 4:
                candidates.append((swing, current, record))

        if not candidates:
            return None

        _, current, record = max(candidates, key=lambda item: item[0])
        topic = ("pit_cycle", record.car_idx, record.last_pit_lap)
        if self.was_recently_sent(topic, current_lap, 30):
            return None

        current_text = PositionFormatter.ordinal(current)
        message = (
            f"The pit cycle has become part of {record.driver_name}'s story. "
            f"The number {record.car_number} last came to pit road around lap "
            f"{record.last_pit_lap}, and now they are scored {current_text}. "
            "That is the kind of sequence Sarah will keep tracking as strategy "
            "starts to separate the field."
        )
        self.mark_sent(topic, current_lap)
        return StorylineEvent(
            story_type="pit_cycle_memory",
            headline=message,
            summary=message,
            priority=7,
            speaker="sarah",
            camera_target_car_idx=record.car_idx,
            participant_car_indices=(record.car_idx,),
            driver_name=record.driver_name,
            car_number=record.car_number,
        )

    def was_recently_sent(self, topic, current_lap, cooldown_laps):
        last_lap = self.sent_topics.get(topic)
        return last_lap is not None and current_lap - last_lap < cooldown_laps

    def mark_sent(self, topic, current_lap):
        self.sent_topics[topic] = current_lap

    @staticmethod
    def safe_int(value, default=0):
        try:
            return int(value)
        except Exception:
            return default
