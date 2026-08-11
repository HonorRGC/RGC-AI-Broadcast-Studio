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
        self.long_green_insight_count = 0
        self.last_stat_filler_lap = 0
        self.sent_stat_keys = {}
        self.points_standings_sent = False

    def long_green_insight(self, race_state, current_lap):
        if not race_state or not race_state.is_green:
            return None
        if race_state.green_lap_count < 12:
            return None
        if race_state.laps_remaining and race_state.laps_remaining <= 10:
            return None
        if self.long_green_insight_count >= 2:
            return None
        if self.last_green_insight_lap and current_lap - self.last_green_insight_lap < 16:
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
        self.long_green_insight_count += 1
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
            self.points_standings_insight(ordered, driver_lookup, race_state, current_lap)
            or
            self.closest_battle_insight(ordered, driver_lookup, current_lap)
            or self.driver_context_insight(ordered, driver_lookup, current_lap)
            or self.biggest_mover_insight(ordered, driver_lookup, current_lap)
            or self.leader_pace_insight(ordered, driver_lookup, current_lap)
        )
        if insight:
            self.last_stat_filler_lap = current_lap
        return insight

    def points_standings_insight(self, ordered, driver_lookup, race_state, current_lap):
        if self.points_standings_sent:
            return None
        if self.safe_int(getattr(race_state, "green_lap_count", 0)) < 10:
            return None
        if self.safe_int(getattr(race_state, "laps_remaining", 999), 999) <= 15:
            return None

        standings = self.points_standings_rows(driver_lookup)
        if len(standings) < 3:
            return None

        leader = standings[0]
        contenders = standings[1:4]
        leader_name = leader["name"]
        leader_position = leader["points_position"]
        contender_text = ", ".join(
            f"{row['name']} in {self.ordinal(row['points_position'])}"
            for row in contenders[:2]
        )
        message = (
            "This is a good time to reset the championship picture. "
            f"{leader_name} came in leading the standings"
        )
        if contender_text:
            message += f", with {contender_text} close enough to keep the pressure on"
        message += ". We will keep that points battle in mind as this run plays out."

        target_idx = None
        for car in ordered:
            driver = (driver_lookup or {}).get(car.get("CarIdx"), {}) or {}
            if self.normalized_name(driver.get("name")) == self.normalized_name(leader["name"]):
                target_idx = car.get("CarIdx")
                break

        self.points_standings_sent = True
        return RaceInsight(
            message=message,
            category=f"race_stat:points_standings:{current_lap // 10}",
            priority=6,
            speaker="jeff",
            camera_target_car_idx=target_idx,
            participant_car_indices=tuple(idx for idx in (target_idx,) if idx is not None),
        )

    def points_standings_rows(self, driver_lookup):
        rows = []
        seen = set()
        for driver in (driver_lookup or {}).values():
            stats = self.scoped_stats((driver or {}).get("league_stats_by_scope") or [], "season")
            if not stats:
                stats = (driver or {}).get("league_stats") or {}
            points_position = self.safe_int((stats or {}).get("points_position"), 0)
            if points_position <= 0 or points_position > 20:
                continue
            name = str((driver or {}).get("name") or (stats or {}).get("name") or "").strip()
            number = str((driver or {}).get("number") or (stats or {}).get("car_number") or "").strip()
            key = self.normalized_name(name) or number
            if not key or key in seen:
                continue
            seen.add(key)
            rows.append(
                {
                    "points_position": points_position,
                    "name": name or f"Car {number}",
                    "number": number,
                    "points_to_next": self.safe_int((stats or {}).get("points_to_next"), 0),
                    "wins": self.safe_int((stats or {}).get("wins"), 0),
                    "top_fives": self.safe_int((stats or {}).get("top_fives"), 0),
                }
            )
        rows.sort(key=lambda row: row["points_position"])
        return rows

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
            f"Good battle going on around {self.ordinal(position)}. "
            f"{chasing_name} in the number {chasing_number} is only {gap:.1f} seconds "
            f"behind {front_name} in the number {front_number}; let's stay with this "
            "for a moment and see how it unfolds."
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

    def driver_context_insight(self, ordered, driver_lookup, current_lap):
        """Use league notes/stats as human-style filler during calm green runs."""

        candidates = []
        for car in ordered[:16]:
            car_idx = car.get("CarIdx")
            if car_idx is None:
                continue
            driver = driver_lookup.get(car_idx, {}) or {}
            context = self.best_driver_context(driver)
            if not context:
                continue
            position = self.display_position(car, ordered)
            start = self.safe_int(car.get("StartingPosition"), 0)
            movement = start - position if start > 0 and position > 0 else 0
            # Prefer useful stories near the front or drivers who have moved,
            # but still let mid-pack league context breathe during long runs.
            score = position - min(max(movement, 0), 6) * 0.5
            candidates.append((score, car, driver, context, movement))

        if not candidates:
            return None

        _, car, driver, context, movement = min(candidates, key=lambda item: item[0])
        car_idx = car.get("CarIdx")
        key = ("driver_context", car_idx, context["key"])
        if self.was_recently_sent(key, current_lap, 26):
            return None

        position = self.display_position(car, ordered)
        name = driver.get("name", f"Car {car_idx}")
        number = driver.get("number", "?")
        movement_line = ""
        if movement >= 3:
            movement_line = (
                f" They have also moved forward {self.position_count(movement)} "
                "from where they started, so the pace is matching the story."
            )
        elif movement <= -3:
            movement_line = (
                f" They have slipped back {self.position_count(abs(movement))} "
                "from the start, so this is a good moment to see whether the car "
                "can settle back into the run."
            )

        message = (
            f"Let's put a little spotlight on {name} in the number {number}, "
            f"running {self.ordinal(position)}. {context['message']}{movement_line}"
        )
        self.mark_sent(key, current_lap)
        return RaceInsight(
            message=message,
            category=f"race_stat:driver_context:{car_idx}:{context['key']}",
            priority=6,
            speaker="jeff",
            camera_target_car_idx=car_idx,
            participant_car_indices=(car_idx,),
        )

    def best_driver_context(self, driver):
        profile = (driver or {}).get("league_profile") or {}
        stats_by_scope = (driver or {}).get("league_stats_by_scope") or []
        if isinstance(stats_by_scope, dict):
            stats_by_scope = [stats_by_scope]

        season_stats = self.scoped_stats(stats_by_scope, "season")
        career_stats = self.scoped_stats(stats_by_scope, "career")
        primary_stats = season_stats or career_stats or ((driver or {}).get("league_stats") or {})

        track_message = self.track_stats_message(primary_stats)
        if track_message:
            return {"key": "track_stats", "message": track_message}

        points_message = self.points_message(season_stats or primary_stats)
        if points_message:
            return {"key": "points", "message": points_message}

        style_message = self.profile_style_message(profile)
        if style_message:
            return {"key": "profile", "message": style_message}

        season_message = self.season_stats_message(season_stats or primary_stats)
        if season_message:
            return {"key": "season_stats", "message": season_message}

        career_message = self.career_stats_message(career_stats)
        if career_message:
            return {"key": "career_stats", "message": career_message}

        note = str((profile or {}).get("notes", "") or "").strip()
        if note:
            return {"key": "driver_note", "message": note}
        return None

    def scoped_stats(self, stats_by_scope, scope):
        scope = str(scope or "").strip().casefold()
        for stats in stats_by_scope or []:
            if str((stats or {}).get("stats_scope", "") or "").strip().casefold() == scope:
                return stats
        return {}

    def track_stats_message(self, stats):
        if not stats:
            return ""
        starts = self.safe_int((stats or {}).get("track_starts"), 0)
        wins = self.safe_int((stats or {}).get("track_wins"), 0)
        best = self.safe_int((stats or {}).get("best_track_finish"), 0)
        if starts <= 0:
            return ""
        if wins > 0:
            return (
                f"They have been strong at this track before with {starts} prior "
                f"{self.start_label(starts)} and {wins} {self.win_label(wins)} here."
            )
        if best > 0:
            return (
                f"Their history at this track is worth watching: {starts} prior "
                f"{self.start_label(starts)} with a best finish of {self.ordinal(best)}."
            )
        return f"They have {starts} prior {self.start_label(starts)} at this track."

    def points_message(self, stats):
        if not stats:
            return ""
        points_position = self.safe_int((stats or {}).get("points_position"), 0)
        points_to_next = self.safe_int((stats or {}).get("points_to_next"), 0)
        if points_position <= 0:
            return ""
        message = f"They came in {self.ordinal(points_position)} in the championship standings"
        if points_to_next > 0:
            message += f", only {points_to_next} points from the next position"
        return message + "."

    def profile_style_message(self, profile):
        if not profile:
            return ""
        pieces = []
        style = str((profile or {}).get("driving_style", "") or "").strip()
        location = str((profile or {}).get("location", "") or "").strip()
        sponsor = str((profile or {}).get("sponsor", "") or "").strip()
        if style:
            pieces.append(f"the league notes describe them as {style}")
        if location:
            pieces.append(f"from {location}")
        if sponsor:
            pieces.append(f"carrying {sponsor} on the car")
        if not pieces:
            return ""
        return "This is one of those driver-card details: " + ", ".join(pieces) + "."

    def season_stats_message(self, stats):
        if not stats:
            return ""
        starts = self.safe_int((stats or {}).get("starts"), 0)
        wins = self.safe_int((stats or {}).get("wins"), 0)
        top_fives = self.safe_int((stats or {}).get("top_fives"), 0)
        avg_finish = str((stats or {}).get("avg_finish", "") or "").strip()
        if wins > 0:
            return (
                f"On the season, they already have {wins} {self.win_label(wins)} "
                f"in {starts} {self.start_label(starts) if starts else 'starts'}."
            )
        if top_fives > 0:
            return f"On the season, they have {top_fives} top-five finishes."
        if avg_finish:
            return f"Their average finish this season is {avg_finish}, so this run matters."
        return ""

    def career_stats_message(self, stats):
        if not stats:
            return ""
        starts = self.safe_int((stats or {}).get("starts"), 0)
        wins = self.safe_int((stats or {}).get("wins"), 0)
        top_fives = self.safe_int((stats or {}).get("top_fives"), 0)
        if starts <= 0:
            return ""
        if wins > 0:
            return (
                f"Across their series career, they have {wins} {self.win_label(wins)} "
                f"in {starts} {self.start_label(starts)}."
            )
        if top_fives > 0:
            return (
                f"Across their series career, they have {top_fives} top-five finishes "
                f"in {starts} {self.start_label(starts)}."
            )
        return f"They have {starts} career {self.start_label(starts)} in this series."

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

    def start_label(self, count):
        count = self.safe_int(count)
        return "start" if count == 1 else "starts"

    def win_label(self, count):
        count = self.safe_int(count)
        return "win" if count == 1 else "wins"

    def safe_int(self, value, default=0):
        try:
            return int(value)
        except Exception:
            return default

    def normalized_name(self, value):
        return str(value or "").strip().casefold()

    def safe_float(self, value, default=0.0):
        try:
            return float(value)
        except Exception:
            return default
