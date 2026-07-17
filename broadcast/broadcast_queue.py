import time
from dataclasses import dataclass, field
from typing import List, Tuple


@dataclass
class ScheduledBroadcast:
    priority: int
    message: str
    category: str = "race_commentary"
    protected: bool = False
    speaker: str = "lead"
    delay_seconds: float = 0.0
    expires_after: float = 90.0
    dedupe_key: str = ""
    camera_target_car_idx: int | None = None
    participant_car_indices: Tuple[int, ...] = ()
    camera_focus_incident: bool = False
    camera_incident_group: str = "Far Chase"
    camera_sequence: Tuple[int, ...] = ()
    camera_sequence_steps: Tuple[tuple, ...] = ()
    replay_session_num: int | None = None
    replay_session_time: float | None = None
    replay_incident_delta: int = 0
    replay_multi_angle: bool = False
    replay_use_incident_marker: bool = False
    replay_marker_pre_roll_frames: int | None = None
    camera_return_home_after_sequence: bool = False
    silent: bool = False
    feature_duration_seconds: float = 0.0
    created_at: float = field(default_factory=time.time)

    @property
    def ready_at(self):
        return self.created_at + self.delay_seconds

    def is_expired(self, now):
        return self.expires_after > 0 and now > self.created_at + self.expires_after


class BroadcastQueue:
    def __init__(self):
        self.items: List[ScheduledBroadcast] = []
        self.busy_until = 0.0
        self.minimum_gap_seconds = 2.5
        self.voice_tail_padding_seconds = 0.55

    def add(
        self,
        commentary,
        priority=5,
        category="race_commentary",
        protected=False,
        speaker="lead",
        delay_seconds=0.0,
        expires_after=90.0,
        dedupe_key="",
        camera_target_car_idx=None,
        participant_car_indices=(),
        camera_focus_incident=False,
        camera_incident_group="Far Chase",
        camera_sequence=(),
        camera_sequence_steps=(),
        replay_session_num=None,
        replay_session_time=None,
        replay_incident_delta=0,
        replay_multi_angle=False,
        replay_use_incident_marker=False,
        replay_marker_pre_roll_frames=None,
        camera_return_home_after_sequence=False,
        silent=False,
        feature_duration_seconds=0.0,
    ):
        if not commentary and not silent:
            return

        key = dedupe_key or f"{category}:{speaker}:{str(commentary).strip().lower()}"
        if any(item.dedupe_key == key for item in self.items):
            return

        self.items.append(
            ScheduledBroadcast(
                priority=priority,
                message=commentary,
                category=category,
                protected=protected,
                speaker=speaker,
                delay_seconds=delay_seconds,
                expires_after=expires_after,
                dedupe_key=key,
                camera_target_car_idx=camera_target_car_idx,
                participant_car_indices=tuple(participant_car_indices),
                camera_focus_incident=bool(camera_focus_incident),
                camera_incident_group=str(camera_incident_group or "Far Chase"),
                camera_sequence=tuple(camera_sequence),
                camera_sequence_steps=tuple(camera_sequence_steps),
                replay_session_num=replay_session_num,
                replay_session_time=replay_session_time,
                replay_incident_delta=replay_incident_delta,
                replay_multi_angle=bool(replay_multi_angle),
                replay_use_incident_marker=bool(replay_use_incident_marker),
                replay_marker_pre_roll_frames=replay_marker_pre_roll_frames,
                camera_return_home_after_sequence=bool(
                    camera_return_home_after_sequence
                ),
                silent=bool(silent),
                feature_duration_seconds=float(feature_duration_seconds or 0.0),
            )
        )

    def can_speak(self, now=None):
        now = time.time() if now is None else now
        return now >= self.busy_until

    def estimate_speech_seconds(self, message, category=""):
        if category == "crank_it_up":
            return 50.0
        if category == "booth_conversation":
            return max(4.4, min(12.0, len(str(message).split()) / 2.9))
        words = len(str(message).split())
        if category == "race_control" and self.is_short_lap_call(message):
            return max(1.2, words / 3.6)
        if category.startswith("opening_field_rundown"):
            return max(1.6, min(10.0, words / 3.35))
        if category.startswith(
            ("quarter_field_rundown", "three_quarter_field_rundown", "long_green_field_rundown")
        ):
            return max(3.0, min(16.0, words / 2.85))
        return max(5.0, min(45.0, words / 2.45))

    @staticmethod
    def is_short_lap_call(message):
        text = str(message or "").strip().lower()
        return text in {
            "two laps to go.",
            "white flag. one lap to go.",
        }

    def estimate_gap_seconds(self, category=""):
        if category.startswith("opening_field_rundown"):
            return 0.75
        if category.startswith(
            ("quarter_field_rundown", "three_quarter_field_rundown", "long_green_field_rundown")
        ):
            return 1.0
        return self.minimum_gap_seconds

    def estimate_item_gap_seconds(self, item):
        if item.category == "race_control" and self.is_short_lap_call(item.message):
            return 0.6
        if item.category == "booth_conversation":
            return 0.2
        return self.estimate_gap_seconds(item.category)

    def has_pending_booth_follow_up(self, now):
        return any(
            item.category == "race_story_follow_up" and item.ready_at <= now
            for item in self.items
        )

    def has_pending_booth_conversation(self):
        return any(item.category == "booth_conversation" for item in self.items)

    def tight_handoff_speech_seconds(self, message, category, default_seconds):
        if category != "race_story":
            return default_seconds

        words = len(str(message).split())
        return min(default_seconds, max(3.6, words / 3.25))

    def next_item(self, now=None):
        now = time.time() if now is None else now
        if not self.items or not self.can_speak(now):
            return None

        self.items = [item for item in self.items if not item.is_expired(now)]
        ready_items = [item for item in self.items if item.ready_at <= now]

        if not ready_items:
            return None

        ready_items.sort(
            key=lambda item: (item.protected, item.priority, -item.created_at),
            reverse=True,
        )
        selected = ready_items[0]

        self.items.remove(selected)

        speech_time = (
            selected.feature_duration_seconds
            if selected.feature_duration_seconds > 0
            else self.estimate_speech_seconds(selected.message, selected.category)
        )
        if self.has_pending_booth_follow_up(now):
            speech_time = self.tight_handoff_speech_seconds(
                selected.message,
                selected.category,
                speech_time,
            )
            gap_time = 0.15
        else:
            gap_time = self.estimate_item_gap_seconds(selected)
        tail_padding = 0.0 if selected.silent else self.voice_tail_padding_seconds
        self.busy_until = now + speech_time + gap_time + tail_padding

        return selected

    def clear_for_race_control(self, preserve_categories=(), reset_busy=True):
        preserved = set(preserve_categories)
        self.items = [item for item in self.items if item.category in preserved]
        if reset_busy:
            self.busy_until = 0.0
