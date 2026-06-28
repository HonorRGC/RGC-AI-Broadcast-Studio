import time
from dataclasses import dataclass
from typing import Dict, List


@dataclass
class IncidentEvent:
    event_type: str
    driver_name: str
    car_number: str
    car_idx: int
    message: str
    importance: int
    lap: int = 0
    incident_delta: int = 0
    total_incidents: int = 0
    trouble_type: str = ""


@dataclass
class IncidentDriverState:
    driver_name: str
    car_number: str
    car_idx: int

    last_incident_count: int = 0
    last_position: int = 0
    last_lap_dist_pct: float = 0.0
    last_est_time: float = 0.0
    last_on_pit_road: bool = False

    last_reported_at: float = 0.0
    initialized: bool = False


class IncidentDetector:
    """
    Detects race trouble, not just official incident points.

    This version watches:
    - official incident changes when available
    - sudden position loss
    - sudden lap distance loss
    - abnormal estimated-time loss
    - off-track / abnormal surface
    """

    def __init__(self):
        self.driver_states: Dict[int, IncidentDriverState] = {}

        self.report_cooldown_seconds = 25
        self.debug = False

        self.position_loss_threshold = 4
        self.lap_distance_loss_threshold = 0.025
        self.est_time_loss_threshold = 4.0

    def analyze(
        self,
        results,
        driver_lookup,
        current_lap=0,
        track_surface_status=None,
        track_surface_material_status=None,
        lap_dist_pct_status=None,
        est_time_status=None,
        pit_road_status=None,
    ) -> List[IncidentEvent]:
        events = []

        if not results:
            return events

        for car in results:
            car_idx = car.get("CarIdx")

            if car_idx is None:
                continue

            driver_info = driver_lookup.get(car_idx, {})
            driver_name = driver_info.get("name", f"Car {car_idx}")
            car_number = driver_info.get("number", "?")

            position = self.safe_int(car.get("Position", 0))
            incident_count = self.safe_int(car.get("Incidents", 0))

            lap_dist_pct = self.get_array_value(
                lap_dist_pct_status,
                car_idx,
                self.safe_float(car.get("Lap", 0)),
            )

            est_time = self.get_array_value(
                est_time_status,
                car_idx,
                self.safe_float(car.get("Time", 0)),
            )

            on_pit_road = self.get_array_bool(pit_road_status, car_idx)

            track_surface = self.get_array_value(track_surface_status, car_idx, None)
            track_surface_material = self.get_array_value(
                track_surface_material_status,
                car_idx,
                None,
            )

            state = self.get_or_create_state(
                car_idx=car_idx,
                driver_name=driver_name,
                car_number=car_number,
            )

            if not state.initialized:
                self.update_state(
                    state,
                    incident_count,
                    position,
                    lap_dist_pct,
                    est_time,
                    on_pit_road,
                )
                state.initialized = True
                continue

            if on_pit_road:
                self.update_state(
                    state,
                    incident_count,
                    position,
                    lap_dist_pct,
                    est_time,
                    on_pit_road,
                )
                continue

            event = self.detect_trouble(
                state=state,
                incident_count=incident_count,
                position=position,
                lap_dist_pct=lap_dist_pct,
                est_time=est_time,
                track_surface=track_surface,
                track_surface_material=track_surface_material,
                current_lap=current_lap,
            )

            if event and self.can_report(state):
                events.append(event)
                state.last_reported_at = time.time()

            self.update_state(
                state,
                incident_count,
                position,
                lap_dist_pct,
                est_time,
                on_pit_road,
            )

        return events

    def detect_trouble(
        self,
        state,
        incident_count,
        position,
        lap_dist_pct,
        est_time,
        track_surface,
        track_surface_material,
        current_lap,
    ):
        incident_delta = incident_count - state.last_incident_count
        position_loss = position - state.last_position
        lap_distance_loss = state.last_lap_dist_pct - lap_dist_pct
        est_time_loss = est_time - state.last_est_time

        if incident_delta >= 4:
            return self.build_event(
                state,
                "major incident",
                f"Trouble for {state.driver_name}. The number {state.car_number} has picked up a {incident_delta}x incident.",
                10,
                current_lap,
                incident_delta,
                incident_count,
            )

        if incident_delta >= 2:
            return self.build_event(
                state,
                "incident points",
                f"{state.driver_name} has picked up a {incident_delta}x incident. That could mean contact or a mistake somewhere on track.",
                8,
                current_lap,
                incident_delta,
                incident_count,
            )

        if position_loss >= self.position_loss_threshold:
            return self.build_event(
                state,
                "position loss",
                f"Something has happened to {state.driver_name}. The number {state.car_number} has suddenly dropped several positions.",
                9,
                current_lap,
                incident_delta,
                incident_count,
            )

        if lap_distance_loss >= self.lap_distance_loss_threshold:
            return self.build_event(
                state,
                "lost ground",
                f"{state.driver_name} has lost a lot of ground in a hurry. That may be trouble for the number {state.car_number}.",
                8,
                current_lap,
                incident_delta,
                incident_count,
            )

        if est_time_loss >= self.est_time_loss_threshold:
            return self.build_event(
                state,
                "slow car",
                f"{state.driver_name} is suddenly off the pace. There may be a problem with the number {state.car_number}.",
                8,
                current_lap,
                incident_delta,
                incident_count,
            )

        if self.is_abnormal_surface(track_surface):
            return self.build_event(
                state,
                "off track",
                f"{state.driver_name} is off the racing surface. Trouble for the number {state.car_number}.",
                7,
                current_lap,
                incident_delta,
                incident_count,
            )

        return None

    def build_event(
        self,
        state,
        trouble_type,
        message,
        importance,
        current_lap,
        incident_delta,
        incident_count,
    ):
        return IncidentEvent(
            event_type="INCIDENT",
            driver_name=state.driver_name,
            car_number=state.car_number,
            car_idx=state.car_idx,
            message=message,
            importance=importance,
            lap=current_lap,
            incident_delta=incident_delta,
            total_incidents=incident_count,
            trouble_type=trouble_type,
        )

    def update_state(
        self,
        state,
        incident_count,
        position,
        lap_dist_pct,
        est_time,
        on_pit_road,
    ):
        state.last_incident_count = incident_count
        state.last_position = position
        state.last_lap_dist_pct = lap_dist_pct
        state.last_est_time = est_time
        state.last_on_pit_road = on_pit_road

    def get_or_create_state(self, car_idx, driver_name, car_number):
        if car_idx not in self.driver_states:
            self.driver_states[car_idx] = IncidentDriverState(
                driver_name=driver_name,
                car_number=car_number,
                car_idx=car_idx,
            )

        state = self.driver_states[car_idx]
        state.driver_name = driver_name
        state.car_number = car_number

        return state

    def is_abnormal_surface(self, track_surface):
        if track_surface is None:
            return False

        try:
            surface = int(track_surface)
        except Exception:
            return False

        # iRacing surface values vary by context, so keep this conservative.
        # Values 0 or negative often indicate not on racing surface / invalid.
        return surface <= 0

    def can_report(self, state):
        return time.time() - state.last_reported_at >= self.report_cooldown_seconds

    def get_array_value(self, values, index, default):
        try:
            if values is None:
                return default
            return values[int(index)]
        except Exception:
            return default

    def get_array_bool(self, values, index):
        try:
            if values is None:
                return False
            return bool(values[int(index)])
        except Exception:
            return False

    def safe_int(self, value):
        try:
            return int(value)
        except Exception:
            return 0

    def safe_float(self, value):
        try:
            return float(value)
        except Exception:
            return 0.0