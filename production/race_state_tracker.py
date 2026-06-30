from dataclasses import dataclass
from enum import Enum


class RaceMoment(Enum):
    UNKNOWN = "UNKNOWN"
    PRE_RACE = "PRE_RACE"
    PARADE_LAP = "PARADE_LAP"
    GREEN = "GREEN"
    LONG_GREEN_RUN = "LONG_GREEN_RUN"
    CAUTION = "CAUTION"
    RESTART = "RESTART"
    CLOSING_LAPS = "CLOSING_LAPS"
    OVERTIME = "OVERTIME"
    WHITE_FLAG = "WHITE_FLAG"
    CHECKERED = "CHECKERED"


@dataclass
class RaceState:
    moment: RaceMoment = RaceMoment.UNKNOWN
    current_lap: int = 0
    total_laps: int = 0
    laps_remaining: int = 0

    green_lap_count: int = 0
    caution_count: int = 0
    restart_count: int = 0

    is_green: bool = False
    is_caution: bool = False
    is_late_race: bool = False
    is_overtime: bool = False

    def can_call_race(self):
        return self.moment in [
            RaceMoment.GREEN,
            RaceMoment.LONG_GREEN_RUN,
            RaceMoment.CLOSING_LAPS,
            RaceMoment.OVERTIME,
            RaceMoment.WHITE_FLAG,
        ]


class RaceStateTracker:
    def __init__(self):
        self.state = RaceState()
        self.last_was_caution = False
        self.last_lap = 0

    def update(self, current_lap=0, total_laps=0, session_flags=0):
        current_lap = self.safe_int(current_lap)
        total_laps = self.safe_int(total_laps)

        is_caution = self.is_caution_flag(session_flags)
        is_green = not is_caution and current_lap > 0

        laps_remaining = max(total_laps - current_lap, 0) if total_laps > 0 else 0
        is_overtime = total_laps > 0 and current_lap > total_laps
        is_late_race = total_laps > 0 and laps_remaining <= 10

        if is_caution and not self.last_was_caution:
            self.state.caution_count += 1

        if self.last_was_caution and is_green:
            self.state.restart_count += 1
            self.state.green_lap_count = 0

        if is_green:
            self.state.green_lap_count += 1

        self.state.moment = self.determine_moment(
            current_lap,
            total_laps,
            laps_remaining,
            is_green,
            is_caution,
            is_late_race,
            is_overtime,
        )

        self.state.current_lap = current_lap
        self.state.total_laps = total_laps
        self.state.laps_remaining = laps_remaining
        self.state.is_green = is_green
        self.state.is_caution = is_caution
        self.state.is_late_race = is_late_race
        self.state.is_overtime = is_overtime

        self.last_was_caution = is_caution
        self.last_lap = current_lap

        return self.state

    def determine_moment(
        self,
        current_lap,
        total_laps,
        laps_remaining,
        is_green,
        is_caution,
        is_late_race,
        is_overtime,
    ):
        if is_caution:
            return RaceMoment.CAUTION

        if current_lap <= 0:
            return RaceMoment.PRE_RACE

        if is_overtime:
            return RaceMoment.OVERTIME

        if total_laps > 0 and current_lap >= total_laps:
            return RaceMoment.CHECKERED

        if total_laps > 0 and laps_remaining == 1:
            return RaceMoment.WHITE_FLAG

        if is_late_race:
            return RaceMoment.CLOSING_LAPS

        if is_green and self.state.green_lap_count >= 10:
            return RaceMoment.LONG_GREEN_RUN

        if is_green:
            return RaceMoment.GREEN

        return RaceMoment.UNKNOWN

    def is_caution_flag(self, session_flags):
        try:
            flags = int(session_flags)
        except Exception:
            return False

        caution_bits = [
            0x00000008,
            0x00000100,
            0x00004000,
            0x00008000,
        ]

        return any(flags & bit for bit in caution_bits)

    def get_state(self):
        return self.state

    def safe_int(self, value):
        try:
            return int(value)
        except Exception:
            return 0