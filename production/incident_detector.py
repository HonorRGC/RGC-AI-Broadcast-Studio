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
    replay_session_time: float | None = None
    replay_confidence: str = ""


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


@dataclass
class CautionCandidate:
    driver_name: str
    car_number: str
    car_idx: int
    score: float
    lap: int
    observed_at: float
    session_time: float | None = None
    signal_count: int = 0
    reasons: tuple[str, ...] = ()


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
        self.pack_report_cooldown_seconds = 45
        self.last_pack_reported_at = 0.0
        self.debug = False

        self.position_loss_threshold = 4
        self.lap_distance_loss_threshold = 0.025
        self.est_time_loss_threshold = 4.0
        self.recent_caution_candidates: List[CautionCandidate] = []

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
        session_time=None,
        suppress_soft_events=False,
    ) -> List[IncidentEvent]:
        events = []
        pack_candidates = []

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
                suppress_soft_events=suppress_soft_events,
            )
            pack_candidate = self.build_pack_trouble_candidate(
                state=state,
                incident_count=incident_count,
                position=position,
                lap_dist_pct=lap_dist_pct,
                est_time=est_time,
                track_surface=track_surface,
                current_lap=current_lap,
                session_time=session_time,
            )
            if pack_candidate:
                pack_candidates.append(pack_candidate)

            self.remember_caution_candidate(
                state=state,
                incident_count=incident_count,
                position=position,
                lap_dist_pct=lap_dist_pct,
                est_time=est_time,
                track_surface=track_surface,
                current_lap=current_lap,
                session_time=session_time,
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

        pack_event = self.build_pack_wreck_event(pack_candidates, current_lap)
        if pack_event:
            return [pack_event]

        return events

    def build_caution_fallback(self, current_lap, max_age_seconds=8.0):
        now = time.time()
        candidates = [
            candidate
            for candidate in self.recent_caution_candidates
            if now - candidate.observed_at <= max_age_seconds
            and abs(current_lap - candidate.lap) <= 1
        ]
        self.recent_caution_candidates = candidates
        if not candidates:
            return None

        candidate = max(candidates, key=lambda item: item.score)
        if candidate.score < 3.0:
            return None

        high_confidence = (
            candidate.session_time is not None
            and candidate.score >= 8.0
            and candidate.signal_count >= 2
        )

        self.recent_caution_candidates = []
        return IncidentEvent(
            event_type="INCIDENT",
            driver_name=candidate.driver_name,
            car_number=candidate.car_number,
            car_idx=candidate.car_idx,
            message=(
                "We may have found the reason for the caution. "
                f"{candidate.driver_name} in the number {candidate.car_number} "
                "showed the clearest sign of trouble as the yellow came out."
            ),
            importance=9,
            lap=current_lap,
            trouble_type="caution candidate",
            replay_session_time=candidate.session_time if high_confidence else None,
            replay_confidence="high" if high_confidence else "low",
        )

    def build_big_wreck_fallback(
        self,
        current_lap,
        max_age_seconds=8.0,
        minimum_cars=4,
    ):
        now = time.time()
        candidates = [
            candidate
            for candidate in self.recent_caution_candidates
            if now - candidate.observed_at <= max_age_seconds
            and abs(current_lap - candidate.lap) <= 1
            and candidate.score >= 3.0
        ]
        if len(candidates) < minimum_cars:
            return None

        candidates.sort(key=lambda item: item.score, reverse=True)
        return self.build_pack_wreck_event(
            candidates[:8],
            current_lap=current_lap,
            force=True,
        )

    def remember_caution_candidate(
        self,
        state,
        incident_count,
        position,
        lap_dist_pct,
        est_time,
        track_surface,
        current_lap,
        session_time=None,
    ):
        incident_delta = max(0, incident_count - state.last_incident_count)
        position_loss = max(0, position - state.last_position)
        lap_distance_loss = self.calculate_lap_distance_loss(
            state.last_lap_dist_pct,
            lap_dist_pct,
        )
        est_time_loss = max(0.0, est_time - state.last_est_time)
        abnormal_surface = self.is_abnormal_surface(track_surface)
        reasons = []
        if incident_delta > 0:
            reasons.append("incident counter changed")
        if position_loss >= 2:
            reasons.append("lost positions")
        if lap_distance_loss >= 0.01:
            reasons.append("lost track position quickly")
        if est_time_loss >= 2.0:
            reasons.append("lost estimated time")
        if abnormal_surface:
            reasons.append("abnormal track surface")

        score = (
            incident_delta * 3.0
            + position_loss
            + lap_distance_loss * 100.0
            + est_time_loss
            + (4.0 if abnormal_surface else 0.0)
        )
        if score < 1.0:
            return

        self.recent_caution_candidates.append(
            CautionCandidate(
                driver_name=state.driver_name,
                car_number=state.car_number,
                car_idx=state.car_idx,
                score=score,
                lap=current_lap,
                observed_at=time.time(),
                session_time=self.safe_optional_float(session_time),
                signal_count=len(reasons),
                reasons=tuple(reasons),
            )
        )
        self.recent_caution_candidates = self.recent_caution_candidates[-30:]

    def build_pack_trouble_candidate(
        self,
        state,
        incident_count,
        position,
        lap_dist_pct,
        est_time,
        track_surface,
        current_lap,
        session_time=None,
    ):
        incident_delta = max(0, incident_count - state.last_incident_count)
        position_loss = max(0, position - state.last_position)
        lap_distance_loss = self.calculate_lap_distance_loss(
            state.last_lap_dist_pct,
            lap_dist_pct,
        )
        est_time_loss = max(0.0, est_time - state.last_est_time)
        abnormal_surface = self.is_abnormal_surface(track_surface)

        reasons = []
        if incident_delta > 0:
            reasons.append("incident counter changed")
        if position_loss >= 2:
            reasons.append("lost positions")
        if lap_distance_loss >= 0.006:
            reasons.append("lost track position quickly")
        if est_time_loss >= 1.5:
            reasons.append("lost estimated time")
        if abnormal_surface:
            reasons.append("abnormal track surface")

        score = (
            incident_delta * 3.0
            + position_loss
            + lap_distance_loss * 100.0
            + est_time_loss
            + (2.5 if abnormal_surface else 0.0)
        )
        if incident_delta >= 2:
            enough_signal = True
        else:
            enough_signal = score >= 3.0 and len(reasons) >= 2
        if not enough_signal:
            return None

        return CautionCandidate(
            driver_name=state.driver_name,
            car_number=state.car_number,
            car_idx=state.car_idx,
            score=score,
            lap=current_lap,
            observed_at=time.time(),
            session_time=self.safe_optional_float(session_time),
            signal_count=len(reasons),
            reasons=tuple(reasons),
        )

    def build_pack_wreck_event(self, candidates, current_lap, force=False):
        unique = []
        seen = set()
        for candidate in sorted(candidates or [], key=lambda item: item.score, reverse=True):
            if candidate.car_idx in seen:
                continue
            seen.add(candidate.car_idx)
            unique.append(candidate)

        if len(unique) < 4:
            return None

        now = time.time()
        if not force and now - self.last_pack_reported_at < self.pack_report_cooldown_seconds:
            return None

        self.last_pack_reported_at = now
        featured = unique[:3]
        if len(featured) >= 2:
            names = ", ".join(
                f"the {candidate.car_number} of {candidate.driver_name}"
                for candidate in featured[:-1]
            )
            names = f"{names}, and the {featured[-1].car_number} of {featured[-1].driver_name}"
        else:
            names = f"the {featured[0].car_number} of {featured[0].driver_name}"

        replay_time = next(
            (
                candidate.session_time
                for candidate in unique
                if candidate.session_time is not None
            ),
            None,
        )

        return IncidentEvent(
            event_type="INCIDENT",
            driver_name=featured[0].driver_name,
            car_number=featured[0].car_number,
            car_idx=featured[0].car_idx,
            message=(
                "Big trouble in the pack. Several cars are suddenly showing "
                f"trouble, including {names}. This looks like what could have "
                "brought out the caution."
            ),
            importance=10,
            lap=current_lap,
            incident_delta=max(candidate.score for candidate in unique),
            total_incidents=len(unique),
            trouble_type="pack wreck",
            replay_session_time=replay_time,
            replay_confidence="high" if replay_time is not None else "low",
        )

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
        suppress_soft_events=False,
    ):
        incident_delta = incident_count - state.last_incident_count
        position_loss = position - state.last_position
        lap_distance_loss = self.calculate_lap_distance_loss(
            state.last_lap_dist_pct,
            lap_dist_pct,
        )
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

        if suppress_soft_events:
            return None

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

    def calculate_lap_distance_loss(self, previous, current):
        """Return backward movement while ignoring the normal 1.0 -> 0.0 lap wrap."""
        loss = previous - current
        if loss > 0.5:
            return 0.0
        return max(loss, 0.0)

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

    def safe_optional_float(self, value):
        try:
            if value is None:
                return None
            return float(value)
        except Exception:
            return None
