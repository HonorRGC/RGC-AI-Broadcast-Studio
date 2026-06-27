import time
from dataclasses import dataclass, field
from typing import Dict, List, Optional

from helpers.position_formatter import PositionFormatter


@dataclass
class DriverStoryState:
    driver_name: str
    car_number: str = "?"
    starting_position: int = 0
    current_position: int = 0
    best_position: int = 999
    total_passes: int = 0
    last_mentioned_at: float = 0.0
    recent_events: List[object] = field(default_factory=list)


class BroadcastProducer:
    """
    The Broadcast Producer decides what deserves airtime.

    It does not announce.
    It does not generate voice.
    It decides whether an event should be sent to the booth.
    """

    def __init__(self):
        self.driver_states: Dict[str, DriverStoryState] = {}

        self.driver_cooldown_seconds = 25
        self.minimum_importance = 6
        self.story_threshold_passes = 3
        self.max_recent_events = 5

    def review_event(self, event):
        if event is None:
            return None

        driver_key = self.get_driver_key(event)
        state = self.get_or_create_driver_state(driver_key, event)

        self.update_driver_state(state, event)

        if self.should_air_now(event, state):
            self.mark_mentioned(state)
            self.enrich_event_message(event, state)
            return event

        return None

    def get_driver_key(self, event):
        return getattr(event, "driver_name", "unknown_driver")

    def get_or_create_driver_state(self, driver_key, event):
        if driver_key not in self.driver_states:
            self.driver_states[driver_key] = DriverStoryState(
                driver_name=getattr(event, "driver_name", "Unknown Driver"),
                car_number=getattr(event, "car_number", "?"),
                starting_position=getattr(event, "starting_position", 0),
                current_position=getattr(event, "new_position", 0),
                best_position=getattr(event, "new_position", 999),
            )

        return self.driver_states[driver_key]

    def update_driver_state(self, state, event):
        state.driver_name = getattr(event, "driver_name", state.driver_name)
        state.car_number = getattr(event, "car_number", state.car_number)

        starting_position = getattr(event, "starting_position", 0)
        if starting_position and state.starting_position == 0:
            state.starting_position = starting_position

        new_position = getattr(event, "new_position", state.current_position)
        state.current_position = new_position

        if new_position:
            state.best_position = min(state.best_position, new_position)

        state.total_passes = max(
            state.total_passes,
            getattr(event, "passes_made", state.total_passes),
        )

        state.recent_events.append(event)

        if len(state.recent_events) > self.max_recent_events:
            state.recent_events.pop(0)

    def should_air_now(self, event, state):
        importance = getattr(event, "importance", 0)
        new_position = getattr(event, "new_position", 999)

        if importance >= 10:
            return True

        if new_position == 1:
            return True

        if new_position <= 5 and importance >= 8:
            return self.driver_is_off_cooldown(state)

        if self.has_story_built(state) and self.driver_is_off_cooldown(state):
            return True

        if importance >= self.minimum_importance and self.driver_is_off_cooldown(state):
            return True

        return False

    def has_story_built(self, state):
        if len(state.recent_events) >= self.story_threshold_passes:
            return True

        if state.starting_position and state.current_position:
            positions_gained = state.starting_position - state.current_position
            return positions_gained >= 5

        return False

    def driver_is_off_cooldown(self, state):
        return time.time() - state.last_mentioned_at >= self.driver_cooldown_seconds

    def mark_mentioned(self, state):
        state.last_mentioned_at = time.time()

    def enrich_event_message(self, event, state):
        current = PositionFormatter.ordinal(state.current_position)
        started = PositionFormatter.ordinal(state.starting_position)
        old_position = PositionFormatter.ordinal(getattr(event, "old_position", 0))

        positions_gained = 0
        if state.starting_position and state.current_position:
            positions_gained = state.starting_position - state.current_position

        if getattr(event, "new_position", 999) == 1:
            event.message = (
                f"{state.driver_name} has taken the race lead. "
                f"He started {started} and is now out front."
            )
            return

        if positions_gained >= 5:
            event.message = (
                f"{state.driver_name} is becoming one of the stories of this race. "
                f"He started {started}, has worked his way up to {current}, "
                f"and has gained {positions_gained} positions."
            )
            return

        if len(state.recent_events) >= self.story_threshold_passes:
            event.message = (
                f"{state.driver_name} is building momentum. "
                f"He has made {len(state.recent_events)} recent position gains "
                f"and now runs {current}."
            )
            return

        event.message = (
            f"{state.driver_name} moves from {old_position} to {current}."
        )