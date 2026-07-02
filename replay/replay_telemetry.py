from replay.replay_reader import ReplayReader


class ReplayTelemetry:
    """Implements the same read interface as the live iRacing adapter."""

    def __init__(self, filename):
        self.snapshots = ReplayReader(filename).load_all()
        self.current_index = 0

    def startup(self):
        return bool(self.snapshots)

    def is_connected(self):
        return self.current_index < len(self.snapshots)

    def current_snapshot(self):
        if not self.is_connected():
            return None
        return self.snapshots[self.current_index]

    def next_snapshot(self):
        self.current_index += 1
        return self.current_snapshot()

    def reset(self):
        self.current_index = 0

    def get_session_flags(self):
        snapshot = self.current_snapshot()
        return snapshot.session_flags if snapshot else 0

    def get_lap(self):
        snapshot = self.current_snapshot()
        return snapshot.race_lap() if snapshot else 0

    def get_total_laps(self):
        snapshot = self.current_snapshot()
        return snapshot.total_laps if snapshot else 0

    def get_results(self):
        snapshot = self.current_snapshot()
        return snapshot.results if snapshot else []

    def get_driver_lookup(self):
        snapshot = self.current_snapshot()
        if not snapshot:
            return {}
        return {self._integer_key(key): value for key, value in snapshot.driver_lookup.items()}

    def get_track_info(self):
        snapshot = self.current_snapshot()
        return snapshot.track_info if snapshot else {}

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
