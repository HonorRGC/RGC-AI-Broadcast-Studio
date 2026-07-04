from enum import Enum

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
    GREEN_FLAG = 0x00000004
    YELLOW_FLAG = 0x00000008
    YELLOW_WAVING = 0x00000100
    ONE_LAP_TO_GREEN = 0x00000200
    CAUTION = 0x00004000
    CAUTION_WAVING = 0x00008000
    START_READY = 0x20000000
    START_SET = 0x40000000
    START_GO = 0x80000000
    SESSION_STATE_CHECKERED = 5
    SESSION_STATE_COOL_DOWN = 6

    def __init__(self):
        self.reset()

    def reset(self):
        self.phase = RacePhase.UNKNOWN
        self.previous_phase = RacePhase.UNKNOWN
        self.phase_changed = False
        self.race_started = False

        self.formation_announced = False
        self.yellow_announced = False
        self.one_to_green_announced = False

        self.ten_to_go_announced = False
        self.five_to_go_announced = False
        self.white_flag_announced = False
        self.checkered_announced = False
        self.progress_milestones_announced = set()
        self.last_results = []
        self.last_driver_lookup = {}

    def update(self, telemetry, results, driver_lookup, scheduler):
        self.phase_changed = False
        session_flags = telemetry.get_session_flags()
        state_reader = getattr(telemetry, "get_session_state", None)
        session_state = state_reader() if state_reader else 0
        total_laps = telemetry.get_total_laps()
        current_lap = self.get_best_race_lap(telemetry.get_lap(), results)
        track_info = telemetry.get_track_info()

        if results:
            self.last_results = list(results)
        if driver_lookup:
            self.last_driver_lookup = dict(driver_lookup)

        effective_results = results or self.last_results
        effective_driver_lookup = driver_lookup or self.last_driver_lookup

        new_phase = self.detect_phase(
            session_flags,
            effective_results,
            current_lap,
            total_laps,
            session_state=session_state,
        )

        if new_phase != RacePhase.CHECKERED:
            self.handle_lap_calls(current_lap, total_laps, scheduler)

        if new_phase != self.phase:
            self.phase_changed = True
            self.previous_phase = self.phase
            self.phase = new_phase
            self.handle_phase_change(
                effective_results,
                effective_driver_lookup,
                scheduler,
                track_info,
            )

        if new_phase == RacePhase.GREEN:
            self.race_started = True

    def detect_phase(
        self,
        session_flags,
        results,
        current_lap,
        total_laps,
        session_state=0,
    ):
        if self.safe_int(session_state) in (
            self.SESSION_STATE_CHECKERED,
            self.SESSION_STATE_COOL_DOWN,
        ):
            return RacePhase.CHECKERED

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

        if self.has_flag(session_flags, self.GREEN_FLAG) or self.has_flag(session_flags, self.START_GO):
            return RacePhase.GREEN

        if current_lap > 0:
            return RacePhase.GREEN

        if self.race_started:
            return RacePhase.GREEN

        if self.has_flag(session_flags, self.START_READY) or self.has_flag(session_flags, self.START_SET):
            return RacePhase.FORMATION

        if results:
            return RacePhase.FORMATION

        return RacePhase.UNKNOWN

    def handle_phase_change(self, results, driver_lookup, scheduler, track_info):
        if self.phase == RacePhase.FORMATION:
            self.handle_formation(scheduler)

        elif self.phase == RacePhase.GREEN:
            self.handle_green_flag(scheduler, track_info)

        elif self.phase == RacePhase.CAUTION:
            self.handle_caution(scheduler, track_info)

        elif self.phase == RacePhase.ONE_TO_GREEN:
            self.handle_one_to_green(results, driver_lookup, scheduler, track_info)

        elif self.phase == RacePhase.CHECKERED:
            self.handle_checkered(results, driver_lookup, scheduler, track_info)

    def handle_formation(self, scheduler):
        if self.formation_announced:
            return

        scheduler.add(
            "The field is rolling away for the parade laps as the drivers get ready for the start.",
            priority=10,
            category="race_control",
            protected=False,
            speaker="lead",
            expires_after=45,
            dedupe_key="race_control:formation",
        )
        self.formation_announced = True

    def handle_green_flag(self, scheduler, track_info):
        scheduler.clear_for_race_control()
        track_name = self.get_track_name(track_info)

        if self.race_started and self.previous_phase in [RacePhase.CAUTION, RacePhase.ONE_TO_GREEN]:
            message = f"Green flag is back in the air! We are racing again at {track_name}!"
        else:
            message = f"Green flag is in the air! We are racing at {track_name}!"

        scheduler.add(
            message,
            priority=12,
            category="race_control",
            protected=True,
            speaker="lead",
            expires_after=30,
            dedupe_key=f"race_control:green:{self.previous_phase.value}",
        )

        self.yellow_announced = False
        self.one_to_green_announced = False

    def handle_caution(self, scheduler, track_info):
        scheduler.clear_for_race_control()

        if self.yellow_announced:
            return

        track_name = self.get_track_name(track_info)

        scheduler.add(
            f"Trouble on the speedway — caution is out here at {track_name}. We'll have to see what brought this yellow flag out.",
            priority=12,
            category="race_control",
            protected=True,
            speaker="lead",
            expires_after=30,
            dedupe_key="race_control:caution",
        )

        self.yellow_announced = True
        self.one_to_green_announced = False

    def handle_one_to_green(self, results, driver_lookup, scheduler, track_info):
        if self.one_to_green_announced:
            return

        track_name = self.get_track_name(track_info)

        if self.race_started:
            scheduler.clear_for_race_control(
                preserve_categories=("caution_pit_summary", "sponsor_read")
            )
            message = (
                f"One lap to green here at {track_name}. "
                "The field is doubling up for the restart."
            )
            dedupe_key = "race_control:one_to_green:restart"
            priority = 11
            protected = True
        else:
            message = (
                f"One pace lap remains before the green flag here at {track_name}. "
                "The field is getting set for the start."
            )
            dedupe_key = "race_control:one_to_green:initial"
            priority = 8
            protected = False

        scheduler.add(
            message,
            priority=priority,
            category="race_control",
            protected=protected,
            speaker="lead",
            expires_after=45,
            dedupe_key=dedupe_key,
        )

        self.one_to_green_announced = True

    def handle_checkered(self, results, driver_lookup, scheduler, track_info):
        scheduler.clear_for_race_control()

        if self.checkered_announced:
            return

        winner = self.get_winner(results, driver_lookup)
        track_name = self.get_track_name(track_info)

        if winner:
            message = f"Checkered flag is out! {winner} wins at {track_name}!"
        else:
            message = f"Checkered flag is out. This race is complete at {track_name}."

        scheduler.add(
            message,
            priority=12,
            category="race_control",
            protected=True,
            speaker="lead",
            expires_after=60,
            dedupe_key="race_control:checkered",
        )

        scheduler.add(
            self.build_finish_rundown(results, driver_lookup, max_cars=10),
            priority=9,
            category="post_race",
            protected=True,
            speaker="lead",
            expires_after=180,
            dedupe_key="post_race:finish_rundown",
        )

        scheduler.add(
            self.build_signoff(track_name),
            priority=7,
            category="post_race_signoff",
            protected=True,
            speaker="lead",
            expires_after=240,
            dedupe_key="post_race:signoff",
        )

        self.checkered_announced = True

    def handle_lap_calls(self, current_lap, total_laps, scheduler):
        if not self.race_started or total_laps <= 0 or current_lap <= 0:
            return

        laps_to_go = total_laps - current_lap

        self.handle_progress_milestone(
            current_lap,
            total_laps,
            laps_to_go,
            scheduler,
        )

        if (
            total_laps > 10
            and 5 < laps_to_go <= 10
            and not self.ten_to_go_announced
        ):
            scheduler.add(
                f"{laps_to_go} laps to go. The closing stage of this race is underway.",
                priority=9,
                category="race_control",
                protected=True,
                speaker="lead",
            )
            self.ten_to_go_announced = True

        if total_laps > 5 and 1 < laps_to_go <= 5 and not self.five_to_go_announced:
            scheduler.add(
                f"{laps_to_go} laps to go. The pressure is about to ramp up.",
                priority=9,
                category="race_control",
                protected=True,
                speaker="lead",
            )
            self.five_to_go_announced = True

        if laps_to_go == 1 and not self.white_flag_announced:
            scheduler.add(
                "White flag is in the air. One lap to go.",
                priority=10,
                category="race_control",
                protected=True,
                speaker="lead",
            )
            self.white_flag_announced = True

    def handle_progress_milestone(
        self,
        current_lap,
        total_laps,
        laps_to_go,
        scheduler,
    ):
        if total_laps < 20:
            return

        milestones = [
            ("quarter", max(1, round(total_laps * 0.25))),
            ("halfway", max(1, round(total_laps * 0.50))),
            ("three_quarter", max(1, round(total_laps * 0.75))),
        ]
        reached = [item for item in milestones if current_lap >= item[1]]
        if not reached:
            return

        latest_name, _ = reached[-1]
        if latest_name in self.progress_milestones_announced:
            return
        if laps_to_go <= 10:
            return

        messages = {
            "quarter": (
                f"{laps_to_go} laps remain. We are one quarter of the way "
                "through this race."
            ),
            "halfway": (
                f"Halfway at the stripe. {laps_to_go} laps remain in this race."
            ),
            "three_quarter": (
                f"{laps_to_go} laps to go as we enter the final quarter of the race."
            ),
        }
        scheduler.add(
            messages[latest_name],
            priority=9,
            category="race_progress",
            protected=True,
            speaker="lead",
            expires_after=45,
            dedupe_key=f"race_progress:{latest_name}",
        )
        self.progress_milestones_announced.add(latest_name)

    def get_track_name(self, track_info):
        if not track_info:
            return "the speedway"
        return track_info.get("track_name", "the speedway") or "the speedway"

    def get_winner(self, results, driver_lookup):
        if not results:
            return ""

        try:
            leader = sorted(results, key=lambda car: int(car.get("Position", 999)))[0]
        except Exception:
            return ""

        car_idx = leader.get("CarIdx")
        driver_info = driver_lookup.get(car_idx, {})
        number = driver_info.get("number", "?")
        name = driver_info.get("name", f"Car {car_idx}")

        return f"the {number} of {name}"

    def build_finish_rundown(self, results, driver_lookup, max_cars=10):
        if not results:
            return "Official finishing results are not available yet."

        lines = ["Here is how they finished."]

        for car in self.sort_results(results)[:max_cars]:
            lines.append(self.format_driver_position(car, driver_lookup))

        return " ".join(lines)

    def build_signoff(self, track_name):
        return (
            f"That will do it tonight from {track_name}. "
            "For Jeff and Sarah, I am Mike with RGC AI Broadcast. "
            "Thank you for watching, and we will see you next time."
        )

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
        try:
            return int(raw_position)
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
        return any(car.get("Position") == 0 for car in results)

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

    def safe_int(self, value, default=0):
        try:
            return int(value)
        except (TypeError, ValueError):
            return default
