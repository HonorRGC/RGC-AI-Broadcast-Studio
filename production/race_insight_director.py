from dataclasses import dataclass
import random


@dataclass(frozen=True)
class RaceInsight:
    message: str
    category: str
    speaker: str = "jeff"
    priority: int = 7
    camera_target_car_idx: int | None = None
    participant_car_indices: tuple[int, ...] = ()


class RaceInsightDirector:
    """Adds non-repeating racing knowledge at natural breaks."""

    def __init__(self, seed=None):
        self.random = random.Random(seed)
        self.used_topics = set()
        self.last_green_insight_lap = 0
        self.last_stat_filler_lap = 0
        self.sent_stat_keys = {}

    def long_green_insight(self, race_state, current_lap):
        if not race_state or not race_state.is_green:
            return None
        if race_state.green_lap_count < 12:
            return None
        if race_state.laps_remaining and race_state.laps_remaining <= 10:
            return None
        if self.last_green_insight_lap and current_lap - self.last_green_insight_lap < 8:
            return None

        candidates = [
            (
                "tire_wear_entry",
                "One thing to watch on a long green run is tire wear on corner entry. "
                "The drivers who can roll out of the throttle smoothly and avoid sliding "
                "the front tires are usually the ones who still have speed later in the run.",
            ),
            (
                "tire_wear_exit",
                "Tire management is not just about going slower. It is about asking less "
                "from the tire at the wrong time. A smooth throttle pickup off the corner "
                "can save the rear tires and keep the car from getting loose late in a run.",
            ),
            (
                "fuel_save_lift",
                "Fuel saving can be subtle in these races. A driver can lift a little earlier "
                "at the end of the straightaway, roll speed through the center, and save fuel "
                "without giving up much lap time if they keep the car free and tidy.",
            ),
            (
                "fuel_save_draft",
                "If fuel mileage becomes part of this, the draft matters. Tucking in behind "
                "another car can let a driver breathe the throttle slightly, save a little fuel, "
                "and still keep touch with the pack.",
            ),
        ]
        insight = self.pick_unused(candidates)
        if not insight:
            return None

        topic, message = insight
        self.used_topics.add(topic)
        self.last_green_insight_lap = current_lap
        return RaceInsight(
            message=message,
            category=f"race_insight:{topic}",
        )

    def race_stat_filler(self, results, driver_lookup, race_state, current_lap):
        if not race_state or not race_state.is_green:
            return None
        if race_state.green_lap_count < 6:
            return None
        if race_state.laps_remaining and race_state.laps_remaining <= 10:
            return None
        if self.last_stat_filler_lap and current_lap - self.last_stat_filler_lap < 5:
            return None

        ordered = self.sorted_running_order(results)
        if len(ordered) < 2:
            return None

        insight = (
            self.closest_battle_insight(ordered, driver_lookup, current_lap)
            or self.biggest_mover_insight(ordered, driver_lookup, current_lap)
            or self.leader_pace_insight(ordered, driver_lookup, current_lap)
        )
        if insight:
            self.last_stat_filler_lap = current_lap
        return insight

    def closest_battle_insight(self, ordered, driver_lookup, current_lap):
        best = None
        for index in range(1, min(len(ordered), 12)):
            front = ordered[index - 1]
            chasing = ordered[index]
            gap = self.gap_between_adjacent(front, chasing)
            if gap <= 0 or gap > 0.75:
                continue
            if best is None or gap < best[2]:
                best = (front, chasing, gap)

        if not best:
            return None

        front, chasing, gap = best
        chasing_idx = chasing.get("CarIdx")
        front_idx = front.get("CarIdx")
        key = ("closest_battle", chasing_idx, front_idx)
        if self.was_recently_sent(key, current_lap, 10):
            return None

        position = self.display_position(chasing, ordered)
        chasing_driver = driver_lookup.get(chasing_idx, {})
        front_driver = driver_lookup.get(front_idx, {})
        chasing_name = chasing_driver.get("name", f"Car {chasing_idx}")
        chasing_number = chasing_driver.get("number", "?")
        front_name = front_driver.get("name", f"Car {front_idx}")
        front_number = front_driver.get("number", "?")
        message = (
            f"The closest battle on track right now is around {self.ordinal(position)}. "
            f"{chasing_name} in the number {chasing_number} is only {gap:.1f} seconds "
            f"behind {front_name} in the number {front_number}, so this is one to watch."
        )
        self.mark_sent(key, current_lap)
        return RaceInsight(
            message=message,
            category=f"race_stat:closest_battle:{chasing_idx}:{current_lap // 5}",
            priority=7,
            speaker="jeff",
            camera_target_car_idx=chasing_idx,
            participant_car_indices=tuple(
                idx for idx in (front_idx, chasing_idx) if idx is not None
            ),
        )

    def biggest_mover_insight(self, ordered, driver_lookup, current_lap):
        best = None
        for car in ordered[:15]:
            start = self.safe_int(car.get("StartingPosition"), 0)
            position = self.display_position(car, ordered)
            if start <= 0 or position <= 0:
                continue
            gained = start - position
            if gained < 4:
                continue
            if best is None or gained > best[1]:
                best = (car, gained)

        if not best:
            return None

        car, gained = best
        car_idx = car.get("CarIdx")
        key = ("biggest_mover", car_idx)
        if self.was_recently_sent(key, current_lap, 12):
            return None

        position = self.display_position(car, ordered)
        driver = driver_lookup.get(car_idx, {})
        name = driver.get("name", f"Car {car_idx}")
        number = driver.get("number", "?")
        message = (
            f"One of the stories quietly building is {name} in the number {number}. "
            f"They started {self.ordinal(self.safe_int(car.get('StartingPosition'), 0))} "
            f"and have climbed to {self.ordinal(position)}, a gain of {self.position_count(gained)}."
        )
        self.mark_sent(key, current_lap)
        return RaceInsight(
            message=message,
            category=f"race_stat:biggest_mover:{car_idx}:{current_lap // 6}",
            priority=6,
            speaker="lead",
            camera_target_car_idx=car_idx,
            participant_car_indices=(car_idx,) if car_idx is not None else (),
        )

    def leader_pace_insight(self, ordered, driver_lookup, current_lap):
        leader = ordered[0]
        second = ordered[1] if len(ordered) > 1 else None
        leader_idx = leader.get("CarIdx")
        key = ("leader_pace", leader_idx)
        if self.was_recently_sent(key, current_lap, 10):
            return None

        gap = self.gap_between_adjacent(leader, second) if second else 0.0
        fastest = self.safe_float(
            leader.get(
                "FastestTime",
                leader.get("BestLapTime", leader.get("FastestLapTime", 0)),
            )
        )
        last = self.safe_float(leader.get("LastTime", 0))
        driver = driver_lookup.get(leader_idx, {})
        name = driver.get("name", f"Car {leader_idx}")
        number = driver.get("number", "?")

        if gap > 0:
            message = (
                f"Up front, {name} in the number {number} has the lead by about "
                f"{gap:.1f} seconds. "
            )
        else:
            message = f"Up front, {name} in the number {number} is controlling the pace. "

        if fastest > 0:
            message += f"Their best lap so far is {fastest:.3f} seconds."
        elif last > 0:
            message += f"Last time by, they ran a {last:.3f}."
        else:
            message += "That is the car everyone else is measuring against right now."

        self.mark_sent(key, current_lap)
        return RaceInsight(
            message=message,
            category=f"race_stat:leader_pace:{leader_idx}:{current_lap // 6}",
            priority=6,
            speaker="jeff",
            camera_target_car_idx=leader_idx,
            participant_car_indices=(leader_idx,) if leader_idx is not None else (),
        )

    def caution_insight(self, race_state):
        if not race_state or not race_state.is_caution:
            return None
        if race_state.laps_remaining <= 0 or race_state.laps_remaining > 10:
            return None

        candidates = [
            (
                "short_run_tires",
                "With a short run to the finish, tire conservation is not the story anymore. "
                "This is closer to a sprint, where clean air, restart execution, and getting "
                "through the gears can matter more than saving anything for later.",
            ),
            (
                "restart_aggression",
                "On a restart this late, the balance changes. Drivers still need to keep it "
                "clean, but nobody is thinking about a 30-lap run from here. Track position "
                "and momentum are everything.",
            ),
        ]
        insight = self.pick_unused(candidates)
        if not insight:
            return None

        topic, message = insight
        self.used_topics.add(topic)
        return RaceInsight(
            message=message,
            category=f"race_insight:{topic}",
            priority=8,
        )

    def pick_unused(self, candidates):
        available = [
            candidate for candidate in candidates
            if candidate[0] not in self.used_topics
        ]
        if not available:
            return None
        return self.random.choice(available)

    def sorted_running_order(self, results):
        valid = [car for car in results or [] if car.get("CarIdx") is not None]
        zero_based = any(self.safe_int(car.get("Position"), 999) == 0 for car in valid)
        return sorted(
            valid,
            key=lambda car: self.safe_int(car.get("Position"), 999)
            + (1 if zero_based else 0),
        )

    def display_position(self, car, ordered):
        raw = self.safe_int(car.get("Position"), 0)
        zero_based = any(self.safe_int(item.get("Position"), 999) == 0 for item in ordered)
        return raw + 1 if zero_based else raw

    def gap_between_adjacent(self, front, chasing):
        if not front or not chasing:
            return 0.0
        front_gap = self.safe_float(front.get("Time", front.get("Gap", 0)))
        chasing_gap = self.safe_float(chasing.get("Time", chasing.get("Gap", 0)))
        if chasing_gap <= 0:
            return 0.0
        return max(0.0, chasing_gap - max(front_gap, 0.0))

    def was_recently_sent(self, key, current_lap, lap_window):
        last_lap = self.sent_stat_keys.get(key)
        return last_lap is not None and current_lap - last_lap < lap_window

    def mark_sent(self, key, current_lap):
        self.sent_stat_keys[key] = current_lap

    def ordinal(self, position):
        position = self.safe_int(position)
        if position <= 0:
            return "the field"
        if position % 100 in (11, 12, 13):
            suffix = "th"
        else:
            suffix = {1: "st", 2: "nd", 3: "rd"}.get(position % 10, "th")
        return f"{position}{suffix}"

    def position_count(self, count):
        count = self.safe_int(count)
        if count == 1:
            return "one spot"
        return f"{count} spots"

    def safe_int(self, value, default=0):
        try:
            return int(value)
        except Exception:
            return default

    def safe_float(self, value, default=0.0):
        try:
            return float(value)
        except Exception:
            return default
