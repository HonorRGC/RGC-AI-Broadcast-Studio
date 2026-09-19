import json
import time
from pathlib import Path

from broadcast.broadcast_queue import ScheduledBroadcast
from replay.replay_reader import ReplayReader


class ReplayTelemetry:
    """Implements the same read interface as the live iRacing adapter."""

    def __init__(self, filename, clock=None):
        self.recorded_broadcast = True
        self.path = Path(filename)
        self.snapshots = ReplayReader(filename).load_all()
        self.current_index = 0
        self.controller = None
        self.recorded_items = self._load_recorded_items()
        self._delivered_event_indices = set()
        self.clock = clock or time.monotonic
        self.playback_started_at = None
        self.capture_started_at = self._capture_start_timestamp()
        self.last_controller_marker = None

    def attach_controller(self, controller):
        self.controller = controller
        return self

    def start_timed_playback(self, reset_index=False):
        if reset_index:
            self.current_index = 0
            self._delivered_event_indices.clear()
        self.playback_started_at = self.clock()
        snapshot = self.current_snapshot()
        if snapshot is not None:
            self.capture_started_at = float(snapshot.timestamp or 0.0)
        return self.current_snapshot()

    def synchronize_to_controller(self, force=False, forward_threshold_seconds=8.0):
        if not self.controller or not self.snapshots:
            return False
        session_num = self.controller.get_current_session_num()
        session_time = self.controller.get_session_time()
        session_type = str(self.controller.get_session_type() or "").strip().lower()
        marker = (int(session_num), float(session_time))
        current = self.current_snapshot()
        if current is not None and not force:
            same_session = int(current.session_num) == marker[0]
            if same_session:
                self.last_controller_marker = marker
                return False

        candidates = [
            (index, snapshot)
            for index, snapshot in enumerate(self.snapshots)
            if int(snapshot.session_num) == marker[0]
        ]
        if not candidates and session_type:
            candidates = [
                (index, snapshot)
                for index, snapshot in enumerate(self.snapshots)
                if str(snapshot.session_type or "").strip().lower() == session_type
            ]
        if not candidates:
            return False

        target_index, _target = min(
            candidates,
            key=lambda pair: abs(float(pair[1].session_time or 0.0) - marker[1]),
        )
        if not force and target_index <= self.current_index:
            return False

        self._mark_events_before(target_index)
        self.current_index = target_index
        self.last_controller_marker = marker
        self.start_timed_playback(reset_index=False)
        return True

    def _mark_events_before(self, snapshot_index):
        for event_snapshot_index, items in self.recorded_items.items():
            if event_snapshot_index >= snapshot_index:
                continue
            for offset in range(len(items)):
                self._delivered_event_indices.add((event_snapshot_index, offset))

    def _capture_start_timestamp(self):
        if not self.snapshots:
            return 0.0
        try:
            return float(self.snapshots[0].timestamp or 0.0)
        except (TypeError, ValueError):
            return 0.0

    def _load_recorded_items(self):
        path = self.path.with_suffix(".events.jsonl")
        if not path.exists():
            return {}
        items = {}
        with path.open("r", encoding="utf-8") as event_file:
            for line in event_file:
                if not line.strip():
                    continue
                data = json.loads(line)
                snapshot_index = int(data.pop("snapshot_index", 0))
                data.pop("captured_at", None)
                allowed = ScheduledBroadcast.__dataclass_fields__
                item = ScheduledBroadcast(**{key: value for key, value in data.items() if key in allowed})
                items.setdefault(snapshot_index, []).append(item)
        return items

    def recorded_item_for_current_snapshot(self):
        for snapshot_index in sorted(self.recorded_items):
            if snapshot_index > self.current_index:
                break
            for offset, item in enumerate(self.recorded_items[snapshot_index]):
                key = (snapshot_index, offset)
                if key not in self._delivered_event_indices:
                    self._delivered_event_indices.add(key)
                    return item
        return None

    def startup(self):
        return bool(self.snapshots)

    def is_connected(self):
        return self.current_index < len(self.snapshots)

    def current_snapshot(self):
        if not self.is_connected():
            return None
        return self.snapshots[self.current_index]

    def next_snapshot(self):
        if self.controller:
            self.synchronize_to_controller(force=False)
        if self.playback_started_at is not None and self.capture_started_at > 0:
            target_timestamp = self.capture_started_at + (
                self.clock() - self.playback_started_at
            )
            best_index = self.current_index
            for index in range(self.current_index, len(self.snapshots)):
                snapshot = self.snapshots[index]
                if float(snapshot.timestamp or 0.0) <= target_timestamp:
                    best_index = index
                else:
                    break
            self.current_index = best_index
            return self.current_snapshot()
        self.current_index += 1
        return self.current_snapshot()

    def reset(self):
        self.current_index = 0
        self._delivered_event_indices.clear()
        self.playback_started_at = None
        self.last_controller_marker = None

    def get_session_flags(self):
        snapshot = self.current_snapshot()
        return snapshot.session_flags if snapshot else 0

    def get_session_type(self):
        snapshot = self.current_snapshot()
        return snapshot.session_type if snapshot else "Unknown"

    def get_session_state(self):
        snapshot = self.current_snapshot()
        return snapshot.session_state if snapshot else 0

    def get_current_session_num(self):
        snapshot = self.current_snapshot()
        return snapshot.session_num if snapshot else 0

    def get_session_time(self):
        snapshot = self.current_snapshot()
        return snapshot.session_time if snapshot else 0.0

    def get_session_time_remaining(self):
        snapshot = self.current_snapshot()
        return snapshot.session_time_remaining if snapshot else 0.0

    def seek_replay_session_time(self, session_num, session_time_seconds):
        if self.controller:
            return self.controller.seek_replay_session_time(
                session_num,
                session_time_seconds,
            )
        return False

    def get_lap(self):
        snapshot = self.current_snapshot()
        return snapshot.race_lap() if snapshot else 0

    def get_total_laps(self):
        snapshot = self.current_snapshot()
        return snapshot.total_laps if snapshot else 0

    def get_results(self):
        snapshot = self.current_snapshot()
        return snapshot.results if snapshot else []

    def get_starting_grid(self):
        snapshot = self.current_snapshot()
        if not snapshot:
            return []
        return snapshot.starting_grid or snapshot.results

    def get_driver_lookup(self):
        snapshot = self.current_snapshot()
        if not snapshot:
            return {}
        return {self._integer_key(key): value for key, value in snapshot.driver_lookup.items()}

    def get_track_info(self):
        snapshot = self.current_snapshot()
        return snapshot.track_info if snapshot else {}

    def get_camera_groups(self):
        if self.controller:
            return self.controller.get_camera_groups()
        return []

    def is_replay_at_live_edge(self, frame_tolerance=120):
        if self.controller:
            snapshot = self.current_snapshot()
            if snapshot is None:
                return False
            controller_session = int(self.controller.get_current_session_num())
            controller_time = float(self.controller.get_session_time())
            tolerance_seconds = max(1.0, float(frame_tolerance) / 60.0)
            return (
                controller_session == int(snapshot.session_num)
                and abs(controller_time - float(snapshot.session_time or 0.0))
                <= tolerance_seconds
            )
        return True

    def return_to_live(self):
        if self.controller:
            snapshot = self.current_snapshot()
            if snapshot is None:
                return False
            return self.controller.seek_replay_session_time(
                snapshot.session_num,
                snapshot.session_time,
            )
        return False

    def __getattr__(self, name):
        controller = self.__dict__.get("controller")
        if controller is not None and hasattr(controller, name):
            return getattr(controller, name)
        raise AttributeError(name)

    def get_car_idx_on_pit_road(self):
        return self._snapshot_list("pit_road_status")

    def get_car_idx_track_surface(self):
        return self._snapshot_list("track_surface")

    def get_car_idx_track_surface_material(self):
        return self._snapshot_list("track_surface_material")

    def get_car_idx_lap_dist_pct(self):
        return self._snapshot_list("lap_dist_pct")

    def get_car_idx_est_time(self):
        return self._snapshot_list("est_time")

    def _snapshot_list(self, name):
        snapshot = self.current_snapshot()
        return getattr(snapshot, name) if snapshot else []

    @staticmethod
    def _integer_key(key):
        try:
            return int(key)
        except (TypeError, ValueError):
            return key
