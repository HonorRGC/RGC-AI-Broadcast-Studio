import time
from dataclasses import dataclass
from typing import Dict, List


@dataclass
class PitStrategyEvent:
    event_type: str
    driver_name: str
    car_number: str
    car_idx: int
    message: str
    importance: int
    lap: int = 0
    under_caution: bool = False


@dataclass
class PitDriverState:
    driver_name: str
    car_number: str
    car_idx: int
    on_pit_road: bool = False
    last_pit_lap: int = 0
    pit_entry_position: int = 0
    pit_entry_time: float = 0.0
    last_pit_lane_seconds: float = 0.0
    current_pit_lane_seconds: float = 0.0
    last_pit_stop_seconds: float = 0.0
    current_pit_stop_seconds: float = 0.0
    previous_pit_update_time: float = 0.0
    previous_lap_dist_pct: float | None = None
    last_reported_at: float = 0.0
    initialized: bool = False
    started_from_pit_road: bool = False


class PitStrategyDetector:
    def __init__(self):
        self.driver_states: Dict[int, PitDriverState] = {}
        self.report_cooldown_seconds = 20

    def analyze(
        self,
        results,
        driver_lookup,
        pit_road_status,
        current_lap=0,
        under_caution=False,
        session_time=None,
        lap_dist_pct=None,
    ) -> List[PitStrategyEvent]:
        events = []
        session_time = self.safe_float(session_time, time.time())

        if not results:
            return events

        for car in results:
            car_idx = car.get("CarIdx")

            if car_idx is None:
                continue
            current_position = self.safe_int(car.get("Position", 0))

            driver_info = driver_lookup.get(car_idx, {})
            driver_name = driver_info.get("name", f"Car {car_idx}")
            car_number = driver_info.get("number", "?")

            state = self.get_or_create_state(
                car_idx=car_idx,
                driver_name=driver_name,
                car_number=car_number,
            )

            on_pit_road = self.is_car_on_pit_road(car_idx, pit_road_status)
            lap_pct = self.array_value(lap_dist_pct, car_idx)

            if not state.initialized:
                state.initialized = True
                if on_pit_road and not under_caution and current_lap <= 1:
                    state.started_from_pit_road = True
                    self.start_pit_timer(state, session_time, current_position, lap_pct)
                    event = self.build_pit_road_start_event(
                        state=state,
                        current_lap=current_lap,
                    )
                    if event and self.can_report(state):
                        events.append(event)
                        state.last_reported_at = time.time()
                    state.last_pit_lap = current_lap

                state.on_pit_road = on_pit_road
                if on_pit_road:
                    self.update_pit_timer(state, session_time, lap_pct)
                continue

            if on_pit_road and not state.on_pit_road:
                self.start_pit_timer(state, session_time, current_position, lap_pct)
                event = self.build_pit_entry_event(
                    state=state,
                    current_lap=current_lap,
                    under_caution=under_caution,
                )

                if event and self.can_report(state):
                    events.append(event)
                    state.last_reported_at = time.time()

                state.last_pit_lap = current_lap
            elif on_pit_road:
                self.update_pit_timer(state, session_time, lap_pct)
            elif state.on_pit_road and not on_pit_road:
                self.finish_pit_timer(state, session_time)
                event = self.build_pit_exit_event(
                    state=state,
                    current_lap=current_lap,
                    under_caution=under_caution,
                )
                if event and (self.can_report(state) or event.event_type == "PIT_STOP_COMPLETE"):
                    events.append(event)
                    state.last_reported_at = time.time()

            state.on_pit_road = on_pit_road

        return events

    def start_pit_timer(self, state, session_time, current_position, lap_pct):
        state.pit_entry_position = current_position
        state.pit_entry_time = session_time
        state.current_pit_lane_seconds = 0.0
        state.current_pit_stop_seconds = 0.0
        state.previous_pit_update_time = session_time
        state.previous_lap_dist_pct = self.safe_float_or_none(lap_pct)

    def update_pit_timer(self, state, session_time, lap_pct):
        if state.pit_entry_time <= 0:
            state.pit_entry_time = session_time
        state.current_pit_lane_seconds = max(session_time - state.pit_entry_time, 0.0)

        previous_time = state.previous_pit_update_time or session_time
        delta_seconds = max(session_time - previous_time, 0.0)
        current_lap_pct = self.safe_float_or_none(lap_pct)
        if delta_seconds > 0 and self.is_stationary_on_pit_road(
            state.previous_lap_dist_pct,
            current_lap_pct,
        ):
            state.current_pit_stop_seconds += delta_seconds

        state.previous_pit_update_time = session_time
        state.previous_lap_dist_pct = current_lap_pct

    def finish_pit_timer(self, state, session_time):
        if state.pit_entry_time > 0:
            state.current_pit_lane_seconds = max(session_time - state.pit_entry_time, 0.0)
        state.last_pit_lane_seconds = state.current_pit_lane_seconds
        state.last_pit_stop_seconds = state.current_pit_stop_seconds
        state.current_pit_lane_seconds = 0.0
        state.current_pit_stop_seconds = 0.0
        state.pit_entry_time = 0.0
        state.previous_pit_update_time = 0.0
        state.previous_lap_dist_pct = None

    @staticmethod
    def is_stationary_on_pit_road(previous_lap_pct, current_lap_pct):
        if previous_lap_pct is None or current_lap_pct is None:
            return False
        return abs(float(current_lap_pct) - float(previous_lap_pct)) < 0.00008

    def get_or_create_state(self, car_idx, driver_name, car_number):
        if car_idx not in self.driver_states:
            self.driver_states[car_idx] = PitDriverState(
                driver_name=driver_name,
                car_number=car_number,
                car_idx=car_idx,
            )

        state = self.driver_states[car_idx]
        state.driver_name = driver_name
        state.car_number = car_number

        return state

    def is_car_on_pit_road(self, car_idx, pit_road_status):
        try:
            return bool(pit_road_status[int(car_idx)])
        except Exception:
            return False

    def array_value(self, values, index):
        try:
            if values is None:
                return None
            return values[int(index)]
        except Exception:
            return None

    def build_pit_entry_event(self, state, current_lap, under_caution):
        if under_caution:
            message = (
                f"{state.driver_name} brings the number {state.car_number} to pit road under caution. "
                "That could be for service, damage repair, or a restart adjustment."
            )
            importance = 8
        else:
            message = (
                f"{state.driver_name} is on pit road under green. "
                "We'll watch whether that is scheduled service, damage repair, "
                "or an off-sequence stop."
            )
            importance = 9

        return PitStrategyEvent(
            event_type="PIT_STOP",
            driver_name=state.driver_name,
            car_number=state.car_number,
            car_idx=state.car_idx,
            message=message,
            importance=importance,
            lap=current_lap,
            under_caution=under_caution,
        )

    def build_pit_exit_event(self, state, current_lap, under_caution):
        stop_note = self.describe_completed_stop(state)
        if under_caution:
            message = (
                f"{state.driver_name} has completed the stop in the number {state.car_number}. "
                f"{stop_note}"
            )
            importance = 7
        else:
            message = (
                f"{state.driver_name} cycles off pit road in the number {state.car_number}. "
                f"{stop_note}"
            )
            importance = 8 if self.is_extended_repair_stop(state) else 7

        return PitStrategyEvent(
            event_type="PIT_STOP_COMPLETE",
            driver_name=state.driver_name,
            car_number=state.car_number,
            car_idx=state.car_idx,
            message=message,
            importance=importance,
            lap=current_lap,
            under_caution=under_caution,
        )

    def describe_completed_stop(self, state):
        lane_seconds = float(state.last_pit_lane_seconds or 0.0)
        stop_seconds = float(state.last_pit_stop_seconds or 0.0)
        timing = self.format_stop_timing(lane_seconds, stop_seconds)

        if self.is_extended_repair_stop(state):
            return (
                f"That was an extended stop{timing}, so damage repair is likely part "
                "of the story."
            )
        if stop_seconds >= 12.0:
            return (
                f"That looks like a full-service stop{timing}, likely tires, fuel, "
                "or a larger adjustment."
            )
        if stop_seconds >= 6.0:
            return (
                f"That was a normal service stop{timing}, enough time for tires, fuel, "
                "or a quick adjustment."
            )
        if lane_seconds > 0 and lane_seconds <= 20.0 and stop_seconds < 3.0:
            return (
                f"That was a very quick trip{timing}, more like a drive-through or "
                "track-position move than a full service stop."
            )
        return (
            f"That was a short stop{timing}, so track position may have mattered "
            "more than full service."
        )

    @staticmethod
    def is_extended_repair_stop(state):
        return (
            float(state.last_pit_stop_seconds or 0.0) >= 25.0
            or float(state.last_pit_lane_seconds or 0.0) >= 65.0
        )

    @staticmethod
    def format_stop_timing(lane_seconds, stop_seconds):
        parts = []
        if stop_seconds > 0:
            parts.append(f"about {round(stop_seconds)} seconds stationary")
        if lane_seconds > 0:
            parts.append(f"{round(lane_seconds)} seconds on pit road")
        if not parts:
            return ""
        if len(parts) == 1:
            return f", {parts[0]}"
        return f", {parts[0]} and {parts[1]}"

    def build_pit_road_start_event(self, state, current_lap):
        return PitStrategyEvent(
            event_type="PIT_ROAD_START",
            driver_name=state.driver_name,
            car_number=state.car_number,
            car_idx=state.car_idx,
            message=(
                f"{state.driver_name} in the number {state.car_number} is starting "
                "this race from pit road. That is usually because of a penalty, "
                "a setup issue, or a choice to stay out of early-race trouble."
            ),
            importance=8,
            lap=current_lap,
            under_caution=False,
        )

    def can_report(self, state):
        return time.time() - state.last_reported_at >= self.report_cooldown_seconds

    @staticmethod
    def safe_int(value, default=0):
        try:
            return int(value)
        except (TypeError, ValueError):
            return default

    @staticmethod
    def safe_float(value, default=0.0):
        try:
            return float(value)
        except (TypeError, ValueError):
            return default

    @staticmethod
    def safe_float_or_none(value):
        try:
            if value is None:
                return None
            return float(value)
        except (TypeError, ValueError):
            return None
