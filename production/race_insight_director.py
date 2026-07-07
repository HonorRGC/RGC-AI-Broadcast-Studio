from dataclasses import dataclass
import random


@dataclass(frozen=True)
class RaceInsight:
    message: str
    category: str
    speaker: str = "jeff"
    priority: int = 7


class RaceInsightDirector:
    """Adds non-repeating racing knowledge at natural breaks."""

    def __init__(self, seed=None):
        self.random = random.Random(seed)
        self.used_topics = set()
        self.last_green_insight_lap = 0

    def long_green_insight(self, race_state, current_lap):
        if not race_state or not race_state.is_green:
            return None
        if race_state.green_lap_count < 12:
            return None
        if race_state.laps_remaining and race_state.laps_remaining <= 10:
            return None
        if self.last_green_insight_lap and current_lap - self.last_green_insight_lap < 8:
            return None

        candidates = [
            (
                "tire_wear_entry",
                "One thing to watch on a long green run is tire wear on corner entry. "
                "The drivers who can roll out of the throttle smoothly and avoid sliding "
                "the front tires are usually the ones who still have speed later in the run.",
            ),
            (
                "tire_wear_exit",
                "Tire management is not just about going slower. It is about asking less "
                "from the tire at the wrong time. A smooth throttle pickup off the corner "
                "can save the rear tires and keep the car from getting loose late in a run.",
            ),
            (
                "fuel_save_lift",
                "Fuel saving can be subtle in these races. A driver can lift a little earlier "
                "at the end of the straightaway, roll speed through the center, and save fuel "
                "without giving up much lap time if they keep the car free and tidy.",
            ),
            (
                "fuel_save_draft",
                "If fuel mileage becomes part of this, the draft matters. Tucking in behind "
                "another car can let a driver breathe the throttle slightly, save a little fuel, "
                "and still keep touch with the pack.",
            ),
        ]
        insight = self.pick_unused(candidates)
        if not insight:
            return None

        topic, message = insight
        self.used_topics.add(topic)
        self.last_green_insight_lap = current_lap
        return RaceInsight(
            message=message,
            category=f"race_insight:{topic}",
        )

    def caution_insight(self, race_state):
        if not race_state or not race_state.is_caution:
            return None
        if race_state.laps_remaining <= 0 or race_state.laps_remaining > 10:
            return None

        candidates = [
            (
                "short_run_tires",
                "With a short run to the finish, tire conservation is not the story anymore. "
                "This is closer to a sprint, where clean air, restart execution, and getting "
                "through the gears can matter more than saving anything for later.",
            ),
            (
                "restart_aggression",
                "On a restart this late, the balance changes. Drivers still need to keep it "
                "clean, but nobody is thinking about a 30-lap run from here. Track position "
                "and momentum are everything.",
            ),
        ]
        insight = self.pick_unused(candidates)
        if not insight:
            return None

        topic, message = insight
        self.used_topics.add(topic)
        return RaceInsight(
            message=message,
            category=f"race_insight:{topic}",
            priority=8,
        )

    def pick_unused(self, candidates):
        available = [
            candidate for candidate in candidates
            if candidate[0] not in self.used_topics
        ]
        if not available:
            return None
        return self.random.choice(available)

