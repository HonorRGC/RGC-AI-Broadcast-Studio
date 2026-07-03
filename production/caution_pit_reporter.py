from dataclasses import dataclass


@dataclass(frozen=True)
class CautionPitReport:
    message: str
    car_indices: tuple[int, ...]
    importance: int = 10


class CautionPitReporter:
    def __init__(self):
        self.reset()

    def reset(self):
        self.active = False
        self.announced = False
        self.seen_on_pit_road = set()

    def update(self, under_caution, results, driver_lookup, pit_road_status):
        if not under_caution:
            self.reset()
            return None

        if not self.active:
            self.active = True
            self.announced = False
            self.seen_on_pit_road = set()

        valid_results = [
            car for car in results or [] if car.get("CarIdx") is not None
        ]
        for car in valid_results:
            car_idx = car.get("CarIdx")
            if self.is_on_pit_road(car_idx, pit_road_status):
                self.seen_on_pit_road.add(car_idx)

        field_size = len(valid_results)
        majority_count = field_size // 2 + 1
        if (
            self.announced
            or field_size < 3
            or len(self.seen_on_pit_road) < majority_count
        ):
            return None

        self.announced = True
        sorted_pitters = sorted(
            [
                car
                for car in valid_results
                if car.get("CarIdx") in self.seen_on_pit_road
            ],
            key=lambda car: self.safe_int(car.get("Position"), 999),
        )
        featured = tuple(car.get("CarIdx") for car in sorted_pitters[:3])
        names = [
            driver_lookup.get(car_idx, {}).get("name", f"Car {car_idx}")
            for car_idx in featured
        ]
        name_summary = self.join_names(names)
        return CautionPitReport(
            message=(
                "Pit road is busy under this caution. "
                f"A majority of the field has come in, {len(self.seen_on_pit_road)} "
                f"of {field_size} cars, including {name_summary}. "
                "This is a major strategy reset before the restart."
            ),
            car_indices=featured,
        )

    @staticmethod
    def is_on_pit_road(car_idx, pit_road_status):
        try:
            return bool(pit_road_status[int(car_idx)])
        except (IndexError, TypeError, ValueError):
            return False

    @staticmethod
    def join_names(names):
        if not names:
            return "several of the front runners"
        if len(names) == 1:
            return names[0]
        if len(names) == 2:
            return f"{names[0]} and {names[1]}"
        return f"{names[0]}, {names[1]}, and {names[2]}"

    @staticmethod
    def safe_int(value, default=0):
        try:
            return int(value)
        except (TypeError, ValueError):
            return default
