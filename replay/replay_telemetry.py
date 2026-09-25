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
        self.playback_ready = False
        self.controller_frame_anchor = None
        self.controller_frame_observed = None
        self.controller_session_marker_observed = None
        self.controller_frame_polled_at = None
        self.manual_review_hold = False
        self.pending_frame_reanchor = False
        self.pending_live_target = None
        self._lap_history_cache_index = -1
        self._recorded_lap_status = {}

    def attach_controller(self, controller):
        self.controller = controller
        self.arm_controller_playback()
        return self

    def arm_controller_playback(self):
        self.playback_ready = False
        self.controller_frame_anchor = self._controller_frame_number()
        self.controller_frame_observed = self.controller_frame_anchor
        self.controller_session_marker_observed = self._controller_session_marker()
        self.controller_frame_polled_at = self.clock()
        self.pending_frame_reanchor = False
        self.pending_live_target = None
        self.playback_started_at = None
        return self.controller_frame_anchor

    def recorded_playback_is_ready(self):
        return not self.controller or self.playback_ready

    def set_manual_review_hold(self, active):
        self.manual_review_hold = bool(active)

    def _controller_frame_number(self):
        if not self.controller:
            return None
        reader = getattr(self.controller, "get_replay_frame_number", None)
        if not reader:
            return None
        try:
            value = reader()
            return int(value) if value is not None else None
        except (TypeError, ValueError):
            return None

    def _controller_session_marker(self):
        if not self.controller:
            return None
        try:
            return (
                int(self.controller.get_current_session_num()),
                float(self.controller.get_session_time()),
                self._session_type_family(self.controller.get_session_type()),
            )
        except (AttributeError, TypeError, ValueError):
            return None

    def _activate_controller_playback_if_moving(self):
        frame = self._controller_frame_number()
        session_marker = self._controller_session_marker()
        if frame is not None and self.controller_frame_observed is None:
            self.controller_frame_observed = frame
            self.controller_frame_anchor = frame
        frame_moved = (
            frame is not None
            and self.controller_frame_observed is not None
            and frame != self.controller_frame_observed
        )
        session_clock_moved = self._session_marker_moved(session_marker)
        if not frame_moved and not session_clock_moved:
            return False
        self.synchronize_to_controller(force=True)
        self.playback_ready = True
        if frame is not None:
            self.controller_frame_anchor = frame
            self.controller_frame_observed = frame
        self.controller_session_marker_observed = session_marker
        snapshot = self.current_snapshot()
        if snapshot is not None:
            self.capture_started_at = float(snapshot.timestamp or 0.0)
        return True

    def _session_marker_moved(self, marker, minimum_seconds=0.2):
        previous = self.controller_session_marker_observed
        if marker is None:
            return False
        if previous is None:
            self.controller_session_marker_observed = marker
            return False
        if marker[0] != previous[0] or marker[2] != previous[2]:
            return True
        return abs(marker[1] - previous[1]) >= float(minimum_seconds)

    def start_timed_playback(self, reset_index=False):
        if reset_index:
            self.current_index = 0
            self._delivered_event_indices.clear()
        self.playback_started_at = self.clock()
        snapshot = self.current_snapshot()
        if snapshot is not None:
            self.capture_started_at = float(snapshot.timestamp or 0.0)
        return self.current_snapshot()

    def synchronize_to_controller(
        self,
        force=False,
        forward_threshold_seconds=8.0,
        preserve_pending_events=False,
    ):
        if not self.controller or not self.snapshots:
            return False
        session_num = self.controller.get_current_session_num()
        session_time = self.controller.get_session_time()
        session_type = self._session_type_family(self.controller.get_session_type())
        marker = (int(session_num), float(session_time))
        current = self.current_snapshot()
        if current is not None and not force:
            same_session = int(current.session_num) == marker[0]
            same_type = not session_type or self._session_type_family(
                current.session_type
            ) == session_type
            if same_session and same_type:
                self.last_controller_marker = marker
                return False

        candidates = [
            (index, snapshot)
            for index, snapshot in enumerate(self.snapshots)
            if int(snapshot.session_num) == marker[0]
        ]
        if session_type:
            typed_candidates = [
                (index, snapshot)
                for index, snapshot in candidates
                if self._session_type_family(snapshot.session_type) == session_type
            ]
            if typed_candidates:
                candidates = typed_candidates
        if not candidates and session_type:
            candidates = [
                (index, snapshot)
                for index, snapshot in enumerate(self.snapshots)
                if self._session_type_family(snapshot.session_type) == session_type
            ]
        if not candidates:
            return False

        target_index, _target = min(
            candidates,
            key=lambda pair: abs(float(pair[1].session_time or 0.0) - marker[1]),
        )
        if not force and target_index <= self.current_index:
            return False

        if target_index < self.current_index:
            self._align_event_delivery_to(target_index)
        elif not preserve_pending_events:
            self._mark_events_before(target_index)
        self.current_index = target_index
        self.last_controller_marker = marker
        self.start_timed_playback(reset_index=False)
        frame = self._controller_frame_number()
        if frame is not None:
            self.controller_frame_anchor = frame
            self.controller_frame_observed = frame
        return True

    @staticmethod
    def _session_type_family(value):
        text = str(value or "").strip().lower()
        if "qual" in text:
            return "qualify"
        if "race" in text:
            return "race"
        if "practice" in text:
            return "practice"
        if "warmup" in text or "warm up" in text:
            return "warmup"
        return text

    def _controller_time_is_ahead(self, threshold_seconds=3.0):
        if not self.controller:
            return False
        current = self.current_snapshot()
        if current is None:
            return False
        try:
            controller_session = int(self.controller.get_current_session_num())
            controller_time = float(self.controller.get_session_time())
            current_session = int(current.session_num)
            current_time = float(current.session_time or 0.0)
        except (TypeError, ValueError):
            return False
        return (
            controller_session == current_session
            and controller_time - current_time >= float(threshold_seconds)
        )

    def _controller_clock_needs_sync(self, threshold_seconds=0.75):
        """Detect recorded telemetry lag even when ReplayFrameNum is unusable."""
        if not self.controller or self.pending_live_target is not None:
            return False
        current = self.current_snapshot()
        if current is None:
            return False
        try:
            controller_session = int(self.controller.get_current_session_num())
            controller_time = float(self.controller.get_session_time())
            controller_type = self._session_type_family(self.controller.get_session_type())
            current_session = int(current.session_num)
            current_time = float(current.session_time or 0.0)
            current_type = self._session_type_family(current.session_type)
        except (AttributeError, TypeError, ValueError):
            return False
        if controller_session != current_session:
            return True
        if controller_type and current_type and controller_type != current_type:
            return True
        return controller_time - current_time >= float(threshold_seconds)

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
            if not self.playback_ready:
                self._activate_controller_playback_if_moving()
                return self.current_snapshot()
            self.synchronize_to_controller(
                force=False,
                preserve_pending_events=True,
            )
            frame = self._controller_frame_number()
            polled_at = self.clock()
            if (
                not self.manual_review_hold
                and self.pending_live_target is None
                and self._controller_frame_jump_is_external(frame, polled_at)
            ):
                if self.synchronize_to_controller(force=True):
                    self._align_event_delivery_to(self.current_index)
                self.controller_frame_polled_at = polled_at
                return self.current_snapshot()
            self.controller_frame_polled_at = polled_at
            if self.manual_review_hold and self.pending_live_target is None:
                if frame is not None:
                    self.controller_frame_observed = frame
                return self.current_snapshot()
            # SessionTime remains available in cases where ReplayFrameNum is
            # absent, frozen, or reset at the green.  Use it as the safety clock
            # so the recorded broadcast cannot remain stuck at lap zero.
            if self._controller_clock_needs_sync():
                self.synchronize_to_controller(
                    force=True,
                    preserve_pending_events=True,
                )
                frame = self._controller_frame_number()
                if frame is not None:
                    self.controller_frame_anchor = frame
                    self.controller_frame_observed = frame
                snapshot = self.current_snapshot()
                if snapshot is not None:
                    self.capture_started_at = float(snapshot.timestamp or 0.0)
            # ReplayFrameNum can roll backward when iRacing crosses from
            # qualifying/pace laps into the race.  Never retain an anchor that
            # is ahead of the current frame: doing so pins elapsed time at zero
            # immediately after the green flag.
            if (
                frame is not None
                and self.controller_frame_anchor is not None
                and self.pending_live_target is None
                and frame < self.controller_frame_anchor
            ):
                self.synchronize_to_controller(
                    force=True,
                    preserve_pending_events=True,
                )
                frame = self._controller_frame_number()
                if frame is not None:
                    self.controller_frame_anchor = frame
                    self.controller_frame_observed = frame
                snapshot = self.current_snapshot()
                if snapshot is not None:
                    self.capture_started_at = float(snapshot.timestamp or 0.0)
            # Some saved replays reset or briefly stop updating ReplayFrameNum at
            # a session boundary.  The sim's session clock still advances, so use
            # it to re-anchor instead of leaving telemetry and commentary frozen
            # in qualifying while the Race cameras continue to move.
            if (
                frame is not None
                and self.controller_frame_observed is not None
                and frame <= self.controller_frame_observed
                and self._controller_time_is_ahead()
            ):
                self.synchronize_to_controller(
                    force=True,
                    preserve_pending_events=True,
                )
                frame = self._controller_frame_number()
            if self.pending_live_target is not None:
                if not self._controller_reached_live_target(frame):
                    return self.current_snapshot()
                self.controller_frame_anchor = frame
                self.controller_frame_observed = frame
                snapshot = self.current_snapshot()
                if snapshot is not None:
                    self.capture_started_at = float(snapshot.timestamp or 0.0)
                self.pending_live_target = None
            if self.pending_frame_reanchor and frame is not None:
                self.controller_frame_anchor = frame
                self.controller_frame_observed = frame
                snapshot = self.current_snapshot()
                if snapshot is not None:
                    self.capture_started_at = float(snapshot.timestamp or 0.0)
                self.pending_frame_reanchor = False
            if frame is not None and self.controller_frame_anchor is not None:
                elapsed = max(0.0, (frame - self.controller_frame_anchor) / 60.0)
                target_timestamp = self.capture_started_at + elapsed
                best_index = self.current_index
                for index in range(self.current_index, len(self.snapshots)):
                    snapshot = self.snapshots[index]
                    if float(snapshot.timestamp or 0.0) <= target_timestamp:
                        best_index = index
                    else:
                        break
                self.current_index = best_index
                self.controller_frame_observed = frame
                return self.current_snapshot()
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

    def _controller_frame_jump_is_external(self, frame, polled_at):
        if frame is None or self.controller_frame_observed is None:
            return False
        previous_poll = self.controller_frame_polled_at
        if previous_poll is None:
            return False
        wall_seconds = max(0.0, float(polled_at) - float(previous_poll))
        allowed_frames = max(180.0, wall_seconds * 60.0 * 4.0 + 120.0)
        return abs(int(frame) - int(self.controller_frame_observed)) > allowed_frames

    def _align_event_delivery_to(self, snapshot_index):
        self._delivered_event_indices = {
            (event_snapshot_index, offset)
            for event_snapshot_index, items in self.recorded_items.items()
            if event_snapshot_index < snapshot_index
            for offset in range(len(items))
        }

    def reset(self):
        self.current_index = 0
        self._delivered_event_indices.clear()
        self.playback_started_at = None
        self.last_controller_marker = None
        self.playback_ready = False
        self.controller_frame_anchor = None
        self.controller_frame_observed = None
        self.controller_session_marker_observed = None
        self.controller_frame_polled_at = None
        self.manual_review_hold = False
        self.pending_frame_reanchor = False
        self.pending_live_target = None
        self._lap_history_cache_index = -1
        self._recorded_lap_status = {}

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
            accepted = self.controller.seek_replay_session_time(
                snapshot.session_num,
                snapshot.session_time,
            )
            if accepted:
                self.pending_frame_reanchor = False
                self.pending_live_target = {
                    "session_num": int(snapshot.session_num),
                    "session_time": float(snapshot.session_time or 0.0),
                    "request_frame": self._controller_frame_number(),
                    "request_session_num": int(self.controller.get_current_session_num()),
                    "request_session_time": float(self.controller.get_session_time()),
                    "requested_at": self.clock(),
                }
            return accepted
        return False

    def _controller_reached_live_target(self, frame, tolerance_seconds=1.25):
        target = self.pending_live_target
        if not target or not self.controller:
            return True
        # Never let an accepted-but-unconfirmed iRacing seek freeze the entire
        # recorded broadcast. A normal seek lands quickly; after five seconds,
        # re-anchor at the best position iRacing currently reports and continue.
        requested_at = target.get("requested_at")
        if requested_at is not None and self.clock() - float(requested_at) >= 5.0:
            return True
        try:
            session_num = int(self.controller.get_current_session_num())
            session_time = float(self.controller.get_session_time())
        except (TypeError, ValueError):
            return False
        if session_num != target["session_num"]:
            return False
        if abs(session_time - target["session_time"]) > tolerance_seconds:
            return False

        request_was_already_near = (
            target["request_session_num"] == target["session_num"]
            and abs(target["request_session_time"] - target["session_time"])
            <= tolerance_seconds
        )
        if request_was_already_near:
            return True
        request_frame = target.get("request_frame")
        return frame is None or request_frame is None or frame != request_frame

    def get_recorded_lap_history(self):
        """Return every recorded race-lap state through the playback position."""
        if self.current_index < self._lap_history_cache_index:
            self._lap_history_cache_index = -1
            self._recorded_lap_status = {}

        caution_mask = 0x00000008 | 0x00000100 | 0x00004000 | 0x00008000
        start = self._lap_history_cache_index + 1
        end = min(self.current_index, len(self.snapshots) - 1)
        for index in range(start, end + 1):
            snapshot = self.snapshots[index]
            if str(snapshot.session_type or "").strip().lower() != "race":
                continue
            lap = int(snapshot.race_lap() or 0)
            if lap <= 0:
                continue
            flags = int(snapshot.session_flags or 0)
            status = "caution" if flags & caution_mask else "green"
            if self._recorded_lap_status.get(lap) != "caution":
                self._recorded_lap_status[lap] = status
        self._lap_history_cache_index = end
        return dict(self._recorded_lap_status)

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
