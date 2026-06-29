from dataclasses import dataclass, field
from typing import Dict, List


@dataclass
class MomentumProfile:
    car_idx: int
    driver_name: str
    car_number: str

    position_history: List[int] = field(default_factory=list)

    current_position: int = 0

    momentum_score: float = 50.0
    confidence: float = 0.0

    trend: str = "steady"
    status: str = "holding"

    average_gain_rate: float = 0.0
    recent_position_change: int = 0


class MomentumTracker:
    """
    Calculates driver momentum.

    This class intentionally does NOT create commentary.

    It simply answers:

        Is this driver's race getting better or worse?
    """

    HISTORY_LENGTH = 15

    def __init__(self):
        self.profiles: Dict[int, MomentumProfile] = {}

    def update(self, results, driver_lookup):
        if not results:
            return

        for car in results:

            car_idx = car.get("CarIdx")

            if car_idx is None:
                continue

            position = self.safe_int(car.get("Position", 0))

            if position <= 0:
                continue

            info = driver_lookup.get(car_idx, {})

            profile = self.get_or_create(
                car_idx,
                info.get("name", f"Car {car_idx}"),
                info.get("number", "?"),
            )

            profile.current_position = position

            profile.position_history.append(position)

            if len(profile.position_history) > self.HISTORY_LENGTH:
                profile.position_history.pop(0)

            self.calculate(profile)

    def calculate(self, profile):

        if len(profile.position_history) < 5:
            return

        first = profile.position_history[0]
        last = profile.position_history[-1]

        gained = first - last

        profile.recent_position_change = gained
        profile.average_gain_rate = gained / len(profile.position_history)

        profile.momentum_score = max(
            0,
            min(
                100,
                50 + gained * 8
            ),
        )

        profile.confidence = min(
            100,
            len(profile.position_history) / self.HISTORY_LENGTH * 100
        )

        if gained >= 4:
            profile.trend = "strong_up"
            profile.status = "charging"

        elif gained >= 2:
            profile.trend = "up"
            profile.status = "moving forward"

        elif gained <= -4:
            profile.trend = "strong_down"
            profile.status = "fading"

        elif gained <= -2:
            profile.trend = "down"
            profile.status = "losing ground"

        else:
            profile.trend = "steady"
            profile.status = "holding"

    def hottest_drivers(self, limit=5):
        return sorted(
            self.profiles.values(),
            key=lambda p: p.momentum_score,
            reverse=True,
        )[:limit]

    def coldest_drivers(self, limit=5):
        return sorted(
            self.profiles.values(),
            key=lambda p: p.momentum_score,
        )[:limit]

    def get_profile(self, car_idx):
        return self.profiles.get(car_idx)

    def get_or_create(self, car_idx, name, number):

        if car_idx not in self.profiles:
            self.profiles[car_idx] = MomentumProfile(
                car_idx=car_idx,
                driver_name=name,
                car_number=number,
            )

        profile = self.profiles[car_idx]
        profile.driver_name = name
        profile.car_number = number

        return profile

    @staticmethod
    def safe_int(value):
        try:
            return int(value)
        except Exception:
            return 0