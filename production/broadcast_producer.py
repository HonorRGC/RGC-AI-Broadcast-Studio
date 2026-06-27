from production.broadcast_context import BroadcastContext
from production.story_detector import StoryDetector


class BroadcastProducer:
    """
    The Broadcast Producer decides what deserves airtime.

    BroadcastContext remembers the race.
    StoryDetector finds developing stories.
    BroadcastProducer decides what gets sent to the booth.
    """

    def __init__(self):
        self.context = BroadcastContext()
        self.story_detector = StoryDetector()

        self.driver_cooldown_seconds = 30
        self.story_cooldown_seconds = 45

        self.minimum_importance = 7
        self.recent_story_keys = {}

    def review_event(self, event):
        if event is None:
            return None

        driver_context = self.context.update_from_event(event)

        if driver_context is None:
            return None

        stories = self.story_detector.detect_stories(self.context)
        best_story = self.choose_best_story(stories, driver_context)

        if best_story and self.should_air_story(best_story, driver_context):
            self.context.mark_mentioned(
                driver_context,
                lap=getattr(event, "lap", 0),
            )
            self.mark_story_aired(best_story)
            self.enrich_event_with_story(event, best_story, driver_context)
            return event

        if self.should_air_event(event, driver_context):
            self.context.mark_mentioned(
                driver_context,
                lap=getattr(event, "lap", 0),
            )
            self.enrich_event_with_context(event, driver_context)
            return event

        return None

    def choose_best_story(self, stories, driver_context):
        if not stories:
            return None

        driver_stories = [
            story for story in stories
            if story.driver_name == driver_context.driver_name
        ]

        if driver_stories:
            return sorted(driver_stories, key=lambda story: story.priority, reverse=True)[0]

        return stories[0]

    def should_air_story(self, story, driver_context):
        if not self.driver_is_off_cooldown(driver_context):
            return False

        story_key = self.get_story_key(story)

        if story_key in self.recent_story_keys:
            return False

        if story.priority >= 8:
            return True

        if story.confidence >= 85:
            return True

        return False

    def should_air_event(self, event, driver_context):
        importance = getattr(event, "importance", 0)
        new_position = getattr(event, "new_position", 999)

        if new_position == 1:
            return True

        if importance >= 10:
            return True

        if not self.driver_is_off_cooldown(driver_context):
            return False

        if new_position <= 5 and importance >= 8:
            return True

        if importance >= self.minimum_importance:
            return True

        return False

    def driver_is_off_cooldown(self, driver_context):
        return (
            self.context.seconds_since_mentioned(driver_context)
            >= self.driver_cooldown_seconds
        )

    def mark_story_aired(self, story):
        self.recent_story_keys[self.get_story_key(story)] = True

    def get_story_key(self, story):
        return f"{story.story_type}:{story.car_number}:{story.driver_name}"

    def enrich_event_with_story(self, event, story, driver_context):
        event.importance = max(getattr(event, "importance", 0), story.priority)

        event.message = (
            f"Broadcast story: {story.headline} "
            f"{story.summary}"
        )

        event.story = (
            f"{story.summary} "
            f"Story type: {story.story_type}. "
            f"Confidence: {story.confidence} percent. "
            f"{self.context.build_context_summary(driver_context)}"
        )

    def enrich_event_with_context(self, event, driver_context):
        event.message = self.context.build_context_summary(driver_context)
        event.story = event.message