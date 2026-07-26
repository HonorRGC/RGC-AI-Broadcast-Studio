from dataclasses import dataclass

from production.track_style import is_road_course, is_true_pack_drafting_track


@dataclass(frozen=True)
class RacecraftEvent:
    story_type: str
    headline: str
    summary: str
    priority: int = 7
    speaker: str = "jeff"
    camera_target_car_idx: int | None = None
    participant_car_indices: tuple[int, ...] = ()
    driver_name: str = ""
    car_number: str = ""


class RacecraftDirector:
    """
    Detect higher-level race situations that a human booth would recognize.

    This does not try to claim exact fuel or tire choices unless the telemetry
    supports it. It turns live context into realistic booth talking points:
    lap traffic, fuel-save possibilities, pit windows, and short-stop strategy.
    """

    def __init__(self):
        self.sent_lap_traffic_cars = {}
        self.sent_topics = {}
        self.last_pit_strategy_lap = {}

    def analyze(
        self,
        results,
        driver_lookup,
        track_info=None,
        race_state=None,
        current_lap=0,
        total_laps=0,
        lap_dist_pct_status=None,
        pit_states=None,
    ):
        events = []
        ordered = self.sorted_running_order(results)
        if not ordered:
            return events

        lap_traffic = self.detect_leader_lap_traffic(
            ordered,
            driver_lookup,
            current_lap,
            lap_dist_pct_status,
        )
        if lap_traffic:
            events.append(lap_traffic)

        draft_save = self.detect_draft_fuel_save(
            ordered,
            track_info or {},
            race_state,
            current_lap,
            lap_dist_pct_status,
        )
        if draft_save:
            events.append(draft_save)

        pit_strategy = self.detect_recent_pit_strategy(
            pit_states or {},
            driver_lookup,
            race_state,
            current_lap,
        )
        if pit_strategy:
            events.append(pit_strategy)

        pit_window = self.detect_pit_window(
            track_info or {},
            race_state,
            current_lap,
            total_laps,
        )
        if pit_window:
            events.append(pit_window)

        return events

    def detect_leader_lap_traffic(
        self,
        ordered,
        driver_lookup,
        current_lap,
        lap_dist_pct_status=None,
    ):
        if len(ordered) < 2 or current_lap < 3:
            return None

        leader = ordered[0]
        leader_idx = leader.get("CarIdx")
        leader_laps = self.completed_laps(leader)
        leader_pct = self.lap_pct(leader, lap_dist_pct_status)
        if leader_idx is None or leader_laps <= 0 or leader_pct is None:
            return None

        candidates = []
        for car in ordered[1:]:
            car_idx = car.get("CarIdx")
            if car_idx is None:
                continue
            laps = self.completed_laps(car)
            car_pct = self.lap_pct(car, lap_dist_pct_status)
            if laps <= 0 or car_pct is None:
                continue

            laps_behind = max(leader_laps - laps, 0)
            if laps_behind > 1:
                continue

            track_delta = self.distance_ahead_on_track(leader_pct, car_pct)
            if 0.0 < track_delta <= 0.10:
                candidates.append((track_delta, laps_behind, car))

        if not candidates:
            return None

        track_delta, laps_behind, car = min(candidates, key=lambda item: item[0])
        car_idx = car.get("CarIdx")
        if self.was_recently_sent(("lap_traffic", car_idx), current_lap, 8):
            return None

        driver = driver_lookup.get(car_idx, {})
        leader_driver = driver_lookup.get(leader_idx, {})
        name = driver.get("name", f"Car {car_idx}")
        number = driver.get("number", "?")
        leader_name = leader_driver.get("name", "the leader")

        if laps_behind >= 1:
            message = (
                f"{leader_name} is closing on the number {number} of {name}, "
                "and this is the kind of lap traffic that can change the rhythm "
                "of a green-flag run."
            )
            story_type = "lap_traffic"
        else:
            message = (
                f"{name} in the number {number} is right in front of the leader "
                "and fighting to stay on the tail end of the lead lap. That can "
                "turn into a race within the race."
            )
            story_type = "lead_lap_survival"

        self.mark_sent(("lap_traffic", car_idx), current_lap)
        return RacecraftEvent(
            story_type=story_type,
            headline=message,
            summary=message,
            priority=8,
            speaker="jeff",
            camera_target_car_idx=car_idx,
            participant_car_indices=tuple(
                idx for idx in (leader_idx, car_idx) if idx is not None
            ),
            driver_name=name,
            car_number=number,
        )

    def detect_draft_fuel_save(
        self,
        ordered,
        track_info,
        race_state,
        current_lap,
        lap_dist_pct_status=None,
    ):
        green_lap_count = self.safe_int(getattr(race_state, "green_lap_count", 0))
        laps_remaining = self.safe_int(getattr(race_state, "laps_remaining", 0))
        if green_lap_count < 8 or (laps_remaining and laps_remaining <= 8):
            return None
        if not self.is_draft_track(track_info):
            return None
        if self.was_recently_sent("draft_fuel_save", current_lap, 18):
            return None

        top_pack = ordered[:8]
        if len(top_pack) < 5:
            return None
        if not self.is_pack_tight(top_pack, lap_dist_pct_status):
            return None

        message = (
            "This has the look of a fuel-save draft run. When the pack is this "
            "tight, drivers can ride in line, breathe the throttle a little, and "
            "try to make the final stop shorter instead of burning everything up "
            "too early."
        )
        self.mark_sent("draft_fuel_save", current_lap)
        leader_idx = top_pack[0].get("CarIdx")
        return RacecraftEvent(
            story_type="draft_fuel_save",
            headline=message,
            summary=message,
            priority=7,
            speaker="jeff",
            camera_target_car_idx=leader_idx,
            participant_car_indices=tuple(
                car.get("CarIdx") for car in top_pack if car.get("CarIdx") is not None
            ),
        )

    def detect_pit_window(self, track_info, race_state, current_lap, total_laps):
        green_lap_count = self.safe_int(getattr(race_state, "green_lap_count", 0))
        laps_remaining = self.safe_int(getattr(race_state, "laps_remaining", 0))
        if total_laps <= 0 or current_lap < 10 or green_lap_count < 12:
            return None
        if laps_remaining <= 8:
            return None
        if self.was_recently_sent("pit_window", current_lap, 22):
            return None

        if self.is_draft_track(track_info):
            message = (
                "Strategy is starting to matter here. On this kind of drafting "
                "track, stretching the run can mean less fuel needed on the final "
                "stop, and that can open the door for a shorter stop or a two-tire "
                "track-position play."
            )
        elif is_road_course(track_info):
            message = (
                "This is where the road-course pit window starts to get interesting. "
                "A strong in-lap and out-lap can make the undercut work, but if "
                "traffic is heavy, staying out for clean air can be just as valuable."
            )
        else:
            message = (
                "We are getting into the part of the run where the pit window "
                "starts to matter. The teams have to balance tire falloff, fuel "
                "needed to reach the end, and whether clean air is worth more than "
                "fresh tires."
            )
        self.mark_sent("pit_window", current_lap)
        return RacecraftEvent(
            story_type="pit_window",
            headline=message,
            summary=message,
            priority=7,
            speaker="sarah",
        )

    def detect_recent_pit_strategy(
        self,
        pit_states,
        driver_lookup,
        race_state,
        current_lap,
    ):
        if not race_state or not getattr(race_state, "is_green", False):
            return None
        for car_idx, state in pit_states.items():
            exit_lap = self.safe_int(getattr(state, "last_pit_exit_lap", 0))
            if exit_lap <= 0 or current_lap - exit_lap > 2:
                continue
            if self.last_pit_strategy_lap.get(car_idx) == exit_lap:
                continue

            stop_seconds = self.safe_float(getattr(state, "last_pit_stop_seconds", 0.0))
            lane_seconds = self.safe_float(getattr(state, "last_pit_lane_seconds", 0.0))
            gain = self.safe_int(getattr(state, "last_pit_position_gain", 0))
            if stop_seconds <= 0 and lane_seconds <= 0:
                continue

            driver = driver_lookup.get(car_idx, {})
            name = driver.get("name", getattr(state, "driver_name", f"Car {car_idx}"))
            number = driver.get("number", getattr(state, "car_number", "?"))

            if stop_seconds >= 25.0 or lane_seconds >= 65.0:
                message = (
                    f"{name} had a long stay on pit road in the number {number}. "
                    "That has the look of damage repair or a bigger adjustment, "
                    "not just a normal strategy stop."
                )
                priority = 8
            elif stop_seconds < 8.0 and gain >= 2:
                message = (
                    f"That was a short stop for {name} in the number {number}, "
                    f"and it gained {self.position_count(gain)}. That is exactly "
                    "the kind of stop that points toward two tires, fuel only, or "
                    "a track-position call."
                )
                priority = 8
            elif stop_seconds < 8.0:
                message = (
                    f"{name} was not stationary very long on that stop in the "
                    f"number {number}. That may be a short-fill or two-tire style "
                    "call if they only needed enough fuel to reach the next window."
                )
                priority = 7
            else:
                continue

            self.last_pit_strategy_lap[car_idx] = exit_lap
            return RacecraftEvent(
                story_type="pit_strategy_context",
                headline=message,
                summary=message,
                priority=priority,
                speaker="sarah",
                camera_target_car_idx=car_idx,
                participant_car_indices=(car_idx,),
                driver_name=name,
                car_number=number,
            )
        return None

    def is_pack_tight(self, cars, lap_dist_pct_status=None):
        pcts = [
            self.lap_pct(car, lap_dist_pct_status)
            for car in cars
        ]
        pcts = [pct for pct in pcts if pct is not None]
        if len(pcts) < 5:
            return False
        span = max(pcts) - min(pcts)
        if span < 0:
            return False
        if span <= 0.055:
            return True

        times = [self.safe_float(car.get("Time", 999.0), 999.0) for car in cars]
        times = [value for value in times if 0 <= value < 999.0]
        return len(times) >= 5 and max(times) - min(times) <= 2.5

    def is_draft_track(self, track_info):
        return is_true_pack_drafting_track(track_info)

    def sorted_running_order(self, results):
        valid = [car for car in results or [] if car.get("CarIdx") is not None]
        zero_based = any(self.safe_int(car.get("Position"), 999) == 0 for car in valid)
        return sorted(
            valid,
            key=lambda car: self.safe_int(car.get("Position"), 999)
            + (1 if zero_based else 0),
        )

    def lap_pct(self, car, lap_dist_pct_status=None):
        for key in ("LapDistPct", "LapDist", "LapPct"):
            if key in car:
                value = self.safe_optional_float(car.get(key))
                if value is not None:
                    return value
        car_idx = car.get("CarIdx")
        try:
            if lap_dist_pct_status is not None and car_idx is not None:
                return self.safe_optional_float(lap_dist_pct_status[int(car_idx)])
        except Exception:
            return None
        return None

    def completed_laps(self, car):
        for key in ("LapsComplete", "Lap"):
            if key in car:
                return self.safe_int(car.get(key))
        return 0

    @staticmethod
    def distance_ahead_on_track(leader_pct, car_pct):
        distance = float(car_pct) - float(leader_pct)
        if distance <= 0:
            distance += 1.0
        return distance

    def was_recently_sent(self, topic, current_lap, cooldown_laps):
        last_lap = self.sent_topics.get(topic)
        return last_lap is not None and current_lap - last_lap < cooldown_laps

    def mark_sent(self, topic, current_lap):
        self.sent_topics[topic] = current_lap

    @staticmethod
    def position_count(count):
        try:
            count = int(count)
        except Exception:
            return f"{count} spots"
        if count == 1:
            return "one spot"
        return f"{count} spots"

    @staticmethod
    def safe_int(value, default=0):
        try:
            return int(value)
        except Exception:
            return default

    @staticmethod
    def safe_float(value, default=0.0):
        try:
            return float(value)
        except Exception:
            return default

    @staticmethod
    def safe_optional_float(value):
        try:
            if value is None:
                return None
            return float(value)
        except Exception:
            return None
