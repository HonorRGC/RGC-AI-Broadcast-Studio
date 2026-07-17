from dataclasses import dataclass


@dataclass(frozen=True)
class BoothConversationLine:
    message: str
    speaker: str
    delay_seconds: float = 0.0
    camera_target_car_idx: int | None = None
    participant_car_indices: tuple[int, ...] = ()


class BoothConversationDirector:
    """
    Builds short, controlled booth conversations for long green-flag runs.

    These are not race-control calls and they should not invent visual contact.
    They give the broadcast room to breathe with strategy, track character, and
    racecraft while the camera watches a live battle or the lead pack.
    """

    DRAFT_TRACKS = ("daytona", "talladega", "superspeedway")
    SHORT_TRACKS = ("martinsville", "bristol", "richmond", "wilkesboro")
    ROAD_TRACKS = ("road", "glen", "sonoma", "spa", "mosport", "virginia")

    def __init__(self):
        self.last_conversation_lap = 0
        self.topic_index = 0
        self.sent_topics: set[str] = set()

    def build(
        self,
        results,
        driver_lookup,
        track_info=None,
        race_state=None,
        current_lap=0,
        total_laps=0,
    ):
        current_lap = self.safe_int(current_lap)
        total_laps = self.safe_int(total_laps)
        green_lap_count = self.safe_int(getattr(race_state, "green_lap_count", 0))
        laps_remaining = self.safe_int(getattr(race_state, "laps_remaining", 0))

        if green_lap_count < 14:
            return []
        if total_laps > 0 and laps_remaining <= 12:
            return []
        if self.last_conversation_lap and current_lap - self.last_conversation_lap < 24:
            return []

        ordered = self.sorted_running_order(results)
        if len(ordered) < 5:
            return []

        topic = self.choose_topic(track_info or {}, green_lap_count, laps_remaining)
        if not topic:
            return []

        battle = self.find_action_target(ordered, driver_lookup)
        target_idx = battle[0] if battle else ordered[0].get("CarIdx")
        participant_indices = battle[1] if battle else tuple(
            car.get("CarIdx") for car in ordered[:3] if car.get("CarIdx") is not None
        )

        lines = self.topic_lines(
            topic,
            track_info or {},
            battle,
            target_idx,
            participant_indices,
        )
        if lines:
            self.last_conversation_lap = current_lap
            self.sent_topics.add(topic)
        return lines

    def choose_topic(self, track_info, green_lap_count, laps_remaining):
        track_name = str(
            track_info.get("track_name")
            or track_info.get("track_display_name")
            or ""
        ).lower()
        track_type = str(track_info.get("track_type") or "").lower()
        text = f"{track_name} {track_type}"

        preferred = []
        if any(key in text for key in self.DRAFT_TRACKS):
            preferred.extend(["draft_rhythm", "fuel_save"])
        elif any(key in text for key in self.SHORT_TRACKS):
            preferred.extend(["short_track_patience", "tire_heat"])
        elif any(key in text for key in self.ROAD_TRACKS):
            preferred.extend(["road_course_rhythm", "brake_management"])
        else:
            preferred.extend(["tire_falloff", "clean_air"])

        if green_lap_count >= 22 and laps_remaining > 18:
            preferred.append("long_run_strategy")

        for topic in preferred:
            if topic not in self.sent_topics:
                return topic

        fallback = preferred[self.topic_index % len(preferred)]
        self.topic_index += 1
        return fallback

    def topic_lines(
        self,
        topic,
        track_info,
        battle,
        target_idx,
        participant_indices,
    ):
        track_name = (
            track_info.get("track_name")
            or track_info.get("track_display_name")
            or "this place"
        )
        battle_note = ""
        if battle:
            _, _, lead_label, chase_label, gap = battle
            battle_note = (
                f" While they talk through it, keep an eye on {chase_label} "
                f"closing on {lead_label}, with the gap around {gap:.1f} seconds."
            )

        topics = {
            "draft_rhythm": (
                "lead",
                (
                    f"This is where {track_name} becomes more than raw speed. "
                    "The draft decides when a driver can build a run and when "
                    f"they have to stay patient.{battle_note}"
                ),
                "jeff",
                (
                    "Exactly — the fast car is not always the one that moves first. "
                    "The smart move is timing the push, keeping the nose clean, and "
                    "not showing the move too early."
                ),
                "sarah",
                (
                    "And from the strategy side, riding in line can save just enough "
                    "fuel to change the final stop. That can matter as much as one "
                    "good pass."
                ),
            ),
            "fuel_save": (
                "lead",
                (
                    "This green run has the feel of drivers thinking ahead, not just "
                    "racing the lap they are on."
                ),
                "sarah",
                (
                    "That is the quiet game right now. A little lift in the draft, "
                    "a smoother throttle trace, and suddenly the last pit stop can "
                    "be a few seconds shorter."
                ),
                "jeff",
                (
                    "The tricky part is saving without getting swallowed up. If you "
                    "lose the pack, the fuel you saved may not be worth the track "
                    "position you gave away."
                ),
            ),
            "tire_falloff": (
                "lead",
                (
                    f"Long runs at {track_name} can turn into a tire-management race. "
                    "The first few laps tell you who has speed; the middle of the run "
                    "tells you who has taken care of the car."
                ),
                "jeff",
                (
                    "That is where patience pays off. A driver who gives up a tenth "
                    "early can get it back later when the right-front tire still has "
                    "something left."
                ),
                "sarah",
                (
                    "And that changes the pit box conversation too — if the falloff "
                    "is big enough, fresh tires can beat clean air."
                ),
            ),
            "clean_air": (
                "lead",
                (
                    "Clean air is still one of the biggest advantages on a run like "
                    "this. The leader gets to pick the line; everyone behind has to "
                    "deal with disturbed air and dirty exits."
                ),
                "jeff",
                (
                    "That is why the battle right behind the leader can be so costly. "
                    "You spend tires trying to make a pass, and the leader gets to "
                    "keep stretching the rhythm."
                ),
                "sarah",
                (
                    "If that gap opens too much, someone may need strategy to get "
                    "back into the fight instead of trying to drive through it."
                ),
            ),
            "long_run_strategy": (
                "lead",
                (
                    "This is the part of a long green run where the race starts to "
                    "split into different games: pace, tire life, fuel, and traffic."
                ),
                "sarah",
                (
                    "The pit window becomes a moving target. Short-pitting can buy "
                    "lap time, but staying out can protect track position if a caution "
                    "falls the right way."
                ),
                "jeff",
                (
                    "And the drivers have to keep the car underneath them while all "
                    "that is happening. Strategy only works if the lap times stay solid."
                ),
            ),
            "short_track_patience": (
                "lead",
                (
                    f"At {track_name}, patience can be just as valuable as aggression. "
                    "You can catch someone quickly and still spend several laps trying "
                    "to finish the pass."
                ),
                "jeff",
                (
                    "That is the discipline of short-track racing. Use the bumper with "
                    "respect, keep the tires under you, and do not turn one lost corner "
                    "into a damaged race car."
                ),
                "sarah",
                (
                    "The teams are watching brake heat and tire abuse too. A driver "
                    "who overworks the car now may pay for it later in the run."
                ),
            ),
            "tire_heat": (
                "lead",
                "This run is long enough that tire heat starts to become part of the story.",
                "jeff",
                (
                    "You can feel it in the way a car changes direction. If the driver "
                    "has to wait longer to pick up throttle, that usually means the "
                    "tires are asking for help."
                ),
                "sarah",
                (
                    "That is when a crew chief starts thinking about air pressure, "
                    "track position, and whether the next stop needs a bigger swing."
                ),
            ),
            "road_course_rhythm": (
                "lead",
                (
                    f"On a road course, {track_name} is about rhythm as much as speed. "
                    "One missed apex can hurt the whole next straightaway."
                ),
                "jeff",
                (
                    "And the best drivers make it look calm. Brake in the same place, "
                    "rotate the car without abusing the rear tires, and keep every "
                    "exit clean."
                ),
                "sarah",
                (
                    "That consistency also protects the strategy. If lap times stay "
                    "stable, the team has more options when the window opens."
                ),
            ),
            "brake_management": (
                "lead",
                "Brake management is one of those quiet details that can decide a race.",
                "jeff",
                (
                    "Absolutely. If you overheat the brakes or start locking tires, "
                    "the lap time disappears in a hurry and passing zones become "
                    "survival zones."
                ),
                "sarah",
                (
                    "And from pit road, that changes how aggressive you can be. A car "
                    "that is hard on brakes may need track position before the problem "
                    "gets worse."
                ),
            ),
        }

        speaker_a, line_a, speaker_b, line_b, speaker_c, line_c = topics[topic]
        return (
            BoothConversationLine(
                message=line_a,
                speaker=speaker_a,
                delay_seconds=0.0,
                camera_target_car_idx=target_idx,
                participant_car_indices=participant_indices,
            ),
            BoothConversationLine(
                message=line_b,
                speaker=speaker_b,
                delay_seconds=0.2,
                camera_target_car_idx=target_idx,
                participant_car_indices=participant_indices,
            ),
            BoothConversationLine(
                message=line_c,
                speaker=speaker_c,
                delay_seconds=0.4,
                camera_target_car_idx=target_idx,
                participant_car_indices=participant_indices,
            ),
        )

    def find_action_target(self, ordered, driver_lookup):
        candidates = []
        for index, car in enumerate(ordered[1:16], start=1):
            gap = self.safe_float(
                car.get("Time")
                or car.get("Gap")
                or car.get("Interval")
                or car.get("TimeBehind")
            )
            if gap <= 0.0 or gap > 1.25:
                continue
            lead = ordered[index - 1]
            lead_idx = lead.get("CarIdx")
            chase_idx = car.get("CarIdx")
            if lead_idx is None or chase_idx is None:
                continue
            lead_label = self.driver_label(lead, driver_lookup)
            chase_label = self.driver_label(car, driver_lookup)
            # Prefer close battles nearer the front, but do not ignore a tight
            # mid-pack fight if it is the best live picture.
            score = gap + (index * 0.05)
            candidates.append(
                (
                    score,
                    chase_idx,
                    (lead_idx, chase_idx),
                    lead_label,
                    chase_label,
                    gap,
                )
            )

        if not candidates:
            return None
        _, chase_idx, participants, lead_label, chase_label, gap = min(
            candidates,
            key=lambda item: item[0],
        )
        return chase_idx, participants, lead_label, chase_label, gap

    def driver_label(self, car, driver_lookup):
        car_idx = car.get("CarIdx")
        driver = driver_lookup.get(car_idx, {})
        number = driver.get("number", "?")
        name = driver.get("name", f"car {car_idx}")
        return f"the {number} of {name}"

    def sorted_running_order(self, results):
        valid = [car for car in results or [] if car.get("CarIdx") is not None]

        def sort_key(car):
            position = self.safe_int(car.get("Position"), 999)
            if position <= 0:
                position = 999
            return position

        return sorted(valid, key=sort_key)

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
