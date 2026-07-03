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
        self.majority_announced = False
        self.small_group_announced = False
        self.seen_on_pit_road = set()
        self.latest_results = []
        self.latest_driver_lookup = {}

    def update(self, under_caution, results, driver_lookup, pit_road_status):
        if not under_caution:
            self.reset()
            return None

        if not self.active:
            self.active = True
            self.majority_announced = False
            self.small_group_announced = False
            self.seen_on_pit_road = set()

        valid_results = [
            car for car in results or [] if car.get("CarIdx") is not None
        ]
        self.latest_results = valid_results
        self.latest_driver_lookup = dict(driver_lookup or {})
        for car in valid_results:
            car_idx = car.get("CarIdx")
            if self.is_on_pit_road(car_idx, pit_road_status):
                self.seen_on_pit_road.add(car_idx)

        field_size = len(valid_results)
        majority_count = field_size // 2 + 1
        if (
            self.majority_announced
            or field_size < 3
            or len(self.seen_on_pit_road) < majority_count
        ):
            return None

        self.majority_announced = True
        featured, name_summary = self.featured_pitters(valid_results, driver_lookup)
        return CautionPitReport(
            message=(
                "Pit road is busy under this caution. "
                f"A majority of the field has come in, {len(self.seen_on_pit_road)} "
                f"of {field_size} cars, including {name_summary}. "
                "This is a major strategy reset before the restart."
            ),
            car_indices=featured,
        )

    def build_small_group_report(self):
        if (
            self.small_group_announced
            or self.majority_announced
            or len(self.seen_on_pit_road) == 0
        ):
            return None

        self.small_group_announced = True
        featured, name_summary = self.featured_pitters(
            self.latest_results,
            self.latest_driver_lookup,
        )
        pitter_count = len(self.seen_on_pit_road)
        plural = "car has" if pitter_count == 1 else "cars have"
        return CautionPitReport(
            message=(
                f"Only a few takers on pit road under this caution. "
                f"{pitter_count} {plural} come in, including {name_summary}. "
                "Most of the field is choosing track position for the restart."
            ),
            car_indices=featured,
            importance=8,
        )

    def featured_pitters(self, results, driver_lookup):
        sorted_pitters = sorted(
            [
                car
                for car in results or []
                if car.get("CarIdx") in self.seen_on_pit_road
            ],
            key=lambda car: self.safe_int(car.get("Position"), 999),
        )
        featured = tuple(car.get("CarIdx") for car in sorted_pitters[:3])
        names = [
            driver_lookup.get(car_idx, {}).get("name", f"Car {car_idx}")
            for car_idx in featured
        ]
        return featured, self.join_names(names)

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
