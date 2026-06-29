from replay.replay_reader import ReplayReader


class ReplayTelemetry:
    def __init__(self, filename):
        self.reader = ReplayReader(filename)
        self.snapshots = self.reader.load_all()
        self.current_index = 0

    def startup(self):
        return len(self.snapshots) > 0

    def is_connected(self):
        return self.current_index < len(self.snapshots)

    def current_snapshot(self):
        if not self.snapshots:
            return None
        return self.snapshots[self.current_index]

    def next_snapshot(self):
        self.current_index += 1
        return self.current_snapshot() if self.is_connected() else None

    def reset(self):
        self.current_index = 0

    def get_session_flags(self):
        snapshot = self.current_snapshot()
        return snapshot.session_flags if snapshot else 0

    def get_lap(self):
        snapshot = self.current_snapshot()
        return snapshot.get_race_lap() if snapshot else 0

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

        fixed_lookup = {}

        for key, value in snapshot.driver_lookup.items():
            try:
                fixed_lookup[int(key)] = value
            except Exception:
                fixed_lookup[key] = value

        return fixed_lookup

    def get_track_info(self):
        snapshot = self.current_snapshot()
        return snapshot.track_info if snapshot else {}

    def get_car_idx_on_pit_road(self):
        snapshot = self.current_snapshot()
        return snapshot.pit_road_status if snapshot else []

    def get_car_idx_track_surface(self):
        snapshot = self.current_snapshot()
        return snapshot.track_surface if snapshot else []

    def get_car_idx_track_surface_material(self):
        snapshot = self.current_snapshot()
        return snapshot.track_surface_material if snapshot else []

    def get_car_idx_lap_dist_pct(self):
        snapshot = self.current_snapshot()
        return snapshot.lap_dist_pct if snapshot else []

    def get_car_idx_est_time(self):
        snapshot = self.current_snapshot()
        return snapshot.est_time if snapshot else []

    def snapshot_count(self):
        return len(self.snapshots)

    def current_position(self):
        return self.current_index + 1

    def percent_complete(self):
        if not self.snapshots:
            return 0.0
        return (self.current_index + 1) / len(self.snapshots) * 100.0