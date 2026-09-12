from dataclasses import dataclass


@dataclass(frozen=True)
class FastestLapEvent:
    car_idx: int
    driver_name: str
    car_number: str
    lap_time: float
    message: str


class FastestLapTracker:
    MIN_LAP = 2
    MIN_IMPROVEMENT_SECONDS = 0.001

    def __init__(self):
        self.fastest_time = None
        self.fastest_car_idx = None

    def analyze(self, results, driver_lookup, current_lap):
        if current_lap < self.MIN_LAP:
            return None

        best = self.best_result(results)
        if not best:
            return None

        car_idx = best["car_idx"]
        lap_time = best["lap_time"]
        if self.fastest_time is not None:
            improvement = self.fastest_time - lap_time
            if improvement < self.MIN_IMPROVEMENT_SECONDS:
                return None

        self.fastest_time = lap_time
        self.fastest_car_idx = car_idx
        driver = (driver_lookup or {}).get(car_idx, {})
        name = driver.get("name", f"Car {car_idx}")
        number = driver.get("number", "?")
        return FastestLapEvent(
            car_idx=car_idx,
            driver_name=name,
            car_number=number,
            lap_time=lap_time,
            message=(
                f"New fastest lap of the race for {name} in the number {number}, "
                f"a {self.format_lap_time(lap_time)}."
            ),
        )

    def best_result(self, results):
        candidates = []
        for car in results or []:
            car_idx = car.get("CarIdx")
            lap_time = self.best_lap_value(car)
            if car_idx is None or lap_time <= 0:
                continue
            candidates.append({"car_idx": car_idx, "lap_time": lap_time})
        if not candidates:
            return None
        return min(candidates, key=lambda item: item["lap_time"])

    def best_lap_value(self, car):
        for key in ("FastestTime", "BestLapTime", "FastestLapTime", "BestTime"):
            value = car.get(key)
            if value not in (None, "", 0, 0.0):
                try:
                    return float(value)
                except (TypeError, ValueError):
                    continue
        return 0.0

    def format_lap_time(self, seconds):
        seconds = float(seconds)
        minutes = int(seconds // 60)
        remainder = seconds - minutes * 60
        if minutes:
            return f"{minutes}:{remainder:06.3f}"
        return f"{remainder:.3f}"
