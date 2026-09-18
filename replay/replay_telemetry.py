import json
from pathlib import Path

from broadcast.broadcast_queue import ScheduledBroadcast
from replay.replay_reader import ReplayReader


class ReplayTelemetry:
    """Implements the same read interface as the live iRacing adapter."""

    def __init__(self, filename):
        self.path = Path(filename)
        self.snapshots = ReplayReader(filename).load_all()
        self.current_index = 0
        self.controller = None
        self.recorded_items = self._load_recorded_items()
        self._delivered_event_indices = set()

    def attach_controller(self, controller):
        self.controller = controller
        return self

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
            session_num = self.controller.get_current_session_num()
            session_time = self.controller.get_session_time()
            best_index = self.current_index
            for index, snapshot in enumerate(self.snapshots):
                marker = (int(snapshot.session_num), float(snapshot.session_time))
                target = (int(session_num), float(session_time))
                if marker <= target:
                    best_index = index
                elif int(snapshot.session_num) >= int(session_num):
                    break
            self.current_index = best_index
            return self.current_snapshot()
        self.current_index += 1
        return self.current_snapshot()

    def reset(self):
        self.current_index = 0
        self._delivered_event_indices.clear()

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
            return self.controller.is_replay_at_live_edge(frame_tolerance)
        return True

    def return_to_live(self):
        if self.controller:
            return self.controller.return_to_live()
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
