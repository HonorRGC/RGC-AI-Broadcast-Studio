import time
from dataclasses import dataclass


@dataclass(frozen=True)
class LiveBattleStory:
    story_type: str
    headline: str
    summary: str
    importance: int
    primary_car_idx: int | None = None
    participant_car_indices: tuple[int, ...] = ()
    confidence: str = "medium"
    position: int = 0


class LiveBattleDetector:
    """Fast on-track battle detector built from live lap-distance telemetry.

    Official iRacing scoring is still the source of truth for the leaderboard,
    restart order, and results. This detector is for broadcast timing: who is
    physically alongside, who is nearly three-wide, and when a pass looks clear
    before the scoring tower catches up.
    """

    ALONGSIDE_DELTA = 0.0028
    THREE_WIDE_DELTA = 0.0024
    CLEAR_DELTA = 0.0048
    PACK_MAX_POSITION = 16

    def __init__(self):
        self.pending_clears = {}
        self.pending_side_by_side = {}
        self.pending_three_wide = {}
        self.last_story_at = {}
        self.story_cooldown_seconds = 24.0
        self.high_priority_cooldown_seconds = 9.0
        self.side_by_side_required_ticks = 2
        self.three_wide_required_ticks = 2
        self.clear_required_ticks = 3

    def analyze(
        self,
        results,
        driver_lookup,
        lap_dist_pct_status,
        pit_road_status=None,
        current_lap=0,
        total_laps=0,
        green_lap_count=0,
    ):
        if current_lap < 1 or not results or not lap_dist_pct_status:
            return []
        if green_lap_count <= 0:
            return []

        cars = self.build_cars(results, lap_dist_pct_status, pit_road_status)
        if len(cars) < 2:
            return []

        stories = []
        three_wide = self.detect_three_wide(cars, driver_lookup, current_lap, total_laps)
        if three_wide:
            stories.append(three_wide)

        clear = self.detect_confident_clear(cars, driver_lookup, current_lap, total_laps)
        if clear:
            stories.append(clear)

        alongside = self.detect_side_by_side(cars, driver_lookup, current_lap, total_laps)
        if alongside:
            stories.append(alongside)

        stories.sort(key=lambda story: story.importance, reverse=True)
        return stories[:2]

    def detect_three_wide(self, cars, driver_lookup, current_lap, total_laps):
        for index in range(len(cars) - 2):
            group = cars[index : index + 3]
            if group[0]["position"] > self.PACK_MAX_POSITION:
                continue
            if self.progress_spread(group) > self.THREE_WIDE_DELTA:
                self.pending_three_wide.pop(tuple(car["car_idx"] for car in group), None)
                continue
            key = ("three_wide", tuple(car["car_idx"] for car in group))
            if not self.stable_for_ticks(
                self.pending_three_wide,
                key,
                self.three_wide_required_ticks,
            ):
                continue
            if not self.cooldown_ready(key, current_lap, total_laps):
                continue
            names = [self.driver_label(driver_lookup, car["car_idx"]) for car in group]
            position = group[0]["position"]
            self.mark_called(key)
            return LiveBattleStory(
                story_type="live_three_wide",
                headline=f"Three-car battle near {self.ordinal(position)}.",
                summary=(
                    f"{names[0]}, {names[1]}, and {names[2]} have been stacked "
                    f"together around {self.ordinal(position)}. Call it as a "
                    "tight battle for position without claiming a lane or a completed pass."
                ),
                importance=self.importance_for_position(position, total_laps, current_lap) + 1,
                primary_car_idx=group[1]["car_idx"],
                participant_car_indices=tuple(car["car_idx"] for car in group),
                confidence="high",
                position=position,
            )
        return None

    def detect_side_by_side(self, cars, driver_lookup, current_lap, total_laps):
        best_pair = None
        best_position = 999
        for first, second in zip(cars, cars[1:]):
            position = min(first["position"], second["position"])
            if position > self.PACK_MAX_POSITION:
                continue
            if abs(first["progress"] - second["progress"]) > self.ALONGSIDE_DELTA:
                continue
            if position < best_position:
                best_pair = (first, second)
                best_position = position

        if not best_pair:
            self.pending_side_by_side = {}
            return None
        first, second = best_pair
        key = ("side_by_side", tuple(sorted([first["car_idx"], second["car_idx"]])))
        if not self.stable_for_ticks(
            self.pending_side_by_side,
            key,
            self.side_by_side_required_ticks,
        ):
            return None
        if not self.cooldown_ready(key, current_lap, total_laps):
            return None

        first_label = self.driver_label(driver_lookup, first["car_idx"])
        second_label = self.driver_label(driver_lookup, second["car_idx"])
        self.mark_called(key)
        return LiveBattleStory(
            story_type="live_side_by_side",
            headline=f"Close battle for {self.ordinal(best_position)}.",
            summary=(
                f"{first_label} and {second_label} have been battling for "
                f"{self.ordinal(best_position)}. The spot is not settled yet, "
                "so describe the pressure without declaring a completed pass."
            ),
            importance=self.importance_for_position(best_position, total_laps, current_lap),
            primary_car_idx=second["car_idx"],
            participant_car_indices=(first["car_idx"], second["car_idx"]),
            confidence="medium",
            position=best_position,
        )

    def detect_confident_clear(self, cars, driver_lookup, current_lap, total_laps):
        by_position = {car["position"]: car for car in cars}
        best_story = None
        for position in sorted(by_position):
            if position <= 0 or position >= self.PACK_MAX_POSITION:
                continue
            leader = by_position.get(position)
            challenger = by_position.get(position + 1)
            if not leader or not challenger:
                continue
            delta = challenger["progress"] - leader["progress"]
            key = ("clear", challenger["car_idx"], leader["car_idx"], position)
            if delta > self.CLEAR_DELTA:
                self.pending_clears[key] = self.pending_clears.get(key, 0) + 1
            else:
                self.pending_clears.pop(key, None)
                continue
            if self.pending_clears[key] < self.clear_required_ticks:
                continue
            if not self.cooldown_ready(key, current_lap, total_laps):
                continue
            challenger_label = self.driver_label(driver_lookup, challenger["car_idx"])
            leader_label = self.driver_label(driver_lookup, leader["car_idx"])
            self.mark_called(key)
            best_story = LiveBattleStory(
                story_type="live_pass_clear",
                headline=f"{challenger_label} makes the move for {self.ordinal(position)}.",
                summary=(
                    f"{challenger_label} has worked past {leader_label} "
                    f"for {self.ordinal(position)} on track. Call it as a "
                    "completed move only if it still matches the live picture; "
                    "otherwise make it a pressure battle for that spot."
                ),
                importance=self.importance_for_position(position, total_laps, current_lap) + 1,
                primary_car_idx=challenger["car_idx"],
                participant_car_indices=(leader["car_idx"], challenger["car_idx"]),
                confidence="high",
                position=position,
            )
            break
        return best_story

    @staticmethod
    def stable_for_ticks(bucket, active_key, required_ticks):
        for key in list(bucket):
            if key != active_key:
                bucket.pop(key, None)
        bucket[active_key] = bucket.get(active_key, 0) + 1
        return bucket[active_key] >= required_ticks

    def build_cars(self, results, distances, pit_status):
        pit_status = pit_status or []
        valid = [car for car in results or [] if car.get("CarIdx") is not None]
        zero_based = any(self.integer(car.get("Position"), 999) == 0 for car in valid)
        cars = []
        for car in valid:
            car_idx = self.integer(car.get("CarIdx"), -1)
            if car_idx < 0 or car_idx >= len(distances):
                continue
            if car_idx < len(pit_status) and pit_status[car_idx]:
                continue
            position = self.display_position(car.get("Position"), zero_based)
            if position <= 0 or position >= 999:
                continue
            lap = self.integer(car.get("LapsComplete", car.get("Lap", 0)), 0)
            try:
                distance = float(distances[car_idx]) % 1.0
            except (TypeError, ValueError):
                continue
            cars.append(
                {
                    "car_idx": car_idx,
                    "position": position,
                    "progress": lap + distance,
                }
            )
        return sorted(cars, key=lambda car: car["position"])

    def cooldown_ready(self, key, current_lap, total_laps):
        last = self.last_story_at.get(key, 0.0)
        cooldown = (
            self.high_priority_cooldown_seconds
            if self.is_late_race(current_lap, total_laps)
            else self.story_cooldown_seconds
        )
        return time.time() - last >= cooldown

    def mark_called(self, key):
        self.last_story_at[key] = time.time()

    def importance_for_position(self, position, total_laps, current_lap):
        importance = 6
        if position <= 1:
            importance = 10
        elif position <= 5:
            importance = 9
        elif position <= 10:
            importance = 8
        if self.is_late_race(current_lap, total_laps):
            importance += 1
        return min(10, importance)

    @staticmethod
    def is_late_race(current_lap, total_laps):
        try:
            return int(total_laps) > 0 and int(total_laps) - int(current_lap) <= 5
        except Exception:
            return False

    @staticmethod
    def progress_spread(cars):
        values = [car["progress"] for car in cars]
        return max(values) - min(values)

    @staticmethod
    def display_position(raw_position, zero_based):
        position = LiveBattleDetector.integer(raw_position, 999)
        return position + 1 if zero_based else position

    @staticmethod
    def driver_label(driver_lookup, car_idx):
        info = driver_lookup.get(car_idx, {}) if driver_lookup else {}
        name = info.get("name", f"Car {car_idx}")
        number = info.get("number", "?")
        return f"{name} in the number {number}"

    @staticmethod
    def ordinal(position):
        try:
            position = int(position)
        except Exception:
            return str(position)
        suffix = "th"
        if position % 100 not in (11, 12, 13):
            suffix = {1: "st", 2: "nd", 3: "rd"}.get(position % 10, "th")
        return f"{position}{suffix}"

    @staticmethod
    def integer(value, default):
        try:
            return int(value)
        except (TypeError, ValueError):
            return default
