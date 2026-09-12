from dataclasses import dataclass
from typing import List


@dataclass
class BattleStory:
    story_type: str
    headline: str
    summary: str
    importance: int

    lead_driver_name: str
    lead_car_number: str
    lead_car_idx: int

    chasing_driver_name: str
    chasing_car_number: str
    chasing_car_idx: int

    position: int
    gap: float


class BattleDetector:
    def __init__(self):
        self.minimum_valid_gap = 0.05
        self.lead_battle_gap = 0.50
        self.top_five_battle_gap = 0.75
        self.top_ten_battle_gap = 1.00

    def analyze(self, results, driver_lookup) -> List[BattleStory]:
        battles = []

        if not results:
            return battles

        sorted_results = sorted(
            results,
            key=lambda car: self.safe_int(car.get("Position", 999)),
        )

        for index in range(len(sorted_results) - 1):
            lead_car = sorted_results[index]
            chasing_car = sorted_results[index + 1]

            position = self.safe_int(lead_car.get("Position", 999))
            gap = self.safe_float(chasing_car.get("Time", 999.0))

            if gap < self.minimum_valid_gap:
                continue

            if position <= 1 and gap <= self.lead_battle_gap:
                battles.append(
                    self.build_battle_story(
                        lead_car,
                        chasing_car,
                        driver_lookup,
                        position,
                        gap,
                        "battle_for_lead",
                        "Battle for the lead is heating up.",
                        10,
                    )
                )

            elif position <= 5 and gap <= self.top_five_battle_gap:
                battles.append(
                    self.build_battle_story(
                        lead_car,
                        chasing_car,
                        driver_lookup,
                        position,
                        gap,
                        "battle_for_top_five",
                        "There is a close fight inside the top five.",
                        8,
                    )
                )

            elif position <= 10 and gap <= self.top_ten_battle_gap:
                battles.append(
                    self.build_battle_story(
                        lead_car,
                        chasing_car,
                        driver_lookup,
                        position,
                        gap,
                        "battle_for_top_ten",
                        "There is a close battle inside the top ten.",
                        6,
                    )
                )

        battles.sort(key=lambda item: item.importance, reverse=True)
        return battles

    def build_battle_story(
        self,
        lead_car,
        chasing_car,
        driver_lookup,
        position,
        gap,
        story_type,
        headline,
        importance,
    ):
        lead_car_idx = lead_car.get("CarIdx")
        chasing_car_idx = chasing_car.get("CarIdx")

        lead_info = driver_lookup.get(lead_car_idx, {})
        chasing_info = driver_lookup.get(chasing_car_idx, {})

        lead_name = lead_info.get("name", f"Car {lead_car_idx}")
        lead_number = lead_info.get("number", "?")

        chasing_name = chasing_info.get("name", f"Car {chasing_car_idx}")
        chasing_number = chasing_info.get("number", "?")

        position_text = self.ordinal(position)
        variants = [
            (
                f"This is a good fight for {position_text}. {lead_name} in the "
                f"number {lead_number} has {chasing_name} in the number "
                f"{chasing_number} close enough that the camera should stay with it."
            ),
            (
                f"Not every good race is for the lead. Around {position_text}, "
                f"{lead_name} in the number {lead_number} and {chasing_name} in "
                f"the number {chasing_number} are putting together a nice battle."
            ),
            (
                f"{chasing_name} in the number {chasing_number} is keeping "
                f"{lead_name} in the number {lead_number} honest for "
                f"{position_text}; the gap is about {gap:.2f} seconds."
            ),
            (
                f"Let's put some attention on {position_text}. {lead_name} in "
                f"the number {lead_number} and {chasing_name} in the number "
                f"{chasing_number} have been close enough to make this worth watching."
            ),
            (
                f"The fight around {position_text} has some life to it. "
                f"{chasing_name} in the number {chasing_number} is hanging with "
                f"{lead_name} in the number {lead_number} without needing this "
                "to become a full strategy lesson."
            ),
        ]
        summary = variants[
            (
                self.safe_int(lead_car_idx)
                + self.safe_int(chasing_car_idx)
                + self.safe_int(position)
            )
            % len(variants)
        ]

        return BattleStory(
            story_type=story_type,
            headline=headline,
            summary=summary,
            importance=importance,
            lead_driver_name=lead_name,
            lead_car_number=lead_number,
            lead_car_idx=lead_car_idx,
            chasing_driver_name=chasing_name,
            chasing_car_number=chasing_number,
            chasing_car_idx=chasing_car_idx,
            position=position,
            gap=gap,
        )

    def safe_int(self, value):
        try:
            return int(value)
        except Exception:
            return 999

    def safe_float(self, value):
        try:
            return float(value)
        except Exception:
            return 999.0

    @staticmethod
    def ordinal(value):
        try:
            number = int(value)
        except (TypeError, ValueError):
            return "that position"
        if 10 <= number % 100 <= 20:
            suffix = "th"
        else:
            suffix = {1: "st", 2: "nd", 3: "rd"}.get(number % 10, "th")
        return f"{number}{suffix}"
