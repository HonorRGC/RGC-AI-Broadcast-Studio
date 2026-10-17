import json
from types import SimpleNamespace
import threading

import pytest

from production.highlights import programme_seconds, selected_highlights_job
from production.highlights_studio import save_highlight_selection
from production.highlights_player import HighlightsPlayer


def prepared(tmp_path):
    segments = [dict(kind=kind, title=title, start=start, end=end,
                     audio=f"audio-{i}.mp3", audio_seconds=10, narration=f"Saved narration {i}")
                for i, (kind, title, start, end) in enumerate([
                    ("intro", "Introduction", 0, 0), ("clip", "Lap 10 · Overtake", 50, 90),
                    ("clip", "Lap 20 · Pit Stops", 100, 140), ("outro", "Race Recap", 150, 150)])]
    job = {"schema_version": 1, "status": "ready", "session_num": 2,
           "options": {"title": "Race"}, "segments": segments}
    path = tmp_path / "programme.json"
    path.write_text(json.dumps(job))
    for segment in segments:
        (tmp_path / segment["audio"]).write_bytes(segment["narration"].encode())
    return path, job


def test_selection_persists_without_removing_segments_audio_or_options(tmp_path):
    path, original = prepared(tmp_path)
    saved = save_highlight_selection(path, {0, 2, 3})
    reloaded = json.loads(path.read_text())
    assert reloaded == saved
    assert len(saved["segments"]) == 4
    assert saved["status"] == "ready" and saved["options"] == original["options"]
    assert saved["segments"][1]["excluded"]
    assert saved["estimated_seconds"] < programme_seconds(original)
    for segment, before in zip(saved["segments"], original["segments"]):
        assert segment["narration"] == before["narration"]
        assert (tmp_path / segment["audio"]).read_bytes() == before["narration"].encode()
    restored = save_highlight_selection(path, range(4))
    assert not any(s["excluded"] for s in restored["segments"])
    assert programme_seconds(restored) == programme_seconds(original)


@pytest.mark.parametrize("selection", [[], [-1], [4], [0, 99], [True]])
def test_invalid_or_empty_selection_cannot_change_saved_programme(tmp_path, selection):
    path, original = prepared(tmp_path)
    before = path.read_bytes()
    with pytest.raises(ValueError):
        save_highlight_selection(path, selection)
    assert path.read_bytes() == before


def test_playback_omits_excluded_segments_and_uses_selected_progress(tmp_path):
    path, original = prepared(tmp_path)
    job = save_highlight_selection(path, {0, 2, 3})
    server = SimpleNamespace(lock=threading.Lock())
    player = HighlightsPlayer(job, SimpleNamespace(), server, SimpleNamespace(), tmp_path)
    assert [s["title"] for s in player.job["segments"]] == ["Introduction", "Lap 20 · Pit Stops", "Race Recap"]
    assert server.highlights["progress"] == "1 / 3"
    player.index = 1
    player.publish()
    assert player.segment["title"] == "Lap 20 · Pit Stops"
    assert server.highlights["progress"] == "2 / 3"
    assert len(job["segments"]) == 4


def test_programmes_without_selection_still_include_every_segment(tmp_path):
    path, original = prepared(tmp_path)
    assert selected_highlights_job(original)["segments"] == original["segments"]
    with pytest.raises(ValueError, match="at least one"):
        selected_highlights_job(dict(original, segments=[dict(s, excluded=True) for s in original["segments"]]))
