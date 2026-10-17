import json
from pathlib import Path
import pytest
from production.capture_library import capture_bundles, set_capture_retention


def make_bundle(root, name="race", pid=123, started=100):
    root.mkdir(parents=True, exist_ok=True)
    (root / (name + ".jsonl")).write_text("telemetry")
    (root / (name + ".events.jsonl")).write_text("events")
    (root / (name + ".capture.json")).write_text(json.dumps({"process_id": pid, "started_at": started, "retention": "pending"}))


def test_keep_and_discard_only_the_stopped_broadcast(tmp_path):
    make_bundle(tmp_path)
    make_bundle(tmp_path, "other", pid=456)
    make_bundle(tmp_path, "old", started=10)
    bundle, = capture_bundles(tmp_path, 123, started_after=90)
    assert bundle["size_bytes"] > 0
    set_capture_retention(bundle, True, tmp_path)
    assert json.loads(bundle["paths"][-1].read_text())["retention"] == "kept"
    assert all(path.is_file() for path in bundle["paths"])
    set_capture_retention(bundle, False, tmp_path)
    assert not any(path.exists() for path in bundle["paths"])
    assert (tmp_path / "other.jsonl").exists()
    assert (tmp_path / "old.jsonl").exists()


def test_discard_validates_all_paths_before_removing_any_file(tmp_path):
    root = tmp_path / "recordings"
    make_bundle(root)
    outside = tmp_path / "other.capture.json"
    outside.write_text("keep me")
    bundle, = capture_bundles(root, 123)
    bundle["paths"] = (*bundle["paths"][:2], outside)
    with pytest.raises(ValueError):
        set_capture_retention(bundle, False, root)
    assert (root / "race.jsonl").is_file()
    assert outside.read_text() == "keep me"


def test_bad_metadata_and_unknown_process_do_not_select_old_races(tmp_path):
    make_bundle(tmp_path)
    (tmp_path / "broken.capture.json").write_text("{")
    assert capture_bundles(tmp_path, None) == []
    assert capture_bundles(tmp_path, 999) == []
    assert len(capture_bundles(tmp_path, 123)) == 1
