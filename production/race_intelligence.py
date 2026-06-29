from dataclasses import dataclass, field
from typing import Dict, List, Optional

from production.story_engine import StoryEngine, RaceStory
from production.story_manager import StoryManager, ManagedStory
from production.battle_detector import BattleDetector, BattleStory
from production.driver_memory import DriverMemory
from production.momentum_tracker import MomentumTracker, MomentumProfile


@dataclass
class DriverIntelligence:
    car_idx: int
    driver_name: str
    car_number: str

    starting_position: int = 0
    current_position: int = 0
    best_position: int = 0
    worst_position: int = 0

    positions_gained: int = 0
    positions_lost: int = 0

    laps_seen: int = 0
    last_updated_lap: int = 0

    tags: List[str] = field(default_factory=list)


class RaceIntelligence:
    """
    Central race intelligence layer.

    Owns:
    - Driver summaries
    - Driver memory
    - Story detection
    - Story lifecycle
    - Battle detection
    - Momentum profiles

    This class should become the main race knowledge source for:
    - Editorial Producer
    - Jeff
    - Sarah
    - OpenAI Broadcast Brain
    - Camera Director
    """

    def __init__(self):
        self.story_engine = StoryEngine()
        self.story_manager = StoryManager()
        self.battle_detector = BattleDetector()
        self.driver_memory = DriverMemory()
        self.momentum_tracker = MomentumTracker()

        self.driver_summaries: Dict[int, DriverIntelligence] = {}

        self.active_stories: List[RaceStory] = []
        self.managed_stories: List[ManagedStory] = []
        self.active_battles: List[BattleStory] = []

        self.current_lap = 0

    def update(self, results, driver_lookup, current_lap=0, pit_road_status=None):
        self.current_lap = current_lap

        self.update_driver_summaries(
            results=results,
            driver_lookup=driver_lookup,
            current_lap=current_lap,
        )

        self.driver_memory.update(
            results=results,
            driver_lookup=driver_lookup,
            current_lap=current_lap,
            pit_road_status=pit_road_status,
        )

        self.momentum_tracker.update(
            results=results,
            driver_lookup=driver_lookup,
        )

        self.active_battles = self.battle_detector.analyze(
            results=results,
            driver_lookup=driver_lookup,
        )

        race_stories = self.story_engine.update(
            results=results,
            driver_lookup=driver_lookup,
            current_lap=current_lap,
        )

        if race_stories:
            self.active_stories = race_stories

        self.managed_stories = self.story_manager.update(
            race_stories=race_stories,
            current_lap=current_lap,
        )

        return self.get_race_knowledge()

    def update_driver_summaries(self, results, driver_lookup, current_lap):
        if not results:
            return

        for car in results:
            car_idx = car.get("CarIdx")

            if car_idx is None:
                continue

            position = self.safe_int(car.get("Position", 0))

            if position <= 0:
                continue

            driver_info = driver_lookup.get(car_idx, {})
            driver_name = driver_info.get("name", f"Car {car_idx}")
            car_number = driver_info.get("number", "?")

            summary = self.get_or_create_driver_summary(
                car_idx=car_idx,
                driver_name=driver_name,
                car_number=car_number,
                position=position,
            )

            summary.driver_name = driver_name
            summary.car_number = car_number
            summary.current_position = position
            summary.best_position = min(summary.best_position, position)
            summary.worst_position = max(summary.worst_position, position)
            summary.positions_gained = summary.starting_position - position
            summary.positions_lost = position - summary.starting_position
            summary.laps_seen += 1
            summary.last_updated_lap = current_lap
            summary.tags = self.build_driver_tags(summary)

    def get_or_create_driver_summary(self, car_idx, driver_name, car_number, position):
        if car_idx not in self.driver_summaries:
            self.driver_summaries[car_idx] = DriverIntelligence(
                car_idx=car_idx,
                driver_name=driver_name,
                car_number=car_number,
                starting_position=position,
                current_position=position,
                best_position=position,
                worst_position=position,
            )

        return self.driver_summaries[car_idx]

    def build_driver_tags(self, summary):
        tags = []

        if summary.positions_gained >= 8:
            tags.append("big mover")

        if summary.positions_gained >= 5 and summary.current_position <= 5:
            tags.append("top five charge")

        if summary.positions_lost >= 6:
            tags.append("fading")

        if summary.current_position == 1:
            tags.append("leader")

        if summary.current_position <= 5:
            tags.append("top five")

        momentum = self.get_momentum_profile(summary.car_idx)

        if momentum:
            if momentum.status == "charging":
                tags.append("charging")
            elif momentum.status == "fading":
                tags.append("losing momentum")

        return tags

    def get_race_knowledge(self):
        return {
            "current_lap": self.current_lap,
            "top_story": self.top_story(),
            "active_stories": self.get_active_stories(),
            "active_battles": self.get_active_battles(),
            "biggest_movers": self.get_biggest_movers(),
            "fading_drivers": self.get_fading_drivers(),
            "hottest_drivers": self.get_hottest_drivers(),
            "coldest_drivers": self.get_coldest_drivers(),
            "top_five": self.get_top_five(),
        }

    def get_active_stories(self):
        return self.story_manager.get_active_stories()

    def top_story(self) -> Optional[ManagedStory]:
        return self.story_manager.get_top_story()

    def mark_story_discussed(self, story_id, current_lap=0):
        self.story_manager.mark_discussed(story_id, current_lap)

    def has_story(self):
        return self.top_story() is not None

    def get_active_battles(self):
        return self.active_battles

    def get_best_battle(self):
        if not self.active_battles:
            return None

        return sorted(
            self.active_battles,
            key=lambda battle: battle.importance,
            reverse=True,
        )[0]

    def get_driver_summary(self, car_idx):
        return self.driver_summaries.get(car_idx)

    def get_driver_memory(self, car_idx):
        return self.driver_memory.get_record(car_idx)

    def get_momentum_profile(self, car_idx) -> Optional[MomentumProfile]:
        return self.momentum_tracker.get_profile(car_idx)

    def get_biggest_movers(self, limit=5):
        summaries = list(self.driver_summaries.values())
        summaries.sort(key=lambda item: item.positions_gained, reverse=True)
        return summaries[:limit]

    def get_fading_drivers(self, limit=5):
        summaries = list(self.driver_summaries.values())
        summaries.sort(key=lambda item: item.positions_lost, reverse=True)
        return summaries[:limit]

    def get_hottest_drivers(self, limit=5):
        return self.momentum_tracker.hottest_drivers(limit=limit)

    def get_coldest_drivers(self, limit=5):
        return self.momentum_tracker.coldest_drivers(limit=limit)

    def get_top_five(self):
        summaries = list(self.driver_summaries.values())

        return sorted(
            [item for item in summaries if item.current_position <= 5],
            key=lambda item: item.current_position,
        )

    def clear(self):
        self.driver_summaries = {}
        self.active_stories = []
        self.managed_stories = []
        self.active_battles = []

        self.story_manager.clear()
        self.driver_memory.clear()

        self.momentum_tracker = MomentumTracker()

        self.current_lap = 0

    def safe_int(self, value):
        try:
            return int(value)
        except Exception:
            return 0