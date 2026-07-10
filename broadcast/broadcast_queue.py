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
        words = len(str(message).split())
        if category.startswith("opening_field_rundown"):
            return max(1.6, min(10.0, words / 3.35))
        if category.startswith(
            ("quarter_field_rundown", "three_quarter_field_rundown", "long_green_field_rundown")
        ):
            return max(3.0, min(16.0, words / 2.85))
        return max(5.0, min(45.0, words / 2.45))

    def estimate_gap_seconds(self, category=""):
        if category.startswith("opening_field_rundown"):
            return 0.75
        if category.startswith(
            ("quarter_field_rundown", "three_quarter_field_rundown", "long_green_field_rundown")
        ):
            return 1.0
        return self.minimum_gap_seconds

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
        self.busy_until = now + speech_time + self.estimate_gap_seconds(
            selected.category
        )

        return selected

    def clear_for_race_control(self, preserve_categories=()):
        preserved = set(preserve_categories)
        self.items = [item for item in self.items if item.category in preserved]
        self.busy_until = 0.0
