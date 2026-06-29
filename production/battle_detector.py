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

        summary = (
            f"{chasing_name} in the number {chasing_number} is right there "
            f"behind {lead_name} in the number {lead_number}, with the gap "
            f"around {gap:.2f} seconds."
        )

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