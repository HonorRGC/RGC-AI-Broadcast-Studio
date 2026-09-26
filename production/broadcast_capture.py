import json
import time
from dataclasses import asdict
from datetime import datetime
from pathlib import Path

from replay.telemetry_snapshot import TelemetrySnapshot


class BroadcastCaptureRecorder:
    """Persist live telemetry and approved broadcast items for later playback."""

    def __init__(self, output_path=None, root=None):
        root = Path(root or Path.cwd())
        if output_path:
            self.telemetry_path = Path(output_path)
        else:
            stamp = datetime.now().strftime("%Y-%m-%d_%H-%M-%S")
            self.telemetry_path = root / "recordings" / f"broadcast_capture_{stamp}.jsonl"
        self.events_path = self.telemetry_path.with_suffix(".events.jsonl")
        self.metadata_path = self.telemetry_path.with_suffix(".capture.json")
        self.telemetry_path.parent.mkdir(parents=True, exist_ok=True)
        self.snapshot_index = -1
        self.started_at = time.time()
        self._telemetry_file = self.telemetry_path.open("w", encoding="utf-8", buffering=1)
        self._events_file = self.events_path.open("w", encoding="utf-8", buffering=1)
        self.write_metadata(status="recording")

    def record_snapshot(self, telemetry):
        self.snapshot_index += 1
        snapshot = TelemetrySnapshot.from_telemetry(telemetry, timestamp=time.time())
        self._telemetry_file.write(
            json.dumps(snapshot.to_dict(), separators=(",", ":")) + "\n"
        )
        return self.snapshot_index

    def record_item(self, item):
        if item is None:
            return
        payload = asdict(item)
        payload["snapshot_index"] = self.snapshot_index
        payload["captured_at"] = time.time()
        self._events_file.write(json.dumps(payload, separators=(",", ":")) + "\n")

    def write_metadata(self, status):
        payload = {
            "format": "rgc-recorded-broadcast-v1",
            "status": status,
            "started_at": self.started_at,
            "completed_at": time.time() if status == "complete" else None,
            "telemetry_file": self.telemetry_path.name,
            "events_file": self.events_path.name,
            "snapshot_count": max(0, self.snapshot_index + 1),
        }
        self.metadata_path.write_text(json.dumps(payload, indent=2), encoding="utf-8")

    def close(self):
        if getattr(self, "_telemetry_file", None):
            self._telemetry_file.close()
            self._telemetry_file = None
        if getattr(self, "_events_file", None):
            self._events_file.close()
            self._events_file = None
        self.write_metadata(status="complete")

    def __enter__(self):
        return self

    def __exit__(self, exc_type, exc, traceback):
        self.close()

