from types import SimpleNamespace

from production.league_manager import (
    LeagueProfile,
    ScheduleEvent,
    default_scoring_system,
    load_race_results,
    load_schedule,
    save_league_profile,
    save_schedule,
    save_scoring_system,
)
from production.league_results_recorder import AutomaticLeagueResultsRecorder


class Source:
    def get_results(self):
        return [
            {"CarIdx": 1, "Position": 0, "StartingPosition": 1, "LapsComplete": 50, "LapsLed": 35, "FastestTime": 30.1, "Incidents": 0},
            {"CarIdx": 2, "Position": 1, "StartingPosition": 0, "LapsComplete": 50, "LapsLed": 15, "FastestTime": 30.2, "Incidents": 2},
        ]

    def get_driver_lookup(self):
        return {1: {"name": "Winner One", "number": "7"}, 2: {"name": "Runner Up", "number": "12"}}

    def get_track_info(self):
        return {"TrackDisplayName": "Kansas Speedway"}

    def get_session_state(self):
        return 5


def test_automatic_results_wait_for_stability_then_save_once(tmp_path):
    save_league_profile(tmp_path / "league.json", LeagueProfile(name="Test League"))
    save_schedule(tmp_path / "schedule.json", [ScheduleEvent(1, "10-04-2026", "Kansas Speedway", laps=50, event_name="Midwest 50")])
    save_scoring_system(tmp_path / "scoring.json", default_scoring_system())
    engine = SimpleNamespace(
        race_director=SimpleNamespace(post_race_results_queued=True),
        openai_director=SimpleNamespace(is_enabled=lambda: False),
        broadcast_queue=SimpleNamespace(items=[], busy_until=0),
    )
    recorder = AutomaticLeagueResultsRecorder(True, tmp_path)

    messages = [recorder.update(Source(), engine) for _ in range(5)]

    assert messages[:4] == [None, None, None, None]
    assert "automatically saved Round 1" in messages[4]
    assert len(load_race_results(tmp_path / "results.json")) == 1
    assert [(entry.name, entry.car_number) for entry in load_race_results(tmp_path / "results.json")[0].entries] == [
        ("Winner One", "7"),
        ("Runner Up", "12"),
    ]
    assert load_schedule(tmp_path / "schedule.json")[0].status == "Completed"
    assert (tmp_path / "drivers.csv").read_text(encoding="utf-8").count("Winner One") == 1
    assert recorder.update(Source(), engine) is None


def test_ai_results_wait_until_post_race_queue_and_voice_are_finished(tmp_path):
    save_schedule(tmp_path / "schedule.json", [ScheduleEvent(1, "10-04-2026", "Kansas Speedway", laps=50)])
    save_scoring_system(tmp_path / "scoring.json", default_scoring_system())
    queue = SimpleNamespace(items=[object()], busy_until=0)
    engine = SimpleNamespace(
        race_director=SimpleNamespace(post_race_results_queued=True),
        openai_director=SimpleNamespace(is_enabled=lambda: True),
        broadcast_queue=queue,
    )
    recorder = AutomaticLeagueResultsRecorder(True, tmp_path)

    for _ in range(6):
        assert recorder.update(Source(), engine) is None

    queue.items = []
    assert "automatically saved" in recorder.update(Source(), engine)
