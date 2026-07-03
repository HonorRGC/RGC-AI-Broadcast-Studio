import pytest

from broadcast.broadcast_queue import BroadcastQueue
from broadcaster.race_director import RaceDirector, RacePhase
from production.incident_detector import IncidentDetector
from production.race_state_tracker import RaceStateTracker


def test_one_to_green_wins_when_caution_bits_are_also_set():
    director = RaceDirector()
    flags = director.ONE_LAP_TO_GREEN | director.CAUTION

    phase = director.detect_phase(flags, [], current_lap=10, total_laps=50)

    assert phase == RacePhase.ONE_TO_GREEN


def test_lap_wrap_is_not_reported_as_backward_movement():
    detector = IncidentDetector()

    assert detector.calculate_lap_distance_loss(0.98, 0.02) == 0.0
    assert detector.calculate_lap_distance_loss(0.50, 0.45) == pytest.approx(0.05)


def test_green_run_counter_counts_laps_not_update_ticks():
    tracker = RaceStateTracker()
    green = RaceDirector.GREEN_FLAG

    tracker.update(current_lap=1, total_laps=50, session_flags=green)
    tracker.update(current_lap=1, total_laps=50, session_flags=green)
    tracker.update(current_lap=2, total_laps=50, session_flags=green)

    assert tracker.get_state().green_lap_count == 2


def test_green_flag_clears_stale_opening_messages():
    director = RaceDirector()
    queue = BroadcastQueue()
    queue.add("Welcome", category="opening_welcome")
    director.previous_phase = RacePhase.FORMATION
    director.phase = RacePhase.GREEN

    director.handle_green_flag(queue, {"track_name": "Daytona"})

    assert [item.category for item in queue.items] == ["race_control"]


def test_new_race_control_state_replaces_an_unspoken_old_state():
    director = RaceDirector()
    director.race_started = True
    queue = BroadcastQueue()
    queue.add(
        "Caution is out",
        category="race_control",
        protected=True,
        dedupe_key="race_control:caution",
    )

    director.handle_one_to_green([], {}, queue, {"track_name": "Daytona"})

    assert len(queue.items) == 1
    assert queue.items[0].dedupe_key == "race_control:one_to_green:restart"


def test_initial_one_to_green_is_not_called_a_restart():
    director = RaceDirector()
    queue = BroadcastQueue()
    queue.add("Welcome", category="opening_welcome")

    director.handle_one_to_green([], {}, queue, {"track_name": "Nashville"})

    assert "start" in queue.items[-1].message.lower()
    assert "restart" not in queue.items[-1].message.lower()
    assert any(item.category == "opening_welcome" for item in queue.items)


def test_initial_green_is_not_called_a_restart():
    director = RaceDirector()
    queue = BroadcastQueue()
    director.previous_phase = RacePhase.ONE_TO_GREEN
    director.phase = RacePhase.GREEN

    director.handle_green_flag(queue, {"track_name": "Nashville"})

    assert "back in the air" not in queue.items[0].message.lower()
    assert "we are racing at nashville" in queue.items[0].message.lower()


def test_restart_green_uses_restart_language():
    director = RaceDirector()
    director.race_started = True
    director.previous_phase = RacePhase.ONE_TO_GREEN
    director.phase = RacePhase.GREEN
    queue = BroadcastQueue()

    director.handle_green_flag(queue, {"track_name": "Nashville"})

    assert "back in the air" in queue.items[0].message.lower()


def test_short_race_does_not_immediately_call_the_closing_stage():
    director = RaceDirector()
    director.race_started = True
    queue = BroadcastQueue()

    director.handle_lap_calls(current_lap=1, total_laps=10, scheduler=queue)
    assert queue.items == []

    director.handle_lap_calls(current_lap=5, total_laps=10, scheduler=queue)
    assert len(queue.items) == 1
    assert queue.items[0].message.startswith("5 laps to go")
