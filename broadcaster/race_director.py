from enum import Enum

from broadcaster.events import RaceEvent
from helpers.position_formatter import PositionFormatter


class RacePhase(Enum):
    UNKNOWN = "UNKNOWN"
    FORMATION = "FORMATION"
    GREEN = "GREEN"
    CAUTION = "CAUTION"
    ONE_TO_GREEN = "ONE_TO_GREEN"
    CHECKERED = "CHECKERED"


class RaceDirector:
    CHECKERED_FLAG = 0x00000001
    WHITE_FLAG = 0x00000002
    GREEN_FLAG = 0x00000010
    YELLOW_FLAG = 0x00000008
    YELLOW_WAVING = 0x00000100
    ONE_LAP_TO_GREEN = 0x00000200
    CAUTION = 0x00004000
    CAUTION_WAVING = 0x00008000
    START_READY = 0x20000000
    START_SET = 0x40000000
    START_GO = 0x80000000

    def __init__(self):
        self.phase = RacePhase.UNKNOWN
        self.previous_phase = RacePhase.UNKNOWN

        self.formation_announced = False
        self.yellow_announced = False
        self.one_to_green_announced = False

        self.ten_to_go_announced = False
        self.five_to_go_announced = False
        self.white_flag_announced = False
        self.checkered_announced = False

    def update(self, telemetry, results, driver_lookup, scheduler):
        session_flags = telemetry.get_session_flags()
        total_laps = telemetry.get_total_laps()
        current_lap = self.get_best_race_lap(telemetry.get_lap(), results)

        new_phase = self.detect_phase(session_flags, results, current_lap, total_laps)

        if new_phase != RacePhase.CHECKERED:
            self.handle_lap_calls(current_lap, total_laps, scheduler)

        if new_phase != self.phase:
            self.previous_phase = self.phase
            self.phase = new_phase
            self.handle_phase_change(results, driver_lookup, scheduler)

    def is_race_over(self):
        return self.phase == RacePhase.CHECKERED

    def detect_phase(self, session_flags, results, current_lap, total_laps):
        if self.has_flag(session_flags, self.CHECKERED_FLAG):
            return RacePhase.CHECKERED

        if total_laps > 0 and current_lap >= total_laps:
            return RacePhase.CHECKERED

        if self.has_flag(session_flags, self.ONE_LAP_TO_GREEN):
            return RacePhase.ONE_TO_GREEN

        if self.has_flag(session_flags, self.CAUTION) or self.has_flag(session_flags, self.CAUTION_WAVING):
            return RacePhase.CAUTION

        if self.has_flag(session_flags, self.YELLOW_FLAG) or self.has_flag(session_flags, self.YELLOW_WAVING):
            return RacePhase.CAUTION

        if self.has_flag(session_flags, self.START_READY) or self.has_flag(session_flags, self.START_SET):
            return RacePhase.FORMATION

        if self.has_flag(session_flags, self.GREEN_FLAG) or self.has_flag(session_flags, self.START_GO):
            return RacePhase.GREEN

        if results:
            return RacePhase.GREEN

        return RacePhase.UNKNOWN

    def handle_lap_calls(self, current_lap, total_laps, scheduler):
        if total_laps <= 0 or current_lap <= 0:
            return

        laps_to_go = total_laps - current_lap

        if laps_to_go <= 10 and laps_to_go > 5 and not self.ten_to_go_announced:
            scheduler.add(
                f"{laps_to_go} laps to go. The closing stage of this race is underway.",
                priority=9,
                category="race_control",
                protected=True,
            )
            self.ten_to_go_announced = True

        if laps_to_go <= 5 and laps_to_go > 1 and not self.five_to_go_announced:
            scheduler.add(
                f"{laps_to_go} laps to go. The pressure is about to ramp up.",
                priority=9,
                category="race_control",
                protected=True,
            )
            self.five_to_go_announced = True

        if laps_to_go == 1 and not self.white_flag_announced:
            scheduler.add(
                "White flag is in the air. One lap to go.",
                priority=10,
                category="race_control",
                protected=True,
            )
            self.white_flag_announced = True

    def handle_phase_change(self, results, driver_lookup, scheduler):
        if self.phase == RacePhase.FORMATION:
            self.handle_formation(scheduler)

        elif self.phase == RacePhase.GREEN:
            self.handle_green_flag(scheduler)

        elif self.phase == RacePhase.CAUTION:
            self.handle_caution(scheduler)

        elif self.phase == RacePhase.ONE_TO_GREEN:
            self.handle_one_to_green(results, driver_lookup, scheduler)

        elif self.phase == RacePhase.CHECKERED:
            self.handle_checkered(results, driver_lookup, scheduler)

    def handle_formation(self, scheduler):
        if self.formation_announced:
            return

        scheduler.add(
            "The field is forming up. Drivers are getting ready for the start.",
            priority=9,
            category="race_control",
            protected=True,
        )
        self.formation_announced = True

    def handle_green_flag(self, scheduler):
        if self.previous_phase in [RacePhase.CAUTION, RacePhase.ONE_TO_GREEN]:
            message = "Green flag is back in the air. We are racing again."
        else:
            message = "Green flag is in the air. The race is underway."

        scheduler.add(
            message,
            priority=10,
            category="race_control",
            protected=True,
        )

        self.yellow_announced = False
        self.one_to_green_announced = False

    def handle_caution(self, scheduler):
        scheduler.clear_race_chatter()

        if self.yellow_announced:
            return

        scheduler.add(
            "Yellow flag is out. The caution is on the speedway.",
            priority=10,
            category="race_control",
            protected=True,
        )

        self.yellow_announced = True
        self.one_to_green_announced = False

    def handle_one_to_green(self, results, driver_lookup, scheduler):
        if self.one_to_green_announced:
            return

        scheduler.add(
            self.build_field_rundown(results, driver_lookup, max_cars=20),
            priority=10,
            category="restart_rundown",
            protected=True,
        )

        self.one_to_green_announced = True

    def handle_checkered(self, results, driver_lookup, scheduler):
        scheduler.clear_race_chatter()

        if self.checkered_announced:
            return

        scheduler.add(
            "Checkered flag is out. This race is complete.",
            priority=10,
            category="race_control",
            protected=True,
        )

        scheduler.add(
            self.build_finish_rundown(results, driver_lookup, max_cars=20),
            priority=9,
            category="post_race",
            protected=True,
        )

        self.checkered_announced = True

    def build_field_rundown(self, results, driver_lookup, max_cars=20):
        if not results:
            return "One lap to green. The field is doubling up for the restart."

        lines = ["One lap to green. Here's your restart rundown through the top twenty."]

        for car in self.sort_results(results)[:max_cars]:
            lines.append(self.format_driver_position(car, driver_lookup))

        return " ".join(lines)

    def build_finish_rundown(self, results, driver_lookup, max_cars=20):
        if not results:
            return "The race is over. Official finishing results are not available yet."

        lines = ["Here is how they finished."]

        for car in self.sort_results(results)[:max_cars]:
            lines.append(self.format_driver_position(car, driver_lookup))

        return " ".join(lines)

    def format_driver_position(self, car, driver_lookup):
        car_idx = car.get("CarIdx")
        position = self.get_display_position(car)

        driver_info = driver_lookup.get(car_idx, {})
        name = driver_info.get("name", f"Car {car_idx}")
        number = driver_info.get("number", "?")

        return f"{PositionFormatter.ordinal(position)}, the {number} of {name}."

    def sort_results(self, results):
        zero_based_positions = self.results_are_zero_based(results)

        return sorted(
            results,
            key=lambda car: self.display_position(
                car.get("Position", 999),
                zero_based_positions,
            ),
        )

    def get_display_position(self, car):
        raw_position = car.get("Position", 999)
        zero_based_positions = False

        try:
            position = int(raw_position)
            return position + 1 if zero_based_positions and position == 0 else position
        except Exception:
            return raw_position

    def get_best_race_lap(self, telemetry_lap, results):
        laps = []

        try:
            laps.append(int(telemetry_lap))
        except Exception:
            pass

        for car in results or []:
            for key in ["Lap", "LapsComplete"]:
                value = car.get(key)
                try:
                    laps.append(int(value))
                except Exception:
                    pass

        return max(laps) if laps else 0

    def results_are_zero_based(self, results):
        positions = []

        for car in results:
            position = car.get("Position")
            if position is not None:
                positions.append(position)

        return 0 in positions

    def display_position(self, raw_position, zero_based_positions):
        try:
            position = int(raw_position)
        except Exception:
            return raw_position

        if zero_based_positions:
            return position + 1

        return position

    def has_flag(self, session_flags, flag):
        try:
            return int(session_flags) & flag != 0
        except Exception:
            return False

    def package_event(self, event):
        if not isinstance(event, RaceEvent):
            return None

        if self.phase in [
            RacePhase.CAUTION,
            RacePhase.ONE_TO_GREEN,
            RacePhase.CHECKERED,
        ]:
            return None

        return event