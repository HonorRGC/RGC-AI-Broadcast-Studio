from dataclasses import dataclass

from helpers.position_formatter import PositionFormatter


@dataclass(frozen=True)
class FieldRundownSegment:
    message: str
    priority: int
    speaker: str
    category: str
    camera_sequence: tuple[int, ...] = ()


class FieldRundownDirector:
    GROUP_SIZE = 8

    def __init__(self):
        self.quarter_rundown_sent = False

    def update(self, results, driver_lookup, current_lap, total_laps, under_green):
        if self.quarter_rundown_sent:
            return []
        if not under_green or total_laps < 20 or current_lap <= 0:
            return []

        quarter_lap = max(1, round(total_laps * 0.25))
        if current_lap < quarter_lap:
            return []

        frozen_results = self.freeze_running_order(results)
        if len(frozen_results) < 3:
            return []

        self.quarter_rundown_sent = True
        return self.build_quarter_rundown(
            frozen_results,
            driver_lookup,
            current_lap=current_lap,
            total_laps=total_laps,
        )

    def build_quarter_rundown(
        self,
        frozen_results,
        driver_lookup,
        current_lap=0,
        total_laps=0,
    ):
        entries = []
        for display_position, car in enumerate(frozen_results, start=1):
            car_idx = car.get("CarIdx")
            driver_info = driver_lookup.get(car_idx, {})
            name = driver_info.get("name", f"Car {car_idx}")
            number = driver_info.get("number", "?")
            entries.append(
                {
                    "position": display_position,
                    "starting_position": self.safe_int(
                        car.get("StartingPosition"),
                        0,
                    ),
                    "car_idx": car_idx,
                    "name": name,
                    "number": number,
                }
            )

        segments = []
        for group_number, start in enumerate(
            range(0, len(entries), self.GROUP_SIZE),
            start=1,
        ):
            group = entries[start:start + self.GROUP_SIZE]
            intro = (
                f"At quarter distance, lap {current_lap} of {total_laps}, "
                "here is the field as they ran when we froze the order."
                if group_number == 1
                else "Continuing the quarter-race field rundown."
            )
            lines = [self.format_entry(entry) for entry in group]
            closing = ""
            if start + self.GROUP_SIZE >= len(entries):
                closing = " That completes the full-field reset at quarter distance."

            segments.append(
                FieldRundownSegment(
                    message=f"{intro} {' '.join(lines)}{closing}",
                    priority=8,
                    speaker="lead" if group_number % 2 == 1 else "jeff",
                    category=f"quarter_field_rundown_{group_number}",
                    camera_sequence=tuple(
                        entry["car_idx"]
                        for entry in group
                        if entry["car_idx"] is not None
                    ),
                )
            )

        return segments

    def freeze_running_order(self, results):
        valid = [dict(car) for car in results or [] if car.get("CarIdx") is not None]
        zero_based = self.results_are_zero_based(valid)
        return sorted(
            valid,
            key=lambda car: self.display_position(
                car.get("Position", 999),
                zero_based,
            ),
        )

    def format_entry(self, entry):
        position = PositionFormatter.ordinal(entry["position"])
        starting_position = entry.get("starting_position", 0)
        movement = self.movement_phrase(
            current_position=entry["position"],
            starting_position=starting_position,
        )
        return (
            f"{position}, the {entry['number']} of {entry['name']}{movement}."
        )

    def movement_phrase(self, current_position, starting_position):
        if not starting_position:
            return ""
        starting = PositionFormatter.ordinal(starting_position)
        net = starting_position - current_position
        if net > 0:
            return f", after starting {starting}, up {self.position_count(net)}"
        if net < 0:
            return (
                f", after starting {starting}, down "
                f"{self.position_count(abs(net))}"
            )
        return f", right where they started in {starting}"

    def results_are_zero_based(self, results):
        return any(car.get("Position") == 0 for car in results or [])

    def display_position(self, raw_position, zero_based):
        try:
            position = int(raw_position)
        except Exception:
            return 999
        return position + 1 if zero_based else position

    def position_count(self, count):
        try:
            count = int(count)
        except Exception:
            return f"{count} spots"
        if count == 1:
            return "one spot"
        return f"{count} spots"

    def safe_int(self, value, default=0):
        try:
            return int(value)
        except Exception:
            return default
