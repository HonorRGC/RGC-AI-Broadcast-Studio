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
                    priority=7,
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
        return (
            f"{position}, the {entry['number']} of {entry['name']}."
        )

    def results_are_zero_based(self, results):
        return any(car.get("Position") == 0 for car in results or [])

    def display_position(self, raw_position, zero_based):
        try:
            position = int(raw_position)
        except Exception:
            return 999
        return position + 1 if zero_based else position
