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


def test_recorded_broadcast_advances_by_original_elapsed_time(tmp_path):
    path = tmp_path / "timed_capture.jsonl"
    snapshots = [
        {"lap": 1, "timestamp": 1000.0, "session_time": 10.0},
        {"lap": 2, "timestamp": 1001.0, "session_time": 11.0},
        {"lap": 3, "timestamp": 1002.0, "session_time": 12.0},
        {"lap": 4, "timestamp": 1003.0, "session_time": 13.0},
    ]
    path.write_text(
        "".join(json.dumps(snapshot) + "\n" for snapshot in snapshots),
        encoding="utf-8",
    )
    now = [50.0]
    replay = ReplayTelemetry(path, clock=lambda: now[0])
    replay.start_timed_playback()

    now[0] = 50.4
    replay.next_snapshot()
    assert replay.get_lap() == 1

    now[0] = 52.2
    replay.next_snapshot()
    assert replay.get_lap() == 3

    now[0] = 53.1
    replay.next_snapshot()
    assert replay.get_lap() == 4


def test_recorded_broadcast_can_start_at_current_iracing_session(tmp_path):
    path = tmp_path / "multi_session.jsonl"
    snapshots = [
        {"lap": 0, "timestamp": 1000.0, "session_num": 0, "session_type": "Practice", "session_time": 20.0},
        {"lap": 0, "timestamp": 1060.0, "session_num": 1, "session_type": "Qualify", "session_time": 10.0},
        {"lap": 0, "timestamp": 1070.0, "session_num": 1, "session_type": "Qualify", "session_time": 20.0},
        {"lap": 1, "timestamp": 1120.0, "session_num": 2, "session_type": "Race", "session_time": 5.0},
    ]
    path.write_text(
        "".join(json.dumps(snapshot) + "\n" for snapshot in snapshots),
        encoding="utf-8",
    )
    path.with_suffix(".events.jsonl").write_text(
        "\n".join(
            [
                json.dumps({"snapshot_index": 0, "priority": 5, "message": "Practice call"}),
                json.dumps({"snapshot_index": 1, "priority": 5, "message": "Qualifying call"}),
                json.dumps({"snapshot_index": 3, "priority": 5, "message": "Race call"}),
            ]
        )
        + "\n",
        encoding="utf-8",
    )
    controller = FakeReplayController(session_num=1, session_time=19.0, session_type="Qualify")
    replay = ReplayTelemetry(path, clock=lambda: 50.0).attach_controller(controller)

    assert replay.synchronize_to_controller(force=True)
    assert replay.current_index == 2
    assert replay.get_session_type() == "Qualify"
    assert replay.recorded_item_for_current_snapshot() is None

    controller.session_num = 2
    controller.session_time = 5.0
    controller.session_type = "Race"
    assert replay.synchronize_to_controller()
    assert replay.current_index == 3
    assert replay.recorded_item_for_current_snapshot().message == "Race call"
    assert replay.seek_replay_session_time(2, 3.5)
    assert replay.return_to_live()
    assert controller.seek_calls == [(2, 3.5), (2, 5.0)]

    controller.session_time = 9999.0
    assert not replay.synchronize_to_controller()
    assert replay.current_index == 3


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


class FakeReplayController:
    def __init__(self, session_num, session_time, session_type):
        self.session_num = session_num
        self.session_time = session_time
        self.session_type = session_type
        self.seek_calls = []

    def get_current_session_num(self):
        return self.session_num

    def get_session_time(self):
        return self.session_time

    def get_session_type(self):
        return self.session_type

    def seek_replay_session_time(self, session_num, session_time):
        self.seek_calls.append((session_num, session_time))
        return True
