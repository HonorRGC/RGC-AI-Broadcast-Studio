import time


class BroadcastStoryProducer:
    """Turns raw telemetry stories into broadcast assignments with context.

    The lower layers find facts. This layer explains why those facts are worth
    airing and gives OpenAI a more human broadcast angle.
    """

    def __init__(self):
        self.driver_angle_history = {}
        self.driver_start_position_mentions = {}
        self.start_position_cooldown_seconds = 20 * 60

    def frame(self, item, race_state=None, race_knowledge=None):
        if not item:
            return item

        notes = []
        notes.extend(self.phase_notes(race_state, race_knowledge))

        story_type = str(getattr(item, "story_type", "") or "")
        driver_key = self.driver_key(item)
        angle = self.choose_angle(item, race_state, race_knowledge)

        if angle:
            setattr(item, "broadcast_angle", angle)
            notes.append(f"Use this broadcast angle without saying the label out loud: {angle}.")

        if story_type in {"biggest_mover", "top_five_charge", "momentum"}:
            notes.append(
                "Do not make this only a position-gain read. Explain the race "
                "story: pace, patience, traffic, long-run strength, or pressure."
            )
            if not self.can_mention_start_position(driver_key):
                notes.append(
                    "Avoid repeating where this driver started. That fact has "
                    "already been used recently."
                )
            else:
                self.driver_start_position_mentions[driver_key] = time.time()

        if story_type == "fading_driver":
            notes.append(
                "Frame this as a developing concern, not just a driver losing spots. "
                "Mention possible handling, tire falloff, traffic, or rhythm only as possibilities."
            )

        if story_type in {"battle_for_lead", "lead_change", "live_pass_clear"}:
            notes.append(
                "Make the leader story feel important. Discuss pressure, gap, "
                "clean air, lap traffic, or what the challenger must do next."
            )

        if story_type in {"live_side_by_side", "live_three_wide", "live_pass_clear"}:
            notes.append(
                "This is a live on-track battle read. If the summary says the "
                "spot is not settled, do not declare the pass complete. If the "
                "summary says the pass looks clear, call it naturally as an "
                "on-track move without mentioning scoring systems or internal "
                "confidence language."
            )

        if story_type.startswith("formation_"):
            notes.append(
                "This is a pack-formation call. Do not claim inside or outside "
                "lane unless explicitly stated. Describe the pack shape, tension, "
                "draft momentum, and why this can create runs or risk."
            )

        if getattr(item, "category", "") == "pit_strategy":
            notes.append(
                "Focus on consequence: timing, track position, tire/fuel window, "
                "or whether this puts the driver on a different strategy."
            )

        if story_type in {"race_recovery", "race_fade", "pit_cycle_memory"}:
            notes.append(
                "This is a race-long storyline. Connect what happened earlier "
                "to what it means now, and avoid making it sound like a fresh "
                "single-lap position update."
            )

        if self.recently_used_angle(driver_key, angle):
            notes.append(
                "Use a different sentence structure and do not repeat the prior "
                "angle for this driver."
            )
        self.remember_angle(driver_key, angle)

        setattr(item, "producer_notes", notes)
        return item

    def phase_notes(self, race_state, race_knowledge=None):
        notes = []
        track_profile = (race_knowledge or {}).get("track_profile") or {}
        if track_profile.get("style") == "road_course":
            notes.append(
                "Track style: road course. Prefer braking zones, apexes, exits, "
                "curbs, traffic, pit windows, undercut/overcut, and local mistakes. "
                "Avoid oval pack-draft or freight-train wording."
            )
        if not race_state:
            return notes
        moment = getattr(getattr(race_state, "moment", None), "value", "")
        laps_remaining = self.safe_int(getattr(race_state, "laps_remaining", 0))
        green_lap_count = self.safe_int(getattr(race_state, "green_lap_count", 0))

        if moment == "LONG_GREEN_RUN":
            notes.extend([
                "Race phase: long green-flag run. Connect the story to tire wear, rhythm, traffic, or strategy if it fits."
            ])
            return notes
        if moment in {"CLOSING_LAPS", "WHITE_FLAG", "OVERTIME"}:
            notes.extend([
                f"Race phase: closing laps with {laps_remaining} to go. Prioritize urgency, leaders, and realistic winning chances."
            ])
            return notes
        if moment == "CAUTION":
            notes.extend([
                "Race phase: caution. Focus on reset, pit decisions, damage, restart order, and who benefits."
            ])
            return notes
        if moment == "GREEN" and green_lap_count <= 3:
            notes.extend([
                "Race phase: early green or restart. Focus on launch, lanes, aggression, and settling into rhythm."
            ])
        return notes

    def choose_angle(self, item, race_state, race_knowledge):
        story_type = str(getattr(item, "story_type", "") or "")
        priority = self.safe_int(getattr(item, "priority", 0))

        if story_type == "top_five_charge":
            return "driver has turned pace into track position near the front"
        if story_type == "biggest_mover":
            return "quiet charge through traffic"
        if story_type == "momentum":
            return "recent pace swing"
        if story_type == "fading_driver":
            return "car or run trend is going the wrong direction"
        if story_type in {"battle_for_lead", "lead_change"}:
            return "fight for control of the race"
        if story_type in {"battle_for_top_five", "battle_for_top_ten", "side_by_side", "three_car_battle", "live_side_by_side", "live_pass_clear"}:
            return "localized battle with consequences"
        if story_type == "live_three_wide":
            return "three-wide live battle building"
        summary = str(getattr(item, "summary", "") or "").lower()
        is_draft_summary = "draft" in summary
        if story_type == "formation_three_wide":
            return (
                "three-wide pressure in the draft"
                if is_draft_summary
                else "three-wide pressure for track position"
            )
        if story_type == "formation_two_wide":
            return (
                "pack is doubled up and momentum is building"
                if is_draft_summary
                else "front group is doubled up and track position is tense"
            )
        if story_type == "formation_single_file":
            return (
                "single-file draft train setting up the next move"
                if is_draft_summary
                else "single-file rhythm as tire falloff and traffic build"
            )
        if story_type == "formation_compressed_pack":
            return "lead pack compression"
        if story_type == "race_recovery":
            return "driver has rebuilt the race after losing track position"
        if story_type == "race_fade":
            return "earlier strength has turned into a developing concern"
        if story_type == "pit_cycle_memory":
            return "pit cycle has shaped this driver's race"
        if getattr(item, "category", "") == "pit_strategy":
            return "strategy consequence"
        if priority >= 9:
            return "high-priority race development"
        return "race context update"

    def can_mention_start_position(self, driver_key):
        if not driver_key:
            return True
        last = self.driver_start_position_mentions.get(driver_key, 0.0)
        return time.time() - last >= self.start_position_cooldown_seconds

    def recently_used_angle(self, driver_key, angle):
        if not driver_key or not angle:
            return False
        return self.driver_angle_history.get(driver_key) == angle

    def remember_angle(self, driver_key, angle):
        if driver_key and angle:
            self.driver_angle_history[driver_key] = angle

    @staticmethod
    def driver_key(item):
        name = str(getattr(item, "driver_name", "") or "").casefold().strip()
        number = str(getattr(item, "car_number", "") or "").strip()
        return name or number

    @staticmethod
    def safe_int(value, default=0):
        try:
            return int(value)
        except (TypeError, ValueError):
            return default
