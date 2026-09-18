import json

from broadcast.broadcast_queue import ScheduledBroadcast
from production.broadcast_capture import BroadcastCaptureRecorder
from replay.replay_telemetry import ReplayTelemetry


def test_replay_implements_live_telemetry_read_contract(tmp_path):
    path = tmp_path / "race.jsonl"
    snapshots = [
        {
            "lap": 0,
            "total_laps": 20,
            "session_flags": 0,
            "track_info": {"track_name": "Daytona"},
            "results": [{"CarIdx": 1, "Position": 1, "LapsComplete": 0}],
            "driver_lookup": {"1": {"name": "Alex Driver", "number": "7"}},
        },
        {
            "lap": 1,
            "total_laps": 20,
            "session_flags": 4,
            "results": [{"CarIdx": 1, "Position": 1, "LapsComplete": 1}],
            "driver_lookup": {"1": {"name": "Alex Driver", "number": "7"}},
        },
    ]
    path.write_text(
        "".join(json.dumps(snapshot) + "\n" for snapshot in snapshots),
        encoding="utf-8",
    )

    replay = ReplayTelemetry(path)

    assert replay.startup()
    assert replay.get_lap() == 0
    assert replay.get_driver_lookup()[1]["name"] == "Alex Driver"
    replay.next_snapshot()
    assert replay.get_lap() == 1
    assert replay.get_session_flags() == 4


def test_recorded_broadcast_loads_original_items(tmp_path):
    path = tmp_path / "broadcast_capture.jsonl"
    path.write_text(
        json.dumps({"lap": 4, "session_num": 0, "session_time": 120.0}) + "\n",
        encoding="utf-8",
    )
    path.with_suffix(".events.jsonl").write_text(
        json.dumps(
            {
                "snapshot_index": 0,
                "captured_at": 10.0,
                "priority": 8,
                "message": "The battle for second is tightening up.",
                "category": "battle",
                "speaker": "jeff",
            }
        )
        + "\n",
        encoding="utf-8",
    )

    replay = ReplayTelemetry(path)
    item = replay.recorded_item_for_current_snapshot()

    assert isinstance(item, ScheduledBroadcast)
    assert item.message == "The battle for second is tightening up."
    assert item.speaker == "jeff"
    assert replay.recorded_item_for_current_snapshot() is None


def test_capture_recorder_writes_telemetry_events_and_metadata(tmp_path, monkeypatch):
    output = tmp_path / "race.jsonl"
    snapshot = SimpleSnapshot()
    monkeypatch.setattr(
        "production.broadcast_capture.TelemetrySnapshot.from_telemetry",
        lambda telemetry, timestamp=0.0: snapshot,
    )
    recorder = BroadcastCaptureRecorder(output_path=output)
    recorder.record_snapshot(object())
    recorder.record_item(
        ScheduledBroadcast(priority=7, message="Caution is out.", speaker="lead")
    )
    recorder.close()

    assert json.loads(output.read_text(encoding="utf-8"))["lap"] == 12
    event = json.loads(output.with_suffix(".events.jsonl").read_text(encoding="utf-8"))
    assert event["snapshot_index"] == 0
    assert event["message"] == "Caution is out."
    metadata = json.loads(output.with_suffix(".capture.json").read_text(encoding="utf-8"))
    assert metadata["status"] == "complete"
    assert metadata["snapshot_count"] == 1


class SimpleSnapshot:
    def to_dict(self):
        return {"lap": 12, "session_num": 0, "session_time": 55.0}
