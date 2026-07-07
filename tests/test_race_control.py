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


def test_recent_trouble_can_supply_a_cautious_caution_cause_fallback():
    detector = IncidentDetector()
    results = [{"CarIdx": 0, "Position": 1, "LapsComplete": 5}]
    drivers = {0: {"name": "Driver One", "number": "1"}}
    detector.analyze(
        results,
        drivers,
        current_lap=5,
        track_surface_status=[3],
        lap_dist_pct_status=[0.50],
        est_time_status=[10.0],
        pit_road_status=[False],
    )
    detector.analyze(
        [{"CarIdx": 0, "Position": 3, "LapsComplete": 5}],
        drivers,
        current_lap=5,
        track_surface_status=[3],
        lap_dist_pct_status=[0.49],
        est_time_status=[11.0],
        pit_road_status=[False],
    )

    event = detector.build_caution_fallback(current_lap=5)

    assert event.trouble_type == "caution candidate"
    assert "may have found" in event.message
    assert event.car_idx == 0


def test_soft_incident_suppression_blocks_false_off_pace_calls():
    detector = IncidentDetector()
    results = [{"CarIdx": 0, "Position": 1, "LapsComplete": 5, "Incidents": 0}]
    drivers = {0: {"name": "Driver One", "number": "1"}}
    detector.analyze(
        results,
        drivers,
        current_lap=5,
        track_surface_status=[3],
        lap_dist_pct_status=[0.50],
        est_time_status=[10.0],
        pit_road_status=[False],
    )

    events = detector.analyze(
        [{"CarIdx": 0, "Position": 1, "LapsComplete": 5, "Incidents": 0}],
        drivers,
        current_lap=5,
        track_surface_status=[3],
        lap_dist_pct_status=[0.50],
        est_time_status=[20.0],
        pit_road_status=[False],
        suppress_soft_events=True,
    )

    assert events == []


def test_soft_incident_suppression_still_allows_incident_points():
    detector = IncidentDetector()
    results = [{"CarIdx": 0, "Position": 1, "LapsComplete": 5, "Incidents": 0}]
    drivers = {0: {"name": "Driver One", "number": "1"}}
    detector.analyze(
        results,
        drivers,
        current_lap=5,
        track_surface_status=[3],
        lap_dist_pct_status=[0.50],
        est_time_status=[10.0],
        pit_road_status=[False],
    )

    events = detector.analyze(
        [{"CarIdx": 0, "Position": 1, "LapsComplete": 5, "Incidents": 4}],
        drivers,
        current_lap=5,
        track_surface_status=[3],
        lap_dist_pct_status=[0.50],
        est_time_status=[20.0],
        pit_road_status=[False],
        suppress_soft_events=True,
    )

    assert events[0].trouble_type == "major incident"


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


def test_caution_uses_immediate_trouble_language():
    director = RaceDirector()
    queue = BroadcastQueue()

    director.handle_caution(queue, {"track_name": "Homestead"})

    assert queue.items[0].message.startswith("Trouble on the speedway")
    assert "caution is out" in queue.items[0].message


def test_one_to_green_preserves_a_pending_caution_pit_summary():
    director = RaceDirector()
    director.race_started = True
    queue = BroadcastQueue()
    queue.add(
        "A majority of the field has come to pit road.",
        category="caution_pit_summary",
        speaker="sarah",
    )
    queue.add(
        "Tonight's coverage is presented by RGC Motorsports.",
        category="sponsor_read",
        speaker="lead",
    )

    director.handle_one_to_green([], {}, queue, {"track_name": "Daytona"})

    assert any(item.category == "caution_pit_summary" for item in queue.items)
    assert any(item.category == "sponsor_read" for item in queue.items)
    assert any(
        item.dedupe_key == "race_control:one_to_green:restart"
        for item in queue.items
    )


def test_initial_one_to_green_is_not_called_a_restart():
    director = RaceDirector()
    queue = BroadcastQueue()
    queue.add("Welcome", category="opening_welcome")

    director.handle_one_to_green([], {}, queue, {"track_name": "Nashville"})

    assert "start" in queue.items[-1].message.lower()
    assert "pace car lights are off" in queue.items[-1].message.lower()
    assert "restart" not in queue.items[-1].message.lower()
    assert any(item.category == "opening_welcome" for item in queue.items)


