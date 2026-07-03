from dataclasses import dataclass


@dataclass(frozen=True)
class ActionEvent:
    event_type: str
    headline: str
    summary: str
    importance: int
    primary_car_idx: int
    participant_car_indices: tuple[int, ...]

    @property
    def camera_target_car_idx(self):
        return self.primary_car_idx


class ActionDetector:
    """Find tightly grouped, position-adjacent cars without inventing lane data."""

    SIDE_BY_SIDE_THRESHOLD = 0.0010
    THREE_CAR_THRESHOLD = 0.0018

    def __init__(self):
        self.previous_close_pairs = set()
        self.previous_action_signatures = set()

    def analyze(self, results, driver_lookup, lap_dist_pct_status, pit_road_status, current_lap):
        if current_lap < 1 or not results or not lap_dist_pct_status:
            return []

        cars = self._ordered_active_cars(results, lap_dist_pct_status, pit_road_status)
        if len(cars) < 2 or not any(car["distance"] > 0 for car in cars):
            return []

        close_pairs = set()
        for first, second in zip(cars, cars[1:]):
            if (
                second["position"] - first["position"] == 1
                and self._same_lap(first, second)
                and self._gap(first, second) <= self.SIDE_BY_SIDE_THRESHOLD
            ):
                close_pairs.add(frozenset((first["car_idx"], second["car_idx"])))

        events = []
        triple_members = set()
        active_signatures = set()
        for index in range(len(cars) - 2):
            group = cars[index : index + 3]
            positions = [car["position"] for car in group]
            if (
                positions != list(range(positions[0], positions[0] + 3))
                or not self._same_lap(*group)
                or self._spread(group) > self.THREE_CAR_THRESHOLD
            ):
                continue
            participants = tuple(car["car_idx"] for car in group)
            triple_members.update(participants)
            signature = ("three_car_battle", participants)
            active_signatures.add(signature)
            if signature in self.previous_action_signatures:
                continue

            newcomer = self._find_newcomer(participants)
            names = [self._name(driver_lookup, car_idx) for car_idx in participants]
            if newcomer is not None:
                newcomer_name = self._name(driver_lookup, newcomer)
                others = [name for car_idx, name in zip(participants, names) if car_idx != newcomer]
                summary = f"{newcomer_name} has joined {others[0]} and {others[1]} in a three-car fight."
                primary = newcomer
            else:
                summary = f"{names[0]}, {names[1]}, and {names[2]} are packed together in a three-car battle."
                primary = participants[1]

            events.append(ActionEvent(
                event_type="three_car_battle",
                headline="Three-car battle developing",
                summary=summary,
                importance=10,
                primary_car_idx=primary,
                participant_car_indices=participants,
            ))

        for pair in close_pairs:
            participants = tuple(car["car_idx"] for car in cars if car["car_idx"] in pair)
            if any(car_idx in triple_members for car_idx in participants):
                continue
            signature = ("side_by_side", participants)
            active_signatures.add(signature)
            if signature in self.previous_action_signatures:
                continue
            first_name, second_name = [self._name(driver_lookup, car_idx) for car_idx in participants]
            events.append(ActionEvent(
                event_type="side_by_side",
                headline=f"{first_name} and {second_name} are side by side",
                summary=f"{first_name} is alongside {second_name} in a close fight for position.",
                importance=9,
                primary_car_idx=participants[0],
                participant_car_indices=participants,
            ))

        self.previous_close_pairs = close_pairs
        self.previous_action_signatures = active_signatures
        return events

    def _ordered_active_cars(self, results, distances, pit_status):
        zero_based = any(self._integer(car.get("Position"), 999) == 0 for car in results)
        cars = []
        for car in results:
            car_idx = self._integer(car.get("CarIdx"), -1)
            if car_idx < 0 or car_idx >= len(distances):
                continue
            if car_idx < len(pit_status) and pit_status[car_idx]:
                continue
            try:
                distance = float(distances[car_idx])
            except (TypeError, ValueError):
                continue
            position = self._integer(car.get("Position"), 999) + (1 if zero_based else 0)
            if position <= 0 or position >= 999:
                continue
            cars.append({
                "car_idx": car_idx,
                "position": position,
                "lap": self._integer(car.get("LapsComplete", car.get("Lap", 0)), 0),
                "distance": distance % 1.0,
            })
        return sorted(cars, key=lambda car: car["position"])

    def _find_newcomer(self, participants):
        for car_idx in participants:
            other_pair = frozenset(item for item in participants if item != car_idx)
            if other_pair in self.previous_close_pairs:
                return car_idx
        return None

    @staticmethod
    def _same_lap(*cars):
        return len({car["lap"] for car in cars}) == 1

    @staticmethod
    def _gap(first, second):
        difference = abs(first["distance"] - second["distance"])
        return min(difference, 1.0 - difference)

    def _spread(self, cars):
        return max(self._gap(first, second) for first in cars for second in cars)

    @staticmethod
    def _name(driver_lookup, car_idx):
        return driver_lookup.get(car_idx, {}).get("name", f"Car {car_idx}")

    @staticmethod
    def _integer(value, default):
        try:
            return int(value)
        except (TypeError, ValueError):
            return default
