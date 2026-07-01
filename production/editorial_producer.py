from dataclasses import dataclass, field
from enum import Enum
from typing import Dict, List, Optional
import time

from production.editorial_timeline import EditorialTimeline, TimelineStory
from production.assignment_engine import AssignmentEngine, AssignmentTarget


class EditorialDecisionType(Enum):
    HOLD = "HOLD"
    AIR_NOW = "AIR_NOW"
    BACKGROUND = "BACKGROUND"
    IGNORE = "IGNORE"


@dataclass
class EditorialItem:
    story_type: str
    headline: str
    summary: str
    priority: int = 5
    source: str = "unknown"

    driver_name: str = ""
    car_number: str = ""

    speaker: str = "lead"
    category: str = "editorial"

    created_at: float = field(default_factory=time.time)
    last_aired_at: float = 0.0
    aired_count: int = 0


@dataclass
class EditorialDecision:
    decision_type: EditorialDecisionType
    item: Optional[EditorialItem] = None
    reason: str = ""


class EditorialProducer:
    def __init__(self):
        self.items: List[EditorialItem] = []
        self.recent_headlines: Dict[str, float] = {}

        self.timeline = EditorialTimeline()
        self.assignment_engine = AssignmentEngine()

        self.minimum_repeat_seconds = 45
        self.max_items = 50

    # ---------------------------------------------------------
    # Story Intake
    # ---------------------------------------------------------

    def submit_story(
        self,
        story_type,
        headline,
        summary,
        priority=5,
        source="unknown",
        driver_name="",
        car_number="",
    ):
        if not headline:
            return None

        item = EditorialItem(
            story_type=story_type,
            headline=headline,
            summary=summary,
            priority=priority,
            source=source,
            driver_name=driver_name,
            car_number=car_number,
            speaker=self.choose_speaker(story_type),
            category="race_story",
        )

        self.add_item(item)
        self.submit_to_timeline(item)

        return item

    def submit_pit_event(self, pit_event):
        item = EditorialItem(
            story_type="pit_strategy",
            headline=getattr(pit_event, "message", ""),
            summary=getattr(pit_event, "message", ""),
            priority=getattr(pit_event, "importance", 7),
            source="pit_strategy_detector",
            driver_name=getattr(pit_event, "driver_name", ""),
            car_number=getattr(pit_event, "car_number", ""),
            speaker="sarah",
            category="pit_strategy",
        )

        self.add_item(item)
        self.submit_to_timeline(item)

        return item

    def submit_race_knowledge(self, race_knowledge):
        if not race_knowledge:
            return []

        created_items = []

        top_story = race_knowledge.get("top_story")
        if top_story:
            item = self.submit_story(
                story_type=getattr(top_story, "story_type", "race_story"),
                headline=getattr(top_story, "headline", ""),
                summary=getattr(top_story, "summary", ""),
                priority=getattr(top_story, "importance", 7),
                source="race_intelligence",
                driver_name=getattr(top_story, "driver_name", ""),
                car_number=getattr(top_story, "car_number", ""),
            )
            if item:
                created_items.append(item)

        best_battle = race_knowledge.get("best_battle")
        if best_battle:
            item = self.submit_story(
                story_type=getattr(best_battle, "story_type", "battle"),
                headline=getattr(best_battle, "headline", ""),
                summary=getattr(best_battle, "summary", ""),
                priority=getattr(best_battle, "importance", 8),
                source="battle_detector",
                driver_name=getattr(best_battle, "chasing_driver_name", ""),
                car_number=getattr(best_battle, "chasing_car_number", ""),
            )
            if item:
                created_items.append(item)

        return created_items

    # ---------------------------------------------------------
    # Editorial Timeline
    # ---------------------------------------------------------

    def submit_to_timeline(self, item):
        story_id = self.build_story_id(item)

        timeline_story = TimelineStory(
            id=story_id,
            headline=item.headline,
            category=item.category,
            priority=item.priority,
            speaker=item.speaker,
            delay_seconds=self.choose_delay(item),
            follow_up_after=30,
            expire_after=120,
        )

        self.timeline.submit(timeline_story)

    # ---------------------------------------------------------
    # Assignment Creation
    # ---------------------------------------------------------

    def create_assignment_from_item(self, item):
        target = self.choose_assignment_target(item)

        self.assignment_engine.submit(
            assignment_id=self.build_story_id(item),
            target=target,
            headline=item.headline,
            summary=item.summary,
            priority=item.priority,
            expires_after=45,
        )

    def choose_assignment_target(self, item):
        if item.speaker == "jeff":
            return AssignmentTarget.JEFF

        if item.speaker == "sarah":
            return AssignmentTarget.SARAH

        return AssignmentTarget.LEAD

    # ---------------------------------------------------------
    # Assignment Dispatch
    # ---------------------------------------------------------

    def get_next_assignment(self, speaker):
        target = self.speaker_to_assignment_target(speaker)

        if not target:
            return None

        return self.assignment_engine.next_assignment(target)

    def complete_assignment(self, assignment):
        if assignment:
            self.assignment_engine.complete(assignment)

    def speaker_to_assignment_target(self, speaker):
        speaker = str(speaker or "").lower()

        if speaker == "lead":
            return AssignmentTarget.LEAD

        if speaker == "jeff":
            return AssignmentTarget.JEFF

        if speaker == "sarah":
            return AssignmentTarget.SARAH

        if speaker == "openai":
            return AssignmentTarget.OPENAI

        if speaker == "camera":
            return AssignmentTarget.CAMERA

        return None

    # ---------------------------------------------------------
    # Decision Layer
    # ---------------------------------------------------------

    def choose_next_item(self, race_state=None) -> EditorialDecision:
        timeline_story = self.timeline.next_story()

        if not timeline_story:
            return EditorialDecision(
                decision_type=EditorialDecisionType.HOLD,
                reason="No editorial timeline story ready.",
            )

        matching_item = self.find_item_for_timeline_story(timeline_story)

        if not matching_item:
            return EditorialDecision(
                decision_type=EditorialDecisionType.HOLD,
                reason="Timeline story had no matching item.",
            )

        if not self.can_air(matching_item):
            return EditorialDecision(
                decision_type=EditorialDecisionType.HOLD,
                reason="Item was recently aired.",
            )

        self.create_assignment_from_item(matching_item)

        assignment = self.get_next_assignment(matching_item.speaker)

        if not assignment:
            return EditorialDecision(
                decision_type=EditorialDecisionType.HOLD,
                reason="Assignment was not ready.",
            )

        matching_item.aired_count += 1
        matching_item.last_aired_at = time.time()
        self.recent_headlines[matching_item.headline] = time.time()

        self.complete_assignment(assignment)

        return EditorialDecision(
            decision_type=EditorialDecisionType.AIR_NOW,
            item=matching_item,
            reason=f"Assignment sent to {matching_item.speaker}.",
        )

    # ---------------------------------------------------------
    # Helpers
    # ---------------------------------------------------------

    def add_item(self, item):
        if not item.headline:
            return

        existing = self.find_existing_item(item)

        if existing:
            existing.priority = max(existing.priority, item.priority)
            existing.summary = item.summary or existing.summary
            existing.speaker = item.speaker or existing.speaker
            return

        self.items.append(item)

        if len(self.items) > self.max_items:
            self.items = self.items[-self.max_items:]

    def find_existing_item(self, item):
        for existing in self.items:
            if self.build_story_id(existing) == self.build_story_id(item):
                return existing

        return None

    def find_item_for_timeline_story(self, timeline_story):
        for item in self.items:
            if self.build_story_id(item) == timeline_story.id:
                return item

        return None

    def build_story_id(self, item):
        parts = [
            item.story_type or "story",
            item.driver_name or "",
            item.car_number or "",
            item.headline or "",
        ]

        return ":".join(parts).lower().strip()

    def choose_delay(self, item):
        if item.story_type in [
            "battle_for_lead",
            "battle_for_top_five",
            "battle_for_top_ten",
            "race_leader",
            "lead_change",
        ]:
            return 0

        if item.story_type in [
            "biggest_mover",
            "top_five_charge",
            "momentum",
            "fading_driver",
        ]:
            return 12

        if item.category == "pit_strategy":
            return 5

        return 8

    def can_air(self, item):
        last_time = self.recent_headlines.get(item.headline)

        if last_time is None:
            return True

        return time.time() - last_time >= self.minimum_repeat_seconds

    def choose_speaker(self, story_type):
        if story_type in [
            "biggest_mover",
            "top_five_charge",
            "momentum",
            "fading_driver",
            "battle_for_lead",
            "battle_for_top_five",
            "battle_for_top_ten",
        ]:
            return "jeff"

        if story_type in [
            "pit_strategy",
            "green_flag_pit",
            "caution_pit",
        ]:
            return "sarah"

        return "lead"

    def clear(self):
        self.items = []
        self.recent_headlines = {}
        self.timeline = EditorialTimeline()
        self.assignment_engine = AssignmentEngine()