def test_initial_one_to_green_does_not_jump_ahead_of_welcome():
    director = RaceDirector()
    queue = BroadcastQueue()
    queue.add(
        "Welcome to Nashville.",
        priority=10,
        category="opening_welcome",
    )

    director.handle_one_to_green([], {}, queue, {"track_name": "Nashville"})

    first = queue.next_item()
    assert first.category == "opening_welcome"


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
    assert queue.items[0].message.startswith("Five laps to go")


def test_white_flag_can_be_called_from_flag_even_if_lap_count_lags():
    director = RaceDirector()
    director.race_started = True
    queue = BroadcastQueue()

    director.handle_lap_calls(
        current_lap=8,
        total_laps=10,
        scheduler=queue,
        session_flags=director.WHITE_FLAG,
    )

    assert any("White flag" in item.message for item in queue.items)


def test_two_to_go_is_called_before_white_flag():
    director = RaceDirector()
    director.race_started = True
    queue = BroadcastQueue()

    director.handle_lap_calls(current_lap=48, total_laps=50, scheduler=queue)

    assert any("Two laps to go" in item.message for item in queue.items)
    assert any(item.dedupe_key == "race_control:two_to_go" for item in queue.items)


def test_long_race_reports_quarter_half_and_three_quarter_progress():
    director = RaceDirector()
    director.race_started = True
    queue = BroadcastQueue()

    director.handle_lap_calls(current_lap=20, total_laps=80, scheduler=queue)
    director.handle_lap_calls(current_lap=40, total_laps=80, scheduler=queue)
    director.handle_lap_calls(current_lap=60, total_laps=80, scheduler=queue)

    messages = [item.message for item in queue.items]
    assert any("60 laps remain" in message for message in messages)
    assert any("Halfway" in message and "40 laps remain" in message for message in messages)
    assert any("20 laps to go" in message for message in messages)


def test_finish_rundown_is_limited_to_top_ten():
    director = RaceDirector()
    results = [
        {"CarIdx": index, "Position": index + 1} for index in range(12)
    ]
    drivers = {
        index: {"name": f"Driver {index + 1}", "number": str(index + 1)}
        for index in range(12)
    }

    rundown = director.build_finish_rundown(results, drivers, max_cars=10)

    assert "Driver 10" in rundown
    assert "Driver 11" not in rundown
    assert "Driver 12" not in rundown


def test_checkered_queues_finish_rundown_then_signoff():
    director = RaceDirector()
    queue = BroadcastQueue()
    results = [
        {"CarIdx": index, "Position": index + 1} for index in range(3)
    ]
    drivers = {
        index: {"name": f"Driver {index + 1}", "number": str(index + 1)}
        for index in range(3)
    }

    director.handle_checkered(
        results,
        drivers,
        queue,
        {"track_name": "Homestead Miami Speedway"},
    )
    for _ in range(4):
        director.handle_post_race_results(
            results,
            drivers,
            queue,
            {"track_name": "Homestead Miami Speedway"},
        )

    categories = [item.category for item in queue.items]
    assert categories == ["race_control", "post_race", "post_race_signoff"]
    assert queue.items[1].priority > queue.items[2].priority
    assert "Thank you for watching" in queue.items[2].message
    assert "Homestead Miami Speedway" in queue.items[2].message
    assert "Jeff and Sarah" in queue.items[2].message


def test_finish_rundown_formats_zero_based_positions():
    director = RaceDirector()
    results = [
        {"CarIdx": 10, "Position": 0},
        {"CarIdx": 20, "Position": 1},
    ]
    drivers = {
        10: {"name": "Winner Driver", "number": "10"},
        20: {"name": "Runner Up", "number": "20"},
    }

    rundown = director.build_finish_rundown(results, drivers, max_cars=2)

    assert "first, the 10 of Winner Driver" in rundown
    assert "second, the 20 of Runner Up" in rundown


def test_cool_down_session_state_is_treated_as_checkered():
    director = RaceDirector()

    phase = director.detect_phase(
        session_flags=0,
        results=[],
        current_lap=0,
        total_laps=0,
        session_state=director.SESSION_STATE_COOL_DOWN,
    )

    assert phase == RacePhase.CHECKERED
