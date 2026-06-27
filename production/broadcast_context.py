import time
from dataclasses import dataclass, field
from typing import Dict, List, Optional

from helpers.position_formatter import PositionFormatter


@dataclass
class DriverContext:
    driver_name: str
    car_number: str = "?"

    starting_position: int = 0
    current_position: int = 0
    previous_position: int = 0
    best_position: int = 999
    worst_position: int = 0

    passes_made: int = 0
    passes_lost: int = 0
    positions_gained: int = 0

    last_mentioned_at: float = 0.0
    last_mentioned_lap: int = 0

    recent_position_history: List[int] = field(default_factory=list)
    current_story: str = ""


class BroadcastContext:
    """
    BroadcastContext is the memory of the current race.

    It tracks driver movement, biggest movers, recent trends,
    and story information for the Broadcast Producer.
    """

    def __init__(self):
        self.drivers: Dict[str, DriverContext] = {}
        self.biggest_mover_key: Optional[str] = None
        self.max_history = 8

    def update_from_event(self, event):
        if event is None:
            return None

        driver_key = self.get_driver_key(event)
        context = self.get_or_create_driver(driver_key, event)

        context.driver_name = getattr(event, "driver_name", context.driver_name)
        context.car_number = getattr(event, "car_number", context.car_number)

        context.previous_position = getattr(
            event,
            "old_position",
            context.previous_position,
        )

        context.current_position = getattr(
            event,
            "new_position",
            context.current_position,
        )

        starting_position = getattr(event, "starting_position", 0)
        if starting_position and context.starting_position == 0:
            context.starting_position = starting_position

        if context.current_position:
            context.best_position = min(context.best_position, context.current_position)

            if context.worst_position == 0:
                context.worst_position = context.current_position
            else:
                context.worst_position = max(context.worst_position, context.current_position)

        context.passes_made = max(
            context.passes_made,
            getattr(event, "passes_made", context.passes_made),
        )

        context.passes_lost = max(
            context.passes_lost,
            getattr(event, "passes_lost", context.passes_lost),
        )

        if context.starting_position and context.current_position:
            context.positions_gained = context.starting_position - context.current_position

        context.recent_position_history.append(context.current_position)

        if len(context.recent_position_history) > self.max_history:
            context.recent_position_history.pop(0)

        self.update_biggest_mover()
        self.update_story(context)

        return context

    def get_driver_key(self, event):
        car_number = getattr(event, "car_number", "?")
        driver_name = getattr(event, "driver_name", "Unknown Driver")
        return f"{car_number}:{driver_name}"

    def get_or_create_driver(self, driver_key, event):
        if driver_key not in self.drivers:
            self.drivers[driver_key] = DriverContext(
                driver_name=getattr(event, "driver_name", "Unknown Driver"),
                car_number=getattr(event, "car_number", "?"),
                starting_position=getattr(event, "starting_position", 0),
                current_position=getattr(event, "new_position", 0),
                previous_position=getattr(event, "old_position", 0),
                best_position=getattr(event, "new_position", 999),
            )

        return self.drivers[driver_key]

    def update_biggest_mover(self):
        best_key = None
        best_gain = 0

        for key, context in self.drivers.items():
            if context.positions_gained > best_gain:
                best_gain = context.positions_gained
                best_key = key

        self.biggest_mover_key = best_key

    def update_story(self, context):
        if context.current_position == 1:
            context.current_story = "race leader"
            return

        if self.is_biggest_mover(context):
            context.current_story = "biggest mover"
            return

        if context.positions_gained >= 8:
            context.current_story = "major charge through the field"
            return

        if context.positions_gained >= 5:
            context.current_story = "quietly moving forward"
            return

        if context.current_position <= 5:
            context.current_story = "top five contender"
            return

        if context.current_position <= 10:
            context.current_story = "top ten runner"
            return

        context.current_story = "race traffic"

    def is_biggest_mover(self, context):
        if not self.biggest_mover_key:
            return False

        driver_key = f"{context.car_number}:{context.driver_name}"
        return driver_key == self.biggest_mover_key and context.positions_gained >= 3

    def mark_mentioned(self, context, lap=0):
        context.last_mentioned_at = time.time()
        context.last_mentioned_lap = lap

    def seconds_since_mentioned(self, context):
        if context.last_mentioned_at == 0:
            return 9999

        return time.time() - context.last_mentioned_at

    def build_context_summary(self, context):
        started = PositionFormatter.ordinal(context.starting_position)
        current = PositionFormatter.ordinal(context.current_position)
        previous = PositionFormatter.ordinal(context.previous_position)

        summary = [
            f"{context.driver_name} drives the number {context.car_number}.",
            f"He started {started} and now runs {current}.",
            f"He just moved from {previous} to {current}.",
        ]

        if context.positions_gained > 0:
            summary.append(f"He has gained {context.positions_gained} positions from the start.")

        if context.passes_made > 0:
            summary.append(f"He has made {context.passes_made} passes.")

        if context.current_story:
            summary.append(f"Current story: {context.current_story}.")

        if self.is_biggest_mover(context):
            summary.append("He is currently the biggest mover in the field.")

        return " ".join(summary)