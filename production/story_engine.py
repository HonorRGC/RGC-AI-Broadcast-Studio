import time
from dataclasses import dataclass, field
from typing import Dict, List, Optional


@dataclass
class DriverStoryState:
    car_idx: int
    driver_name: str
    car_number: str

    first_position: int = 0
    current_position: int = 0
    best_position: int = 0
    worst_position: int = 0

    positions_seen: List[int] = field(default_factory=list)
    last_story_time: float = 0.0


@dataclass
class RaceStory:
    story_type: str
    driver_name: str
    car_number: str
    car_idx: int
    headline: str
    summary: str
    importance: int
    position_change: int = 0


class StoryEngine:
    """
    Tracks longer race stories.

    This does not call the race like RaceBrain.
    This watches trends over time:
    - drivers charging forward
    - drivers fading
    - top-five breakthroughs
    - biggest movers
    """

    def __init__(self):
        self.driver_states: Dict[int, DriverStoryState] = {}
        self.story_cooldown_seconds = 45

    def update(self, results, driver_lookup, current_lap=0) -> List[RaceStory]:
        stories = []

        if not results:
            return stories

        sorted_results = sorted(
            results,
            key=lambda car: self.safe_int(car.get("Position", 999)),
        )

        for car in sorted_results:
            car_idx = car.get("CarIdx")

            if car_idx is None:
                continue

            position = self.safe_int(car.get("Position", 0))

            if position <= 0:
                continue

            driver_info = driver_lookup.get(car_idx, {})
            driver_name = driver_info.get("name", f"Car {car_idx}")
            car_number = driver_info.get("number", "?")

            state = self.get_or_create_state(
                car_idx=car_idx,
                driver_name=driver_name,
                car_number=car_number,
                position=position,
            )

            self.update_driver_state(state, position)

            story = self.evaluate_driver_story(state, current_lap)

            if story:
                stories.append(story)
                state.last_story_time = time.time()

        stories.sort(key=lambda item: item.importance, reverse=True)
        return stories

    def get_or_create_state(self, car_idx, driver_name, car_number, position):
        if car_idx not in self.driver_states:
            self.driver_states[car_idx] = DriverStoryState(
                car_idx=car_idx,
                driver_name=driver_name,
                car_number=car_number,
                first_position=position,
                current_position=position,
                best_position=position,
                worst_position=position,
            )

        state = self.driver_states[car_idx]
        state.driver_name = driver_name
        state.car_number = car_number

        return state

    def update_driver_state(self, state, position):
        state.current_position = position
        state.best_position = min(state.best_position, position)
        state.worst_position = max(state.worst_position, position)
        state.positions_seen.append(position)

        if len(state.positions_seen) > 30:
            state.positions_seen = state.positions_seen[-30:]

    def evaluate_driver_story(self, state, current_lap) -> Optional[RaceStory]:
        if not self.can_tell_story(state):
            return None

        total_gain = state.first_position - state.current_position
        total_loss = state.current_position - state.first_position

        recent_gain = self.recent_position_change(state)

        if state.current_position <= 5 and total_gain >= 5:
            return RaceStory(
                story_type="top_five_charge",
                driver_name=state.driver_name,
                car_number=state.car_number,
                car_idx=state.car_idx,
                headline=f"{state.driver_name} has charged into the top five.",
                summary=(
                    f"{state.driver_name} started {self.ordinal(state.first_position)} "
                    f"and has worked up to {self.ordinal(state.current_position)}."
                ),
                importance=9,
                position_change=total_gain,
            )

        if total_gain >= 8:
            return RaceStory(
                story_type="biggest_mover",
                driver_name=state.driver_name,
                car_number=state.car_number,
                car_idx=state.car_idx,
                headline=f"{state.driver_name} is one of the biggest movers in the field.",
                summary=(
                    f"The number {state.car_number} has gained {total_gain} positions "
                    f"since the start of this run."
                ),
                importance=8,
                position_change=total_gain,
            )

        if recent_gain >= 4:
            return RaceStory(
                story_type="momentum",
                driver_name=state.driver_name,
                car_number=state.car_number,
                car_idx=state.car_idx,
                headline=f"{state.driver_name} is building momentum.",
                summary=(
                    f"{state.driver_name} has gained {recent_gain} spots recently "
                    f"and is moving forward quickly."
                ),
                importance=7,
                position_change=recent_gain,
            )

        if total_loss >= 6:
            return RaceStory(
                story_type="fading_driver",
                driver_name=state.driver_name,
                car_number=state.car_number,
                car_idx=state.car_idx,
                headline=f"{state.driver_name} is fading back through the field.",
                summary=(
                    f"The number {state.car_number} has lost {total_loss} positions "
                    f"from where they started."
                ),
                importance=7,
                position_change=-total_loss,
            )

        return None

    def recent_position_change(self, state):
        if len(state.positions_seen) < 10:
            return 0

        old_position = state.positions_seen[0]
        new_position = state.positions_seen[-1]

        return old_position - new_position

    def can_tell_story(self, state):
        return time.time() - state.last_story_time >= self.story_cooldown_seconds

    def safe_int(self, value):
        try:
            return int(value)
        except Exception:
            return 0

    def ordinal(self, number):
        try:
            number = int(number)
        except Exception:
            return str(number)

        if 10 <= number % 100 <= 20:
            suffix = "th"
        else:
            suffix = {1: "st", 2: "nd", 3: "rd"}.get(number % 10, "th")

        return f"{number}{suffix}"