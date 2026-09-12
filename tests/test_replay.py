import json

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
