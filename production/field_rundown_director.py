from dataclasses import dataclass

from helpers.position_formatter import PositionFormatter


@dataclass(frozen=True)
class FieldRundownSegment:
    message: str
    priority: int
    speaker: str
    category: str
    camera_sequence: tuple[int, ...] = ()
    camera_sequence_steps: tuple[tuple, ...] = ()
    camera_return_home_after_sequence: bool = False
    feature_duration_seconds: float = 0.0


class FieldRundownDirector:
    GROUP_SIZE = 1
    MAX_RUNNING_ORDER_CARS = 10
    LONG_GREEN_RUN_LAPS = 20

    def __init__(self):
        self.sent_milestones = set()
        self.active_milestone = None
        self.active_entries = []
        self.active_next_index = 0
        self.active_entry_count = 0
        self.active_called_car_indices = set()

    def update(
        self,
        results,
        driver_lookup,
        current_lap,
        total_laps,
        under_green,
        green_lap_count=0,
    ):
        if not under_green or total_laps < 20 or current_lap <= 0:
            self.cancel_active()
            return []

        milestone = self.active_milestone or self.next_due_milestone(
            current_lap,
            total_laps,
            green_lap_count,
        )
        if not milestone:
            return []

        if self.active_milestone is None:
            frozen_results = self.freeze_running_order(results)[
                : self.MAX_RUNNING_ORDER_CARS
            ]
            if len(frozen_results) < 3:
                return []
            self.active_milestone = milestone
            self.sent_milestones.add(milestone)
            self.active_entries = self.build_entries(frozen_results, driver_lookup)
            self.active_entry_count = len(self.active_entries)
            self.active_called_car_indices = set()
            self.active_next_index = 0

        live_entries = self.build_entries(
            self.freeze_running_order(results)[: self.active_entry_count],
            driver_lookup,
        )
        segment = self.build_next_segment(
            milestone=self.active_milestone,
            entries=live_entries,
            current_lap=current_lap,
            total_laps=total_laps,
        )
        return [segment] if segment else []

    def is_due_or_active(self, current_lap, total_laps, green_lap_count=0):
        if self.active_milestone:
            return True
        if total_laps < 20 or current_lap <= 0:
            return False
        return self.next_due_milestone(
            current_lap,
            total_laps,
            green_lap_count,
        ) is not None

    def next_due_milestone(self, current_lap, total_laps, green_lap_count=0):
        if (
            "long_green" not in self.sent_milestones
            and green_lap_count >= self.LONG_GREEN_RUN_LAPS
        ):
            return "long_green"
        return None

    def build_quarter_rundown(
        self,
        frozen_results,
        driver_lookup,
        current_lap=0,
        total_laps=0,
    ):
        return self.build_segments(
            "quarter",
            self.build_entries(
                self.freeze_running_order(frozen_results)[
                    : self.MAX_RUNNING_ORDER_CARS
                ],
                driver_lookup,
            ),
            current_lap,
            total_laps,
        )

    def build_entries(self, frozen_results, driver_lookup):
        entries = []
        zero_based = self.results_are_zero_based(frozen_results)
        previous_gap_to_leader = None
        for order_position, car in enumerate(frozen_results, start=1):
            car_idx = car.get("CarIdx")
            driver_info = driver_lookup.get(car_idx, {})
            name = driver_info.get("name", f"Car {car_idx}")
            number = driver_info.get("number", "?")
            current_position = self.display_position(
                car.get("Position", order_position),
                zero_based,
            )
            gap_to_leader = self.safe_float(car.get("Time", car.get("Gap", 0)))
            gap_to_car_ahead = 0.0
            if order_position > 1 and previous_gap_to_leader is not None:
                gap_to_car_ahead = max(0.0, gap_to_leader - previous_gap_to_leader)
            entries.append(
                {
                    "order_position": order_position,
                    "position": current_position,
                    "starting_position": self.safe_int(
                        car.get("StartingPosition"),
                        order_position,
                    ),
                    "car_idx": car_idx,
                    "name": name,
                    "number": number,
                    "gap": gap_to_car_ahead,
                    "gap_to_car_ahead": gap_to_car_ahead,
                    "gap_to_leader": gap_to_leader,
                    "last_lap": self.safe_float(car.get("LastTime", 0)),
                    "fastest_lap": self.safe_float(
                        car.get(
                            "FastestTime",
                            car.get(
                                "BestLapTime",
                                car.get("FastestLapTime", car.get("BestTime", 0)),
                            ),
                        )
                    ),
                    "league_context": self.league_rundown_context(
                        driver_info,
                        order_position,
                    ),
                }
            )
            previous_gap_to_leader = gap_to_leader
        return entries

    def build_segments(self, milestone, entries, current_lap=0, total_laps=0):
        segments = []
        for group_number, start in enumerate(
            range(0, len(entries), self.GROUP_SIZE),
            start=1,
        ):
            group = entries[start:start + self.GROUP_SIZE]
            intro = self.segment_intro(milestone, group_number, current_lap, total_laps)
            lines = [self.format_entry(entry) for entry in group]
            closing = ""
            if start + self.GROUP_SIZE >= len(entries):
                closing = self.segment_closing(milestone)

            segments.append(
                FieldRundownSegment(
                    message=self.combine_message(intro, lines, closing),
                    priority=10,
                    speaker="jeff",
                    category=f"{milestone}_field_rundown_{group_number}",
                    camera_sequence=tuple(
                        entry["car_idx"]
                        for entry in group
                        if entry["car_idx"] is not None
                    ),
                    camera_sequence_steps=self.build_quarter_camera_steps(group),
                    camera_return_home_after_sequence=(
                        start + self.GROUP_SIZE >= len(entries)
                    ),
                    feature_duration_seconds=self.segment_feature_duration(milestone),
                )
            )

        return segments

    def build_next_segment(self, milestone, entries, current_lap, total_laps):
        start = self.active_next_index
        if start >= self.active_entry_count:
            self.complete_active_milestone()
            return None

        group_number = start // self.GROUP_SIZE + 1
        group = self.next_live_group(entries, start)
        self.active_next_index += self.GROUP_SIZE
        is_final = self.active_next_index >= self.active_entry_count
        if is_final:
            self.sent_milestones.add(milestone)

        intro = self.segment_intro(milestone, group_number, current_lap, total_laps)
        lines = [self.format_entry(entry) for entry in group]
        closing = self.segment_closing(milestone) if is_final else ""
        segment = FieldRundownSegment(
            message=self.combine_message(intro, lines, closing),
            priority=10,
            speaker="jeff",
            category=f"{milestone}_field_rundown_{group_number}",
            camera_sequence=tuple(
                entry["car_idx"] for entry in group if entry["car_idx"] is not None
            ),
            camera_sequence_steps=self.build_quarter_camera_steps(group),
            camera_return_home_after_sequence=is_final,
            feature_duration_seconds=self.segment_feature_duration(milestone),
        )

        if is_final:
            self.complete_active_milestone()
        return segment

    def next_live_group(self, entries, start):
        group = []
        for entry in entries[start:start + self.GROUP_SIZE]:
            if entry["car_idx"] not in self.active_called_car_indices:
                group.append(entry)

        if not group:
            for entry in entries:
                if entry["car_idx"] not in self.active_called_car_indices:
                    group.append(entry)
                    break

        for entry in group:
            self.active_called_car_indices.add(entry["car_idx"])
        return group

    def combine_message(self, intro, lines, closing):
        parts = [part for part in [intro, " ".join(lines)] if part]
        return f"{' '.join(parts)}{closing}".strip()

    def complete_active_milestone(self):
        self.active_milestone = None
        self.active_entries = []
        self.active_next_index = 0
        self.active_entry_count = 0
        self.active_called_car_indices = set()

    def cancel_active(self):
        self.complete_active_milestone()

    def segment_intro(self, milestone, group_number, current_lap, total_laps):
        laps_left = max(total_laps - current_lap, 0) if total_laps else 0
        lap_text = f" with {laps_left} laps to go" if laps_left else ""
        if group_number == 1:
            return (
                f"We are 20 laps into this green-flag stretch{lap_text}. "
                "Let's do a rundown of the top ten."
            )
        return ""

    def segment_closing(self, milestone):
        return " That completes the top-ten reset."

    def build_quarter_camera_steps(self, group):
        steps = []
        for entry in group:
            car_idx = entry["car_idx"]
            if car_idx is None:
                continue
            steps.append((car_idx, "TV1", 0))
            steps.append((car_idx, "Cockpit", 0))
        return tuple(steps)

    def segment_feature_duration(self, milestone):
        if milestone == "long_green":
            return 22.0
        return 0.0

    def freeze_running_order(self, results):
        valid = [dict(car) for car in results or [] if car.get("CarIdx") is not None]
        zero_based = self.results_are_zero_based(valid)
        return sorted(
            valid,
            key=lambda car: self.display_position(
                car.get("Position", 999),
                zero_based,
            ),
        )

    def freeze_starting_order(self, results):
        valid = [dict(car) for car in results or [] if car.get("CarIdx") is not None]
        if any(self.safe_int(car.get("StartingPosition"), 0) > 0 for car in valid):
            return sorted(
                valid,
                key=lambda car: self.safe_int(car.get("StartingPosition"), 999),
            )
        return self.freeze_running_order(valid)

    def format_entry(self, entry):
        current_position = PositionFormatter.ordinal(entry["position"])
        starting_position = entry.get("starting_position", 0)
        net = starting_position - entry["position"] if starting_position else 0
        position = entry["position"]
        number = entry["number"]
        name = entry["name"]

        if net > 0:
            templates = (
                f"{current_position.capitalize()} place is the {number} of {name}, up {self.position_count(net)} from the start.",
                f"Scored {current_position}, {name} has moved the {number} forward {self.position_count(net)}.",
                f"{name} has climbed to {current_position} in the number {number}, a gain of {self.position_count(net)}.",
            )
        elif net < 0:
            lost = self.position_count(abs(net))
            starting = PositionFormatter.ordinal(starting_position)
            templates = (
                f"{current_position.capitalize()} place belongs to the {number} of {name}, after starting {starting}.",
                f"{name} is shown {current_position} in the number {number}, down {lost} from the grid.",
                f"The {number} of {name} is holding {current_position} now after slipping back {lost}.",
            )
        else:
            templates = (
                f"{current_position.capitalize()} place, the {number} of {name}, right where they started.",
                f"{name} continues in {current_position} with the number {number}, matching their starting spot.",
                f"The {number} of {name} is steady in {current_position}, no change from the grid.",
            )

        stat_context = entry.get("league_context") or self.session_stat_context(
            entry,
            net,
        )
        if stat_context:
            return f"{templates[(position - 1) % len(templates)]} {stat_context}"
        return templates[(position - 1) % len(templates)]

    def league_rundown_context(self, driver_info, order_position=1):
        candidates = []
        driver_info = driver_info or {}

        profile_context = self.league_profile_context(
            driver_info.get("league_profile") or driver_info
        )
        if profile_context:
            candidates.append(profile_context)

        for stats in driver_info.get("league_stats_by_scope") or []:
            stats_context = self.league_stats_context(stats)
            if stats_context:
                if profile_context:
                    candidates.append(f"{profile_context} {stats_context}")
                candidates.append(stats_context)

        if not candidates:
            return ""

        index = max(0, self.safe_int(order_position, 1) - 1) % len(candidates)
        return candidates[index]

    def league_stats_context(self, stats):
        stats = stats or {}
        scope = str(stats.get("stats_scope") or "season").strip().casefold()
        scope_label = (
            "career"
            if scope in {"career", "all", "all_seasons", "all seasons"}
            else "season"
        )

        track_context = self.league_track_context(stats)
        if track_context:
            return track_context

        points = self.clean(stats.get("points_position"))
        points_to_next = self.clean(stats.get("points_to_next"))
        if points:
            sentence = f"They entered this one {PositionFormatter.ordinal(points)} in points"
            if points_to_next:
                sentence += f", {points_to_next} points from the next spot"
            return f"{sentence}."

        wins = self.clean(stats.get("wins"))
        top_fives = self.clean(stats.get("top_fives"))
        top_tens = self.clean(stats.get("top_tens"))
        starts = self.clean(stats.get("starts"))
        avg_finish = self.clean(stats.get("avg_finish"))
        last_finish = self.clean(stats.get("last_finish"))

        if self.positive_number(wins) or self.positive_number(top_fives):
            pieces = []
            if self.positive_number(wins):
                pieces.append(f"{wins} {scope_label} win{'s' if wins != '1' else ''}")
            if self.positive_number(top_fives):
                pieces.append(f"{top_fives} top-five{'s' if top_fives != '1' else ''}")
            return f"Their {scope_label} record shows {self.join_phrase(pieces)}."

        if self.positive_number(starts) and scope_label == "career":
            pieces = [f"{starts} league starts"]
            if self.positive_number(top_tens):
                pieces.append(f"{top_tens} top-tens")
            return f"Across their league career, they have {self.join_phrase(pieces)}."

        if avg_finish:
            return f"Their {scope_label} average finish is {avg_finish}."

        if last_finish:
            return f"Last time out in the league, they finished {PositionFormatter.ordinal(last_finish)}."

        note = self.clean(stats.get("notes"))
        if note:
            return self.trim_sentence(note)

        return ""

    def league_track_context(self, stats):
        track_starts = self.clean(stats.get("track_starts"))
        track_wins = self.clean(stats.get("track_wins"))
        best_track_finish = self.clean(stats.get("best_track_finish"))
        if not any((track_starts, track_wins, best_track_finish)):
            return ""

        pieces = []
        if self.positive_number(track_starts):
            pieces.append(
                f"{track_starts} previous league start{'s' if track_starts != '1' else ''}"
            )
        if self.positive_number(track_wins):
            pieces.append(f"{track_wins} track win{'s' if track_wins != '1' else ''}")
        if best_track_finish:
            pieces.append(f"a best finish of {PositionFormatter.ordinal(best_track_finish)}")

        if not pieces:
            return ""
        return f"At this track, they have {self.join_phrase(pieces)}."

    def league_profile_context(self, profile):
        profile = profile or {}
        style = self.clean(profile.get("driving_style"))
        hometown = self.location_phrase(profile)
        sponsor = self.clean(profile.get("sponsor"))
        notes = self.clean(profile.get("notes"))

        if style and hometown:
            return f"League notes list them as {style}, representing {hometown}."
        if style:
            return f"League notes describe them as {style}."
        if hometown:
            return f"They represent {hometown}."
        if sponsor:
            return f"Their listed sponsor is {sponsor}."
        if notes:
            return self.trim_sentence(notes)
        return ""

    def location_phrase(self, profile):
        parts = [
            self.clean(profile.get("hometown")),
            self.clean(profile.get("state")),
            self.clean(profile.get("country")),
        ]
        parts = [part for part in parts if part]
        return ", ".join(parts)

    def join_phrase(self, pieces):
        pieces = [str(piece) for piece in pieces if piece]
        if len(pieces) <= 1:
            return "".join(pieces)
        if len(pieces) == 2:
            return " and ".join(pieces)
        return f"{', '.join(pieces[:-1])}, and {pieces[-1]}"

    def positive_number(self, value):
        try:
            return float(str(value or "").strip()) > 0
        except (TypeError, ValueError):
            return False

    def trim_sentence(self, text, max_words=18):
        words = str(text or "").strip().split()
        if not words:
            return ""
        if len(words) > max_words:
            words = words[:max_words]
        sentence = " ".join(words).rstrip(".,;")
        return f"{sentence}."

    def session_stat_context(self, entry, net):
        position = self.safe_int(entry.get("position"), 0)
        gap_to_car_ahead = self.safe_float(
            entry.get("gap_to_car_ahead", entry.get("gap", 0))
        )
        gap_to_leader = self.safe_float(entry.get("gap_to_leader", 0))
        fastest_lap = self.safe_float(entry.get("fastest_lap", 0))
        last_lap = self.safe_float(entry.get("last_lap", 0))

        if position == 1 and fastest_lap > 0:
            return f"Their best lap so far is {fastest_lap:.3f} seconds."
        if position == 1 and last_lap > 0:
            return f"Last time by, they ran a {last_lap:.3f}."
        if position > 1 and 0 < gap_to_car_ahead < 0.75:
            return f"They are within {gap_to_car_ahead:.1f} seconds of the car ahead, so that is still a live battle."
        if position > 1 and gap_to_car_ahead >= 0.75:
            return f"They are about {gap_to_car_ahead:.1f} seconds behind the car ahead."
        if position > 1 and gap_to_leader > 0:
            return f"They are scored about {gap_to_leader:.1f} seconds behind the leader."
        if net > 0:
            return f"That is {self.position_count(net)} gained since the start."
        if net < 0:
            return f"They are trying to stop the slide after losing {self.position_count(abs(net))}."
        return ""

    def movement_phrase(self, current_position, starting_position):
        if not starting_position:
            return ""
        starting = PositionFormatter.ordinal(starting_position)
        net = starting_position - current_position
        if net > 0:
            return f", after starting {starting}, up {self.position_count(net)}"
        if net < 0:
            return (
                f", after starting {starting}, down "
                f"{self.position_count(abs(net))}"
            )
        return f", right where they started in {starting}"

    def results_are_zero_based(self, results):
        return any(car.get("Position") == 0 for car in results or [])

    def display_position(self, raw_position, zero_based):
        try:
            position = int(raw_position)
        except Exception:
            return 999
        return position + 1 if zero_based else position

    def position_count(self, count):
        try:
            count = int(count)
        except Exception:
            return f"{count} spots"
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

    def clean(self, value):
        return str(value or "").strip()
