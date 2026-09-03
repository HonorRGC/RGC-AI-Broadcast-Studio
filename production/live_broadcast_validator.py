import re
from dataclasses import dataclass


@dataclass
class BroadcastValidation:
    valid: bool
    reason: str = ""


class LiveBroadcastValidator:
    """Final live sanity check before a queued story reaches the booth.

    The editorial queue can be a few seconds behind live telemetry. This
    validator catches the most embarrassing cases: a driver pits while a
    leader/mover story is waiting, or the live running order no longer matches
    the claim being aired.
    """

    STORY_CATEGORIES = {
        "race_story",
        "fastest_lap",
        "final_laps_battle",
    }

    ORDER_SENSITIVE_CATEGORIES = {
        "caution_top_ten_reset",
    }

    def validate(self, item, telemetry):
        category = str(getattr(item, "category", "") or "")
        car_idx = getattr(item, "camera_target_car_idx", None)

        if category in self.ORDER_SENSITIVE_CATEGORIES:
            return self.validate_running_order_item(item, telemetry)

        if category not in self.STORY_CATEGORIES or car_idx is None:
            return BroadcastValidation(True)

        message = str(getattr(item, "message", "") or "")
        position = self.current_position(telemetry, car_idx)

        if self.is_on_pit_road(telemetry, car_idx):
            return BroadcastValidation(
                False,
                "driver went to pit road before the story aired",
            )

        if not self.is_active_on_track(telemetry, car_idx):
            return BroadcastValidation(
                False,
                "driver is no longer active on the racing surface",
            )

        if self.claims_lead(message) and position not in (None, 1):
            return BroadcastValidation(
                False,
                f"story claimed the lead but live position is P{position}",
            )

        if self.claims_top_five(message) and position is not None and position > 5:
            return BroadcastValidation(
                False,
                f"story claimed top five but live position is P{position}",
            )

        if self.claims_top_ten(message) and position is not None and position > 10:
            return BroadcastValidation(
                False,
                f"story claimed top ten but live position is P{position}",
            )

        return BroadcastValidation(True)

    def validate_running_order_item(self, item, telemetry):
        expected = tuple(
            car_idx
            for car_idx in (getattr(item, "participant_car_indices", ()) or ())
            if car_idx is not None
        )
        if not expected:
            return BroadcastValidation(True)

        live = self.current_top_order(telemetry, len(expected))
        if len(live) < min(3, len(expected)):
            return BroadcastValidation(
                False,
                "live running order was not available before the rundown aired",
            )
        if live != expected:
            return BroadcastValidation(
                False,
                "queued restart top ten no longer matches live scoring",
            )
        return BroadcastValidation(True)

    def current_position(self, telemetry, car_idx):
        results_reader = getattr(telemetry, "get_results", None)
        if not results_reader:
            return None
        results = results_reader() or []
        zero_based = any(self.safe_int(car.get("Position"), 999) == 0 for car in results)
        for car in results:
            if car.get("CarIdx") != car_idx:
                continue
            position = self.safe_int(car.get("Position"), 0)
            if position <= 0 and not zero_based:
                return None
            return position + 1 if zero_based else position
        return None

    def current_top_order(self, telemetry, count):
        results_reader = getattr(telemetry, "get_results", None)
        if not results_reader:
            return ()
        results = [
            car
            for car in (results_reader() or [])
            if car.get("CarIdx") is not None
        ]
        zero_based = any(self.safe_int(car.get("Position"), 999) == 0 for car in results)
        ordered = sorted(
            results,
            key=lambda car: self.display_position(
                car.get("Position", 999),
                zero_based,
            ),
        )
        return tuple(car.get("CarIdx") for car in ordered[:count])

    def display_position(self, raw_position, zero_based):
        position = self.safe_int(raw_position, 999)
        return position + 1 if zero_based else position

    def is_on_pit_road(self, telemetry, car_idx):
        pit_reader = getattr(telemetry, "get_car_idx_on_pit_road", None)
        if not pit_reader:
            return False
        try:
            return bool((pit_reader() or [])[int(car_idx)])
        except Exception:
            return False

    def is_active_on_track(self, telemetry, car_idx):
        surface_reader = getattr(telemetry, "get_car_idx_track_surface", None)
        if not surface_reader:
            return True
        try:
            surface = (surface_reader() or [])[int(car_idx)]
        except Exception:
            return True
        if surface is None:
            return True
        try:
            return int(surface) > 1
        except Exception:
            return True

    @staticmethod
    def claims_lead(message):
        text = str(message or "").lower()
        if "lead lap" in text:
            return False
        return bool(
            re.search(
                r"\b(in|for|takes?|holding|has|keeps|extends|controls)\s+the\s+lead\b|\bleader\b|\bleads\b",
                text,
            )
        )

    @staticmethod
    def claims_top_five(message):
        return bool(re.search(r"\btop[- ]five\b|\btop 5\b", str(message or "").lower()))

    @staticmethod
    def claims_top_ten(message):
        return bool(re.search(r"\btop[- ]ten\b|\btop 10\b", str(message or "").lower()))

    @staticmethod
    def safe_int(value, default=0):
        try:
            return int(value)
        except (TypeError, ValueError):
            return default
