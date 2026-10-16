import json
import os
import uuid
from copy import deepcopy
import time
from dataclasses import asdict
from datetime import datetime
from pathlib import Path

from replay.telemetry_snapshot import TelemetrySnapshot


class BroadcastCaptureRecorder:
    """Persist live telemetry and approved broadcast items for later playback."""

    def __init__(self, output_path=None, root=None, event_context=None):
        root = Path(root or Path.cwd())
        if output_path:
            self.telemetry_path = Path(output_path)
        else:
            stamp = datetime.now().strftime("%Y-%m-%d_%H-%M-%S")
            self.telemetry_path = root / "recordings" / f"broadcast_capture_{stamp}.jsonl"
        if not output_path and self.telemetry_path.exists():
            self.telemetry_path = self.telemetry_path.with_name(self.telemetry_path.stem + "_" + uuid.uuid4().hex[:8] + ".jsonl")
        self.event_context = dict(event_context or {})
        self.capture_id = uuid.uuid4().hex
        self.events_path = self.telemetry_path.with_suffix(".events.jsonl")
        self.metadata_path = self.telemetry_path.with_suffix(".capture.json")
        self.telemetry_path.parent.mkdir(parents=True, exist_ok=True)
        self.snapshot_index = -1
        self.started_at = time.time()
        self.previous_payload = None
        self.last_snapshot = {}
        self.last_checkpoint = 0.0
        self.interruptions = []
        self.stop_reason = None
        self._telemetry_file = self.telemetry_path.open("w", encoding="utf-8", buffering=1)
        self._events_file = self.events_path.open("w", encoding="utf-8", buffering=1)
        self.write_metadata(status="recording")

    def record_snapshot(self, telemetry):
        snapshot = TelemetrySnapshot.from_telemetry(telemetry, timestamp=time.time())
        payload = snapshot.to_dict()
        next_index = self.snapshot_index + 1
        entry = payload
        if self.previous_payload is not None and next_index % 100:
            entry = {"_capture_delta": {key: value for key, value in payload.items()
                                        if value != self.previous_payload.get(key)}}
        self._telemetry_file.write(json.dumps(entry, separators=(",", ":")) + "\n")
        self.snapshot_index = next_index
        self.previous_payload = deepcopy(payload)
        self.last_snapshot = {key: payload.get(key) for key in
                              ("timestamp", "lap", "total_laps", "session_num", "session_time", "session_state", "session_flags")}
        if time.time() - self.last_checkpoint >= 1:
            self.write_metadata("recording")
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
            "format": "rgc-recorded-broadcast-v2",
            "capture_id": self.capture_id,
            "event": self.event_context,
            "process_id": os.getpid(),
            "retention": "pending",
            "status": status,
            "started_at": self.started_at,
            "completed_at": time.time() if status == "complete" else None,
            "telemetry_file": self.telemetry_path.name,
            "events_file": self.events_path.name,
            "stop_reason": self.stop_reason,
            "last_snapshot": self.last_snapshot,
            "telemetry_interruptions": self.interruptions,
            "updated_at": time.time(),
            "snapshot_count": max(0, self.snapshot_index + 1),
        }
        temporary = self.metadata_path.with_suffix(".tmp")
        temporary.write_text(json.dumps(payload, indent=2), encoding="utf-8")
        temporary.replace(self.metadata_path)
        self.last_checkpoint = time.time()

    def connection_lost(self):
        if not self.interruptions or self.interruptions[-1].get("resumed_at"):
            self.interruptions.append({"lost_at": time.time(), "after_snapshot": self.snapshot_index})
            print("Capture paused: local iRacing telemetry unavailable; waiting to reconnect.", flush=True)
            self.write_metadata("waiting_for_telemetry")

    def connection_restored(self):
        if self.interruptions and not self.interruptions[-1].get("resumed_at"):
            self.interruptions[-1]["resumed_at"] = time.time()
            print("Capture resumed: iRacing telemetry reconnected.", flush=True)
            self.write_metadata("recording")

    def close(self, reason="stopped"):
        self.stop_reason = reason
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
        self.close(reason=f"error: {exc}" if exc else "stopped")

