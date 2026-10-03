import re


METERS_PER_SECOND_TO_MPH = 2.2369362921
KILOMETERS_TO_MILES = 0.6213711922


def parse_track_length_miles(value):
    if value in (None, ""):
        return 0.0
    text = str(value).strip().lower()
    match = re.search(r"([0-9]+(?:\.[0-9]+)?)", text)
    if not match:
        return 0.0
    length = float(match.group(1))
    if "km" in text or "kilometer" in text:
        return length * KILOMETERS_TO_MILES
    return length


def speed_value_to_mph(value):
    try:
        speed = float(value)
    except (TypeError, ValueError):
        return 0.0
    if speed <= 0:
        return 0.0
    return speed * METERS_PER_SECOND_TO_MPH if speed < 120 else speed


class CarSpeedTracker:
    """Estimate per-car MPH from lap-distance telemetry when direct speed is absent."""

    def __init__(self):
        self._samples = {}
        self._mph_by_car_idx = {}

    def update(
        self,
        *,
        session_time,
        lap_dist_pct_by_car_idx,
        results,
        track_length_miles,
    ):
        try:
            now = float(session_time)
            track_length = float(track_length_miles)
        except (TypeError, ValueError):
            return dict(self._mph_by_car_idx)
        if now <= 0 or track_length <= 0:
            return dict(self._mph_by_car_idx)

        laps_by_car_idx = {}
        for car in results or []:
            try:
                laps_by_car_idx[int(car.get("CarIdx"))] = int(
                    car.get("LapsComplete") or car.get("Lap") or 0
                )
            except (TypeError, ValueError):
                continue

        for car_idx, lap_pct in enumerate(lap_dist_pct_by_car_idx or []):
            try:
                pct = float(lap_pct)
            except (TypeError, ValueError):
                continue
            if pct < 0:
                continue

            progress = laps_by_car_idx.get(car_idx, 0) + pct
            previous = self._samples.get(car_idx)
            self._samples[car_idx] = (now, progress)
            if not previous:
                continue

            previous_time, previous_progress = previous
            elapsed = now - previous_time
            if elapsed <= 0.05 or elapsed > 10.0:
                continue

            progress_delta = progress - previous_progress
            if progress_delta < -0.5:
                progress_delta += 1.0
            if progress_delta <= 0 or progress_delta > 0.25:
                continue

            mph = progress_delta * track_length * 3600.0 / elapsed
            if 1 <= mph <= 260:
                self._mph_by_car_idx[car_idx] = mph

        return dict(self._mph_by_car_idx)
