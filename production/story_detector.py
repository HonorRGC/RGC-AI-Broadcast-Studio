from dataclasses import dataclass
from typing import List

from helpers.position_formatter import PositionFormatter


@dataclass
class RaceStory:
    story_type: str
    driver_name: str
    car_number: str
    headline: str
    summary: str
    confidence: int
    priority: int


class StoryDetector:
    """
    StoryDetector looks at BroadcastContext and finds race stories.

    BroadcastContext remembers facts.
    StoryDetector decides which facts are becoming stories.
    BroadcastProducer decides what gets airtime.
    """

    def detect_stories(self, broadcast_context) -> List[RaceStory]:
        stories = []

        for driver_context in broadcast_context.drivers.values():
            biggest_mover_story = self.detect_biggest_mover(
                broadcast_context,
                driver_context,
            )

            if biggest_mover_story:
                stories.append(biggest_mover_story)

            top_five_story = self.detect_top_five_charge(driver_context)

            if top_five_story:
                stories.append(top_five_story)

            top_ten_story = self.detect_top_ten_charge(driver_context)

            if top_ten_story:
                stories.append(top_ten_story)

        stories.sort(key=lambda story: story.priority, reverse=True)
        return stories

    def detect_biggest_mover(self, broadcast_context, driver_context):
        if not broadcast_context.is_biggest_mover(driver_context):
            return None

        if driver_context.positions_gained < 5:
            return None

        current = PositionFormatter.ordinal(driver_context.current_position)
        started = PositionFormatter.ordinal(driver_context.starting_position)

        return RaceStory(
            story_type="biggest_mover",
            driver_name=driver_context.driver_name,
            car_number=driver_context.car_number,
            headline=f"{driver_context.driver_name} is the biggest mover of the race.",
            summary=(
                f"{driver_context.driver_name} started {started}, "
                f"now runs {current}, and has gained "
                f"{driver_context.positions_gained} positions."
            ),
            confidence=min(100, 70 + driver_context.positions_gained * 3),
            priority=9,
        )

    def detect_top_five_charge(self, driver_context):
        if driver_context.current_position <= 0:
            return None

        if driver_context.current_position > 5:
            return None

        if driver_context.positions_gained < 4:
            return None

        current = PositionFormatter.ordinal(driver_context.current_position)
        started = PositionFormatter.ordinal(driver_context.starting_position)

        return RaceStory(
            story_type="top_five_charge",
            driver_name=driver_context.driver_name,
            car_number=driver_context.car_number,
            headline=f"{driver_context.driver_name} has charged into the top five.",
            summary=(
                f"{driver_context.driver_name} started {started} "
                f"and has climbed all the way to {current}."
            ),
            confidence=min(100, 75 + driver_context.positions_gained * 2),
            priority=8,
        )

    def detect_top_ten_charge(self, driver_context):
        if driver_context.current_position <= 0:
            return None

        if driver_context.current_position > 10:
            return None

        if driver_context.positions_gained < 5:
            return None

        current = PositionFormatter.ordinal(driver_context.current_position)
        started = PositionFormatter.ordinal(driver_context.starting_position)

        return RaceStory(
            story_type="top_ten_charge",
            driver_name=driver_context.driver_name,
            car_number=driver_context.car_number,
            headline=f"{driver_context.driver_name} has worked into the top ten.",
            summary=(
                f"{driver_context.driver_name} started {started}, "
                f"now runs {current}, and has gained "
                f"{driver_context.positions_gained} positions."
            ),
            confidence=min(100, 70 + driver_context.positions_gained * 2),
            priority=7,
        )