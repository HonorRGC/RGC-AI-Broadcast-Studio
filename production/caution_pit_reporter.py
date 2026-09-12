from dataclasses import dataclass

from config import PIT_BROADCASTER_NAME


@dataclass(frozen=True)
class CautionPitReport:
    message: str
    car_indices: tuple[int, ...]
    importance: int = 10


class CautionPitReporter:
    def __init__(self):
        self._phrase_counts = {}
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

        return None

    def build_majority_report(self, pit_states=None):
        if self.majority_announced:
            return None

        field_size = len(self.latest_results)
        majority_count = field_size // 2 + 1
        if field_size < 3 or len(self.seen_on_pit_road) < majority_count:
            return None

        self.majority_announced = True
        featured, name_summary = self.featured_pitters(
            self.latest_results,
            self.latest_driver_lookup,
        )
        service_note = self.service_summary(pit_states)
        opener = self.rotate_phrase(
            "majority_opener",
            [
                "Pit road is busy under this caution.",
                f"{PIT_BROADCASTER_NAME} is reporting a busy pit road under this yellow.",
                "The pit lane has come alive under this caution.",
                "A big chunk of the field has chosen pit road this time.",
            ],
        )
        count_phrase = self.rotate_phrase(
            "majority_count",
            [
                f"A majority of the field has come in, {len(self.seen_on_pit_road)} of {field_size} cars, including {name_summary}.",
                f"We have {len(self.seen_on_pit_road)} of {field_size} cars recorded on pit road, with {name_summary} among them.",
                f"That is {len(self.seen_on_pit_road)} of {field_size} cars coming to the attention of their crews, including {name_summary}.",
            ],
        )
        return CautionPitReport(
            message=(
                f"{opener} "
                f"{count_phrase} "
                f"{service_note}"
            ),
            car_indices=featured,
        )

    def build_small_group_report(self, pit_states=None):
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
        service_note = self.service_summary(pit_states)
        opener = self.rotate_phrase(
            "small_group_opener",
            [
                "Only a few takers on pit road under this caution.",
                "This is a smaller group choosing pit road under the yellow.",
                "Most of the field stayed out, but a few cars have come down pit road.",
                f"{PIT_BROADCASTER_NAME} has a short list of pit road traffic this time.",
            ],
        )
        count_phrase = self.rotate_phrase(
            "small_group_count",
            [
                f"{pitter_count} {plural} come in, including {name_summary}.",
                f"{pitter_count} {plural} been on pit road, with {name_summary} on that list.",
                f"The group includes {name_summary}, {pitter_count} {plural} total.",
            ],
        )
        return CautionPitReport(
            message=(
                f"{opener} "
                f"{count_phrase} "
                f"{service_note}"
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

    def service_summary(self, pit_states=None):
        states = pit_states or {}
        pitter_states = []
        for car_idx in self.seen_on_pit_road:
            state = states.get(car_idx) if hasattr(states, "get") else None
            if state is not None:
                pitter_states.append(state)

        extended = [
            state
            for state in pitter_states
            if float(getattr(state, "last_pit_stop_seconds", 0.0) or 0.0) >= 25.0
            or float(getattr(state, "last_pit_lane_seconds", 0.0) or 0.0) >= 65.0
        ]
        full_service = [
            state
            for state in pitter_states
            if float(getattr(state, "last_pit_stop_seconds", 0.0) or 0.0) >= 12.0
        ]
        track_position = [
            state
            for state in pitter_states
            if float(getattr(state, "last_pit_stop_seconds", 0.0) or 0.0) < 8.0
            and int(getattr(state, "last_pit_position_gain", 0) or 0) >= 2
        ]

        if extended:
            names = self.join_names(
                [
                    getattr(state, "driver_name", f"Car {getattr(state, 'car_idx', '?')}")
                    for state in extended[:3]
                ]
            )
            return self.rotate_phrase(
                "extended_service",
                [
                    f"{names} had an extended stop, which points toward damage repair or a longer service call before the restart.",
                    f"The longer stop for {names} suggests repairs or a more involved adjustment before they rejoin the field.",
                    f"{names} spent extra time with the crew, so damage repair may be part of that story.",
                ],
            )
        if full_service and track_position:
            names = self.join_names(
                [
                    self.car_label(state)
                    for state in track_position[:3]
                ]
            )
            return self.rotate_phrase(
                "mixed_service",
                [
                    f"Most of those stops look long enough for full service. {names} had the quicker stop and gained track position, so that has the look of a two-tire or fuel-only call.",
                    f"The main group appears to have had time for full service, while {names} came away quicker and picked up track position.",
                    f"There may be a split on pit road here: several longer stops, but {names} gained spots with a shorter stop.",
                ],
            )
        if full_service:
            return self.rotate_phrase(
                "full_service",
                [
                    "Several of those stops were long enough for full service, so tires and fuel are likely part of this strategy reset.",
                    "Those stop times look long enough for tires and fuel for a good portion of the group.",
                    "That looked more like regular service than a quick splash-and-go for several of the cars.",
                ],
            )
        if track_position:
            names = self.join_names(
                [
                    self.car_label(state)
                    for state in track_position[:3]
                ]
            )
            return self.rotate_phrase(
                "track_position",
                [
                    f"{names} gained spots with a short stop, so that looks like a track-position call before the restart.",
                    f"{names} came away with track position, which usually means the crew kept that stop short.",
                    f"The quick stop paid off for {names}; they picked up spots for the restart.",
                ],
            )
        return self.rotate_phrase(
            "generic_service",
            [
                "This changes the restart picture once the field gets doubled up.",
                "We will see who gained clean air and who has fresher tires when they come back to green.",
                "The pit story is still forming, but track position will matter when they stack back up.",
            ],
        )

    @staticmethod
    def car_label(state):
        number = getattr(state, "car_number", "")
        if number:
            return f"the {number}"
        return getattr(state, "driver_name", f"Car {getattr(state, 'car_idx', '?')}")

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

    def rotate_phrase(self, key, phrases):
        if not phrases:
            return ""
        index = self._phrase_counts.get(key, 0)
        self._phrase_counts[key] = index + 1
        return phrases[index % len(phrases)]

    @staticmethod
    def safe_int(value, default=0):
        try:
            return int(value)
        except (TypeError, ValueError):
            return default
