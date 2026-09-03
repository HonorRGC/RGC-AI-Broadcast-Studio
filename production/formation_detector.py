from dataclasses import dataclass

from production.track_style import is_true_pack_drafting_track


@dataclass(frozen=True)
class FormationStory:
    story_type: str
    headline: str
    summary: str
    importance: int
    primary_car_idx: int | None = None
    participant_car_indices: tuple[int, ...] = ()


class FormationDetector:
    """Detects race-pack formations from timing/scoring geometry.

    This does not claim inside/outside lane unless we can truly know it. It
    focuses on reliable broadcast language: single-file train, two-wide pack,
    three-wide pressure, and lead-pack compression.
    """

    CLOSE_GAP = 0.0060
    OVERLAP_GAP = 0.0014
    PACK_GAP = 0.0180
    MULTI_PACK_GAP = 0.0350
    MULTI_PACK_MIN_SIZE = 3

    def __init__(self):
        self.last_story_type = ""
        self.last_story_lap = -999
        self.min_laps_between_calls = 4
        self.last_multi_pack_lap = -999
        self.multi_pack_cooldown_laps = 8

    def analyze(
        self,
        results,
        driver_lookup,
        lap_dist_pct_status,
        pit_road_status=None,
        current_lap=0,
        track_info=None,
    ):
        if current_lap < 1 or not results or not lap_dist_pct_status:
            return []

        cars = self.ordered_active_cars(results, lap_dist_pct_status, pit_road_status)
        if len(cars) < 4:
            return []

        draft_pack_track = (
            True if track_info is None else is_true_pack_drafting_track(track_info)
        )

        if draft_pack_track:
            multi_pack_story = self.detect_multiple_packs(
                cars,
                driver_lookup,
                current_lap,
            )
            if multi_pack_story:
                return [multi_pack_story]

        lead_pack = self.lead_pack(cars)
        if len(lead_pack) < 4:
            return []

        story = (
            self.detect_three_wide(lead_pack, driver_lookup, draft_pack_track)
            or self.detect_two_wide(lead_pack, draft_pack_track)
            or self.detect_single_file(lead_pack, draft_pack_track)
            or self.detect_compressed_pack(lead_pack)
        )
        if not story:
            return []

        if (
            story.story_type == self.last_story_type
            and current_lap - self.last_story_lap < self.min_laps_between_calls
        ):
            return []

        self.last_story_type = story.story_type
        self.last_story_lap = current_lap
        return [story]

    def detect_multiple_packs(self, cars, driver_lookup, current_lap):
        if current_lap - self.last_multi_pack_lap < self.multi_pack_cooldown_laps:
            return None

        packs = self.split_packs(cars)
        if len(packs) < 2:
            return None

        lead_pack = packs[0]
        second_pack = packs[1]
        if (
            len(lead_pack) < self.MULTI_PACK_MIN_SIZE
            or len(second_pack) < self.MULTI_PACK_MIN_SIZE
        ):
            return None

        separation = self.gap(lead_pack[-1], second_pack[0])
        if separation < self.MULTI_PACK_GAP:
            return None

        second_leader = second_pack[0]
        second_leader_name = self.name(driver_lookup, second_leader["car_idx"])
        second_position = second_leader.get("position", 0)
        gap_text = self.pack_gap_text(second_leader)
        pack_count_text = (
            "two draft packs"
            if len(packs) == 2
            else f"{min(len(packs), 3)} draft packs"
        )
        summary = (
            f"The field has split into {pack_count_text}. The lead pack has "
            f"{len(lead_pack)} cars, and the second pack starts around "
            f"{self.ordinal(second_position)} with {second_leader_name}"
        )
        if gap_text:
            summary += f", about {gap_text} behind the front group"
        summary += (
            ". That second group needs to get organized and work together, "
            "because if they race each other too hard the lead pack can keep "
            "stretching the gap."
        )

        self.last_multi_pack_lap = current_lap
        return FormationStory(
            story_type="formation_multiple_packs",
            headline="Multiple draft packs have formed.",
            summary=summary,
            importance=9,
            primary_car_idx=second_leader["car_idx"],
            participant_car_indices=tuple(
                car["car_idx"] for car in (lead_pack + second_pack)[:10]
            ),
        )

    def detect_three_wide(self, cars, driver_lookup, draft_pack_track=True):
        for index in range(len(cars) - 2):
            group = cars[index : index + 3]
            if self.spread(group) > self.OVERLAP_GAP:
                continue
            names = [self.name(driver_lookup, car["car_idx"]) for car in group]
            summary = (
                f"{names[0]}, {names[1]}, and {names[2]} are packed tightly "
                "together in the draft. That is pressure building in the pack."
                if draft_pack_track
                else (
                    f"{names[0]}, {names[1]}, and {names[2]} are packed tightly "
                    "together on track with very little room to sort it out."
                )
            )
            return FormationStory(
                story_type="formation_three_wide",
                headline="Three-car pressure in the pack.",
                summary=summary,
                importance=10,
                primary_car_idx=group[1]["car_idx"],
                participant_car_indices=tuple(car["car_idx"] for car in group),
            )
        return None

    def detect_two_wide(self, cars, draft_pack_track=True):
        overlap_pairs = 0
        participants = []
        for first, second in zip(cars, cars[1:]):
            if self.gap(first, second) <= self.OVERLAP_GAP:
                overlap_pairs += 1
                participants.extend([first["car_idx"], second["car_idx"]])
        if overlap_pairs < 2:
            return None
        unique_participants = tuple(dict.fromkeys(participants))
        summary = (
            f"The front pack is doubled up with {len(cars)} cars covered "
            "by just a few car lengths. This is where the draft can start "
            "to create big runs."
            if draft_pack_track
            else (
                f"The front group is doubled up with {len(cars)} cars covered "
                "by just a few car lengths. Track position is getting tense, "
                "and clean corner exits matter more than forcing the issue."
            )
        )
        return FormationStory(
            story_type="formation_two_wide",
            headline="The lead pack is doubled up.",
            summary=summary,
            importance=9,
            primary_car_idx=unique_participants[0] if unique_participants else None,
            participant_car_indices=unique_participants[:8],
        )

    def detect_single_file(self, cars, draft_pack_track=True):
        close_pairs = [
            self.gap(first, second)
            for first, second in zip(cars, cars[1:])
            if self.gap(first, second) <= self.CLOSE_GAP
        ]
        if len(close_pairs) < min(len(cars) - 1, 5):
            return None
        if any(
            self.gap(first, second) <= self.OVERLAP_GAP
            for first, second in zip(cars, cars[1:])
        ):
            return None
        summary = (
            f"The front {len(cars)} have settled into one long draft train. "
            "It is calm for the moment, but this kind of single-file run can "
            "turn into a scramble once someone decides to jump out of line."
            if draft_pack_track
            else (
                f"The front {len(cars)} have settled into a single-file rhythm. "
                "It is calm for the moment, but traffic, tire falloff, and corner "
                "exit can still open the door for a move."
            )
        )
        return FormationStory(
            story_type="formation_single_file",
            headline="The lead pack is single file.",
            summary=summary,
            importance=7,
            primary_car_idx=cars[0]["car_idx"],
            participant_car_indices=tuple(car["car_idx"] for car in cars[:8]),
        )

    def detect_compressed_pack(self, cars):
        if self.spread(cars[: min(len(cars), 8)]) > self.PACK_GAP:
            return None
        return FormationStory(
            story_type="formation_compressed_pack",
            headline="The lead pack is tightening up.",
            summary=(
                f"The lead pack is tightening up with {len(cars)} cars close together. "
                "At this kind of spacing, one mistimed run can shuffle the order quickly."
            ),
            importance=8,
            primary_car_idx=cars[0]["car_idx"],
            participant_car_indices=tuple(car["car_idx"] for car in cars[:8]),
        )

    def lead_pack(self, cars):
        pack = [cars[0]]
        for previous, current in zip(cars, cars[1:]):
            if self.gap(previous, current) > self.PACK_GAP:
                break
            pack.append(current)
        return pack

    def split_packs(self, cars):
        packs = []
        current_pack = []
        for car in cars:
            if not current_pack:
                current_pack = [car]
                continue
            previous = current_pack[-1]
            if self.gap(previous, car) <= self.PACK_GAP:
                current_pack.append(car)
            else:
                if current_pack:
                    packs.append(current_pack)
                current_pack = [car]
        if current_pack:
            packs.append(current_pack)
        return packs

    def ordered_active_cars(self, results, distances, pit_status):
        pit_status = pit_status or []
        zero_based = any(self.integer(car.get("Position"), 999) == 0 for car in results)
        cars = []
        for car in results:
            car_idx = self.integer(car.get("CarIdx"), -1)
            if car_idx < 0 or car_idx >= len(distances):
                continue
            if car_idx < len(pit_status) and pit_status[car_idx]:
                continue
            try:
                distance = float(distances[car_idx]) % 1.0
            except (TypeError, ValueError):
                continue
            position = self.integer(car.get("Position"), 999) + (1 if zero_based else 0)
            lap = self.integer(car.get("LapsComplete", car.get("Lap", 0)), 0)
            if position <= 0 or position >= 999:
                continue
            cars.append(
                {
                    "car_idx": car_idx,
                    "position": position,
                    "lap": lap,
                    "distance": distance,
                    "time": self.safe_float(
                        car.get("Time", car.get("Gap", car.get("Interval", 0.0))),
                        0.0,
                    ),
                }
            )
        return sorted(cars, key=lambda car: car["position"])

    def pack_gap_text(self, pack_leader):
        time_gap = self.safe_float(pack_leader.get("time", 0.0), 0.0)
        if 1.0 <= time_gap < 120.0:
            return f"{time_gap:.1f} seconds"
        return ""

    def spread(self, cars):
        return max(self.gap(first, second) for first in cars for second in cars)

    @staticmethod
    def gap(first, second):
        difference = abs(first["distance"] - second["distance"])
        return min(difference, 1.0 - difference)

    @staticmethod
    def name(driver_lookup, car_idx):
        return driver_lookup.get(car_idx, {}).get("name", f"Car {car_idx}")

    @staticmethod
    def integer(value, default):
        try:
            return int(value)
        except (TypeError, ValueError):
            return default

    @staticmethod
    def safe_float(value, default):
        try:
            return float(value)
        except (TypeError, ValueError):
            return default

    @staticmethod
    def ordinal(position):
        try:
            position = int(position)
        except (TypeError, ValueError):
            return "that spot"
        if 10 <= position % 100 <= 20:
            suffix = "th"
        else:
            suffix = {1: "st", 2: "nd", 3: "rd"}.get(position % 10, "th")
        return f"{position}{suffix}"
