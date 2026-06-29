import json
import os
from typing import Iterator, List

from replay.telemetry_snapshot import TelemetrySnapshot


class ReplayReader:
    def __init__(self, filename):
        self.filename = filename

    def exists(self):
        return os.path.exists(self.filename)

    def load_all(self) -> List[TelemetrySnapshot]:
        snapshots = []

        if not self.exists():
            raise FileNotFoundError(f"Replay file not found: {self.filename}")

        with open(self.filename, "r", encoding="utf-8") as file:
            for line in file:
                if not line.strip():
                    continue

                data = json.loads(line)
                snapshots.append(TelemetrySnapshot.from_dict(data))

        return snapshots

    def iter_snapshots(self) -> Iterator[TelemetrySnapshot]:
        if not self.exists():
            raise FileNotFoundError(f"Replay file not found: {self.filename}")

        with open(self.filename, "r", encoding="utf-8") as file:
            for line in file:
                if not line.strip():
                    continue

                data = json.loads(line)
                yield TelemetrySnapshot.from_dict(data)

    def count_snapshots(self):
        count = 0

        if not self.exists():
            return 0

        with open(self.filename, "r", encoding="utf-8") as file:
            for line in file:
                if line.strip():
                    count += 1

        return count