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
    ) -> List[PitStrategyEvent]:
        events = []

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

            if not state.initialized:
                state.initialized = True
                if on_pit_road and not under_caution and current_lap <= 1:
                    state.started_from_pit_road = True
                    event = self.build_pit_road_start_event(
                        state=state,
                        current_lap=current_lap,
                    )
                    if event and self.can_report(state):
                        events.append(event)
                        state.last_reported_at = time.time()
                    state.last_pit_lap = current_lap

                state.on_pit_road = on_pit_road
                continue

            if on_pit_road and not state.on_pit_road:
                state.pit_entry_position = current_position
                event = self.build_pit_entry_event(
                    state=state,
                    current_lap=current_lap,
                    under_caution=under_caution,
                )

                if event and self.can_report(state):
                    events.append(event)
                    state.last_reported_at = time.time()

                state.last_pit_lap = current_lap

            state.on_pit_road = on_pit_road

        return events

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
