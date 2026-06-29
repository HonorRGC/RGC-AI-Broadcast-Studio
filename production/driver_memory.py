from dataclasses import dataclass, field
from typing import Dict, List, Optional


@dataclass
class DriverMemoryRecord:
    car_idx: int
    driver_name: str
    car_number: str

    starting_position: int = 0
    current_position: int = 0
    best_position: int = 0
    worst_position: int = 0

    positions_gained: int = 0
    positions_lost: int = 0

    laps_recorded: int = 0
    last_seen_lap: int = 0

    pit_stops: int = 0
    last_pit_lap: int = 0
    was_on_pit_road: bool = False

    incident_notes: List[str] = field(default_factory=list)
    story_tags: List[str] = field(default_factory=list)


class DriverMemory:
    """
    Long-term driver memory.

    RaceIntelligence tracks what is happening right now.
    DriverMemory remembers each driver's full race.

    Future use:
    - Jeff context
    - Sarah context
    - OpenAI prompts
    - post-race summaries
    """

    def __init__(self):
        self.records: Dict[int, DriverMemoryRecord] = {}

    def update(
        self,
        results,
        driver_lookup,
        current_lap=0,
        pit_road_status=None,
    ):
        if not results:
            return

        for car in results:
            car_idx = car.get("CarIdx")

            if car_idx is None:
                continue

            position = self.safe_int(car.get("Position", 0))

            if position <= 0:
                continue

            driver_info = driver_lookup.get(car_idx, {})
            driver_name = driver_info.get("name", f"Car {car_idx}")
            car_number = driver_info.get("number", "?")

            record = self.get_or_create_record(
                car_idx=car_idx,
                driver_name=driver_name,
                car_number=car_number,
                position=position,
            )

            on_pit_road = self.get_array_bool(pit_road_status, car_idx)

            self.update_position_memory(record, position, current_lap)
            self.update_pit_memory(record, on_pit_road, current_lap)

            record.driver_name = driver_name
            record.car_number = car_number
            record.story_tags = self.build_story_tags(record)

    def get_or_create_record(self, car_idx, driver_name, car_number, position):
        if car_idx not in self.records:
            self.records[car_idx] = DriverMemoryRecord(
                car_idx=car_idx,
                driver_name=driver_name,
                car_number=car_number,
                starting_position=position,
                current_position=position,
                best_position=position,
                worst_position=position,
            )

        return self.records[car_idx]

    def update_position_memory(self, record, position, current_lap):
        record.current_position = position
        record.best_position = min(record.best_position, position)
        record.worst_position = max(record.worst_position, position)

        record.positions_gained = record.starting_position - position
        record.positions_lost = position - record.starting_position

        record.laps_recorded += 1
        record.last_seen_lap = current_lap

    def update_pit_memory(self, record, on_pit_road, current_lap):
        if on_pit_road and not record.was_on_pit_road:
            record.pit_stops += 1
            record.last_pit_lap = current_lap

        record.was_on_pit_road = on_pit_road

    def build_story_tags(self, record):
        tags = []

        if record.positions_gained >= 8:
            tags.append("big mover")

        if record.positions_gained >= 5 and record.current_position <= 5:
            tags.append("top five charge")

        if record.positions_lost >= 6:
            tags.append("fading")

        if record.pit_stops > 0:
            tags.append("has pitted")

        if record.current_position == 1:
            tags.append("leader")

        return tags

    def add_incident_note(self, car_idx, note):
        record = self.records.get(car_idx)

        if not record:
            return

        record.incident_notes.append(note)

        if len(record.incident_notes) > 10:
            record.incident_notes = record.incident_notes[-10:]

    def get_record(self, car_idx) -> Optional[DriverMemoryRecord]:
        return self.records.get(car_idx)

    def get_biggest_movers(self, limit=5):
        records = list(self.records.values())
        records.sort(key=lambda item: item.positions_gained, reverse=True)
        return records[:limit]

    def get_fading_drivers(self, limit=5):
        records = list(self.records.values())
        records.sort(key=lambda item: item.positions_lost, reverse=True)
        return records[:limit]

    def clear(self):
        self.records = {}

    def get_array_bool(self, values, index):
        try:
            if values is None:
                return False
            return bool(values[int(index)])
        except Exception:
            return False

    def safe_int(self, value):
        try:
            return int(value)
        except Exception:
            return 0