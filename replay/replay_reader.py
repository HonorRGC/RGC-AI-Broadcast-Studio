import json
from pathlib import Path

from replay.telemetry_snapshot import TelemetrySnapshot


class ReplayReader:
    def __init__(self, filename):
        self.path = Path(filename)

    def load_all(self):
        return list(self.iter_snapshots())

    def iter_snapshots(self):
        if not self.path.exists():
            raise FileNotFoundError(f"Replay file not found: {self.path}")

        previous = None
        payload = {}
        with self.path.open("r", encoding="utf-8") as replay_file:
            for line_number, line in enumerate(replay_file, start=1):
                if not line.strip():
                    continue
                try:
                    entry = json.loads(line)
                    if "_capture_delta" in entry:
                        if previous is None:
                            raise ValueError("Delta snapshot has no initial full snapshot")
                        payload = {**payload, **entry["_capture_delta"]}
                    else:
                        payload = entry
                    snapshot = TelemetrySnapshot.from_dict(payload)
                    if previous is not None:
                        for field in ("driver_lookup", "track_info", "weekend_info", "starting_grid", "pit_road_status", "track_surface", "track_surface_material", "car_rpm", "car_gear", "car_throttle", "car_brake", "car_fuel_pct", "car_idx_session_flags", "car_idx_penalty_reasons"):
                            if getattr(snapshot, field) == getattr(previous, field):
                                setattr(snapshot, field, getattr(previous, field))
                    previous = snapshot
                    yield snapshot
                except (TypeError, ValueError) as error:
                    raise ValueError(
                        f"Invalid replay snapshot on line {line_number}: {error}"
                    ) from error
