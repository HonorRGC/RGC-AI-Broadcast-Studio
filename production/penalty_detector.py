from dataclasses import dataclass


@dataclass(frozen=True)
class PenaltyEvent:
    car_idx: int
    driver_name: str
    car_number: str
    event_type: str
    reason: str
    message: str
    priority: int = 9


class PenaltyDetector:
    """Broadcast only race-relevant penalties and damage flags.

    Generic black flags can be noisy in iRacing, especially under caution.
    This detector only airs:
    - black flags with a known pit-speeding reason
    - black flags with a known jumped-start/restart reason
    - repair/meatball flags, because that usually means major damage
    """

    BLACK_FLAG = 0x00010000
    REPAIR_FLAG = 0x00100000

    def __init__(self):
        self.last_states = {}
        self.reported_keys = set()

    def analyze(
        self,
        results,
        driver_lookup,
        current_lap=0,
        car_idx_session_flags=None,
        penalty_reasons=None,
    ):
        events = []
        for car in results or []:
            car_idx = car.get("CarIdx")
            if car_idx is None:
                continue
            try:
                car_idx = int(car_idx)
            except Exception:
                continue

            flags = self.resolve_flags(car, car_idx_session_flags, car_idx)
            reason = self.resolve_reason(car, penalty_reasons, car_idx)
            previous_flags = self.last_states.get(car_idx, 0)
            self.last_states[car_idx] = flags

            new_black = self.has_flag(flags, self.BLACK_FLAG) and not self.has_flag(
                previous_flags,
                self.BLACK_FLAG,
            )
            new_repair = self.has_flag(flags, self.REPAIR_FLAG) and not self.has_flag(
                previous_flags,
                self.REPAIR_FLAG,
            )

            driver = driver_lookup.get(car_idx, {})
            name = driver.get("name", f"Car {car_idx}")
            number = driver.get("number", "?")

            if new_repair:
                event = self.build_meatball_event(car_idx, name, number, current_lap)
                if self.can_report(event):
                    events.append(event)

            if new_black and self.is_broadcast_black_flag_reason(reason):
                event = self.build_black_flag_event(
                    car_idx,
                    name,
                    number,
                    reason,
                    current_lap,
                )
                if self.can_report(event):
                    events.append(event)

        return events

    def build_black_flag_event(self, car_idx, name, number, reason, current_lap):
        normalized = self.normalize(reason)
        if self.is_pit_speeding_reason(normalized):
            detail = "for speeding on pit road"
        elif self.is_jump_start_reason(normalized):
            detail = "for jumping the start or restart"
        else:
            detail = "for a race-control penalty"
        return PenaltyEvent(
            car_idx=car_idx,
            driver_name=name,
            car_number=number,
            event_type="black_flag",
            reason=detail,
            message=(
                f"Race control has shown the black flag to {name} in the "
                f"number {number} {detail}."
            ),
            priority=8,
        )

    def build_meatball_event(self, car_idx, name, number, current_lap):
        return PenaltyEvent(
            car_idx=car_idx,
            driver_name=name,
            car_number=number,
            event_type="meatball",
            reason="required repairs",
            message=(
                f"Race control is calling {name} in the number {number} "
                "to pit road for required damage repairs. Hopefully the crew "
                "can get that car fixed up and keep their race from ending early."
            ),
            priority=10,
        )

    def can_report(self, event):
        key = (event.event_type, event.car_idx)
        if key in self.reported_keys:
            return False
        self.reported_keys.add(key)
        return True

    def resolve_flags(self, car, car_idx_session_flags, car_idx):
        for key in (
            "SessionFlags",
            "CarIdxSessionFlags",
            "Flags",
            "PenaltyFlags",
            "CarFlags",
        ):
            value = car.get(key)
            if value is not None:
                return self.safe_int(value)
        try:
            return self.safe_int(car_idx_session_flags[car_idx])
        except Exception:
            return 0

    def resolve_reason(self, car, penalty_reasons, car_idx):
        for key in (
            "PenaltyReason",
            "Penalty",
            "BlackFlagReason",
            "Reason",
            "Status",
        ):
            value = car.get(key)
            if value:
                return str(value)
        try:
            value = penalty_reasons[car_idx]
            return str(value or "")
        except Exception:
            return ""

    def is_broadcast_black_flag_reason(self, reason):
        normalized = self.normalize(reason)
        return self.is_pit_speeding_reason(normalized) or self.is_jump_start_reason(
            normalized
        )

    @staticmethod
    def is_pit_speeding_reason(normalized):
        return "speed" in normalized and ("pit" in normalized or "pitroad" in normalized)

    @staticmethod
    def is_jump_start_reason(normalized):
        return (
            ("jump" in normalized or "start" in normalized)
            and ("start" in normalized or "restart" in normalized or "green" in normalized)
        )

    @staticmethod
    def has_flag(flags, bit):
        try:
            return bool(int(flags or 0) & int(bit))
        except Exception:
            return False

    @staticmethod
    def safe_int(value):
        try:
            return int(value)
        except Exception:
            return 0

    @staticmethod
    def normalize(value):
        text = str(value or "").lower()
        return "".join(char if char.isalnum() else " " for char in text)
