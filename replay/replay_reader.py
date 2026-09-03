import json
from pathlib import Path

from replay.telemetry_snapshot import TelemetrySnapshot


class ReplayReader:
    def __init__(self, filename):
        self.path = Path(filename)

    def load_all(self):
        if not self.path.exists():
            raise FileNotFoundError(f"Replay file not found: {self.path}")

        snapshots = []
        with self.path.open("r", encoding="utf-8") as replay_file:
            for line_number, line in enumerate(replay_file, start=1):
                if not line.strip():
                    continue
                try:
                    snapshots.append(TelemetrySnapshot.from_dict(json.loads(line)))
                except (TypeError, ValueError) as error:
                    raise ValueError(
                        f"Invalid replay snapshot on line {line_number}: {error}"
                    ) from error
        return snapshots
