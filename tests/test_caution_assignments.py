import json
from types import SimpleNamespace
import pytest
from production.caution_assignments import CautionAssignments, handle_assignment, attach_replay_plan


def job(sid=123):
    return {"track": "Richmond", "session_num": 2, "subsession_id": sid, "source": "capture.jsonl",
            "cautions": [{"id": "2:300.000", "lap": 10, "time": 300}],
            "drivers": [{"car_idx": 0, "driver_name": "T.J. Lee"}, {"car_idx": 1, "driver_name": "Chuck Sweeting"}]}


def test_assignments_persist_for_same_race_and_do_not_leak_between_races(tmp_path):
    plan = CautionAssignments(job(), tmp_path)
    plan.assign("2:300.000", "0")
    loaded = CautionAssignments(job(), tmp_path)
    assert loaded.target("2:300.000") == 0
    assert loaded.for_time(2, 301)[1] == 0
    assert loaded.for_time(1, 300) is None
    assert loaded.for_time(2, 320) is None
    assert CautionAssignments(job(456), tmp_path).target("2:300.000") is None
    loaded.assign("2:300.000", "")
    assert CautionAssignments(job(), tmp_path).target("2:300.000") is None


def test_rejects_unknown_cautions_and_drivers(tmp_path):
    plan = CautionAssignments(job(), tmp_path)
    with pytest.raises(ValueError):
        plan.assign("2:999.000", 1)
    with pytest.raises(ValueError):
        plan.assign("2:300.000", 99)
    assert not plan.assignments and not plan.path.exists()
    assert handle_assignment(SimpleNamespace(caution_assignments=plan), "caution_driver_assign",
                             {"caution_id": "2:300.000", "car_idx": "1"})
    assert plan.target("2:300.000") == 1


def test_live_source_never_loads_replay_assignments():
    source = SimpleNamespace(get_weekend_info=lambda: {"SimMode": "full", "SubSessionID": 123})
    server = SimpleNamespace()
    attach_replay_plan(source, server)
    assert not hasattr(source, "caution_assignments")
    assert not hasattr(server, "caution_assignments")


def test_stale_replay_choices_cannot_apply_after_switching_to_live_or_another_race(tmp_path):
    plan = CautionAssignments(job(), tmp_path)
    source = SimpleNamespace(get_weekend_info=lambda: {"SimMode": "replay", "SubSessionID": 123})
    assert plan.applies_to_source(source)
    source.get_weekend_info = lambda: {"SimMode": "full", "SubSessionID": 123}
    assert not plan.applies_to_source(source)
    source.get_weekend_info = lambda: {"SimMode": "replay", "SubSessionID": 456}
    assert not plan.applies_to_source(source)
