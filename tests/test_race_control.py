import time

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
    assert event.replay_confidence == "low"
    assert event.replay_session_time is None


def test_multi_signal_caution_candidate_keeps_replay_session_time():
    detector = IncidentDetector()
    drivers = {0: {"name": "Driver One", "number": "1"}}
    detector.analyze(
        [{"CarIdx": 0, "Position": 1, "LapsComplete": 5}],
        drivers,
        current_lap=5,
        track_surface_status=[3],
        lap_dist_pct_status=[0.50],
        est_time_status=[10.0],
        pit_road_status=[False],
        session_time=120.0,
    )
    detector.analyze(
        [{"CarIdx": 0, "Position": 5, "LapsComplete": 5}],
        drivers,
        current_lap=5,
        track_surface_status=[0],
        lap_dist_pct_status=[0.46],
        est_time_status=[15.0],
        pit_road_status=[False],
        session_time=124.0,
    )

    event = detector.build_caution_fallback(current_lap=5)

    assert event.replay_confidence == "high"
    assert event.replay_session_time == pytest.approx(124.0)


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


def test_pre_race_yellow_does_not_count_as_live_caution():
    tracker = RaceStateTracker()
    yellow = RaceDirector.YELLOW_FLAG
    green = RaceDirector.GREEN_FLAG

    tracker.update(current_lap=0, total_laps=50, session_flags=yellow)

    assert tracker.get_state().caution_count == 0

    tracker.update(current_lap=1, total_laps=50, session_flags=green)
    tracker.update(current_lap=2, total_laps=50, session_flags=yellow)

    assert tracker.get_state().caution_count == 1


def test_green_flag_clears_stale_opening_messages():
    director = RaceDirector()
    queue = BroadcastQueue()
    queue.add("Welcome", category="opening_welcome")
    director.previous_phase = RacePhase.FORMATION
    director.phase = RacePhase.GREEN

    director.handle_green_flag(queue, {"track_name": "Daytona"})

    assert [item.category for item in queue.items] == ["race_control"]


def test_green_flag_waits_for_pending_sponsor_read():
    director = RaceDirector()
    queue = BroadcastQueue()
    queue.add("Welcome", category="opening_welcome")
    queue.add(
        "Tonight's coverage is presented by RGC Motorsports.",
        priority=8,
        category="sponsor_read",
        protected=True,
        speaker="lead",
        dedupe_key="sponsor_read:opening",
    )
    director.previous_phase = RacePhase.ONE_TO_GREEN
    director.phase = RacePhase.GREEN

    director.handle_green_flag(queue, {"track_name": "Daytona"})

    categories = [item.category for item in queue.items]
    assert "opening_welcome" not in categories
    assert categories == ["sponsor_read", "race_control"]
    assert queue.next_item().category == "sponsor_read"
    green = queue.items[0]
    assert green.message == "We are under green at Daytona."


def test_delayed_restart_green_uses_back_under_green_wording():
    director = RaceDirector()
    director.race_started = True
    queue = BroadcastQueue()
    queue.add(
        "Tonight's coverage is presented by RGC Motorsports.",
        priority=8,
        category="sponsor_read",
        protected=True,
        speaker="lead",
        dedupe_key="sponsor_read:caution",
    )
    director.previous_phase = RacePhase.ONE_TO_GREEN
    director.phase = RacePhase.GREEN

    director.handle_green_flag(queue, {"track_name": "Daytona"})

    green = [item for item in queue.items if item.category == "race_control"][0]
    assert green.message == "We are back under green at Daytona."
    assert "Green flag is back in the air" not in green.message


def test_green_flag_does_not_interrupt_active_sponsor_read():
    director = RaceDirector()
    queue = BroadcastQueue()
    queue.add(
        "Tonight's coverage is presented by RGC Motorsports.",
        priority=8,
        category="sponsor_read",
        protected=True,
        speaker="lead",
        dedupe_key="sponsor_read:opening",
    )
    now = time.time()
    sponsor = queue.next_item(now=now)
    assert sponsor.category == "sponsor_read"
    busy_until = queue.busy_until
    director.previous_phase = RacePhase.ONE_TO_GREEN
    director.phase = RacePhase.GREEN

    director.handle_green_flag(queue, {"track_name": "Daytona"})

    assert queue.busy_until == busy_until
    assert queue.next_item(now=now) is None
    assert any(item.category == "race_control" for item in queue.items)


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
    director.race_started = True
    queue = BroadcastQueue()

    director.handle_caution(queue, {"track_name": "Homestead"})

    assert queue.items[0].message.startswith("Trouble on the speedway")
    assert "caution is out" in queue.items[0].message
    assert "could have brought out the caution" not in queue.items[0].message
    assert queue.items[0].camera_focus_incident is True
    assert queue.items[0].camera_incident_group == "Far Chase"


def test_admin_caution_is_called_as_race_control_caution():
    director = RaceDirector()
    director.race_started = True
    director.mark_admin_caution_pending()
    queue = BroadcastQueue()

    director.handle_caution(queue, {"track_name": "Homestead"})

    assert queue.items[0].message.startswith("Race control has put out the caution")
    assert "Trouble on the speedway" not in queue.items[0].message
    assert queue.items[0].dedupe_key == "race_control:admin_caution"
    assert queue.items[0].camera_focus_incident is False
    assert director.admin_caution_pending is False


def test_extended_yellow_is_not_called_new_trouble():
    director = RaceDirector()
    director.race_started = True
    director.previous_phase = RacePhase.ONE_TO_GREEN
    queue = BroadcastQueue()

    director.handle_caution(queue, {"track_name": "Homestead"})

    assert "yellow is being extended" in queue.items[0].message
    assert "Trouble on the speedway" not in queue.items[0].message
    assert queue.items[0].dedupe_key == "race_control:caution_extended"
    assert queue.items[0].camera_focus_incident is False


def test_initial_pace_lap_extension_does_not_interrupt_starting_lineup():
    director = RaceDirector()
    director.race_started = False
    director.previous_phase = RacePhase.ONE_TO_GREEN
    director.one_to_green_announced = True
    queue = BroadcastQueue()
    queue.add(
        "Starting third, the 34 of T.J. Lee.",
        priority=9,
        category="opening_field_rundown_1",
        speaker="jeff",
        protected=False,
        dedupe_key="opening_field_rundown_1",
    )

    director.handle_caution(queue, {"track_name": "EchoPark Speedway"})

    assert len(queue.items) == 2
    assert queue.items[0].category == "opening_field_rundown_1"
    assert queue.items[1].dedupe_key == "race_control:pre_start_extension"
    assert "adding another pace lap before the start" in queue.items[1].message
    assert "serve any pre-race penalties" in queue.items[1].message
    assert director.one_to_green_announced is False


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
    assert next(item for item in queue.items if item.dedupe_key == "race_control:two_to_go").message == "Two laps to go."


def test_final_lap_calls_wait_for_current_broadcast_to_finish():
    director = RaceDirector()
    director.race_started = True
    queue = BroadcastQueue()
    queue.busy_until = 999

    director.handle_lap_calls(current_lap=48, total_laps=50, scheduler=queue)

    assert any(item.dedupe_key == "race_control:two_to_go" for item in queue.items)
    assert queue.busy_until == 999


def test_only_key_final_lap_calls_are_announced():
    expected = {
        45: ("Five laps to go", "race_control:five_to_go"),
        48: ("Two laps to go", "race_control:two_to_go"),
    }

    for current_lap, (text, key) in expected.items():
        director = RaceDirector()
        director.race_started = True
        queue = BroadcastQueue()

        director.handle_lap_calls(current_lap=current_lap, total_laps=50, scheduler=queue)

        assert any(text in item.message for item in queue.items)
        assert any(item.dedupe_key == key for item in queue.items)


def test_four_and_three_to_go_are_not_announced():
    for current_lap in (46, 47):
        director = RaceDirector()
        director.race_started = True
        queue = BroadcastQueue()

        director.handle_lap_calls(current_lap=current_lap, total_laps=50, scheduler=queue)

        assert queue.items == []


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
    assert all("Autism Awareness" in message for message in messages)
    assert all("This race update is presented" in message for message in messages)


def test_progress_milestone_sponsor_can_be_disabled():
    director = RaceDirector()
    director.race_started = True
    director.progress_sponsor_cause = ""
    queue = BroadcastQueue()

    director.handle_lap_calls(current_lap=20, total_laps=80, scheduler=queue)

    assert queue.items
    assert "Autism Awareness" not in queue.items[0].message


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


def test_finish_rundown_can_include_entire_field():
    director = RaceDirector()
    results = [
        {"CarIdx": index, "Position": index + 1} for index in range(12)
    ]
    drivers = {
        index: {"name": f"Driver {index + 1}", "number": str(index + 1)}
        for index in range(12)
    }

    rundown = director.build_finish_rundown(results, drivers, max_cars=None)

    assert "Driver 1" in rundown
    assert "Driver 12" in rundown


def test_post_race_recap_includes_key_race_summary_details():
    director = RaceDirector()
    results = [
        {
            "CarIdx": 0,
            "Position": 1,
            "StartingPosition": 4,
            "LapsLed": 12,
            "FastestLapTime": 31.884,
            "LapsBehind": 0,
        },
        {
            "CarIdx": 1,
            "Position": 2,
            "StartingPosition": 10,
            "LapsLed": 18,
            "FastestLapTime": 31.221,
            "LapsBehind": 0,
        },
        {
            "CarIdx": 2,
            "Position": 3,
            "StartingPosition": 3,
            "LapsBehind": 1,
        },
    ]
    drivers = {
        0: {"name": "Winner Driver", "number": "10"},
        1: {"name": "Big Mover", "number": "2"},
        2: {"name": "Third Driver", "number": "3"},
    }

    recap = director.build_post_race_recap(
        results,
        drivers,
        "Homestead Miami Speedway",
    )

    assert "Final race recap from Homestead Miami Speedway" in recap
    assert "the 10 of Winner Driver gets the win" in recap
    assert "most laps led belonged to the 2 of Big Mover" in recap
    assert "18 laps" in recap
    assert "biggest mover was the 2 of Big Mover" in recap
    assert "up 8 spots" in recap
    assert "Fastest lap went to the 2 of Big Mover at 31.221 seconds" in recap
    assert "2 of the 3 starters finished on the lead lap" in recap


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
    for _ in range(20):
        director.handle_post_race_results(
            results,
            drivers,
            queue,
            {"track_name": "Homestead Miami Speedway"},
        )

    categories = [item.category for item in queue.items]
    assert categories == [
        "race_control",
        "post_race_story",
        "post_race",
        "post_race_recap",
        "post_race_signoff",
    ]
    assert queue.items[0].camera_sequence_steps == ((0, "TV Mixed", 0),)
    assert queue.items[1].priority > queue.items[2].priority
    assert queue.items[2].priority > queue.items[3].priority
    assert queue.items[3].priority > queue.items[4].priority
    assert "top ten" in queue.items[1].message.lower()
    assert "Final race recap from Homestead Miami Speedway" in queue.items[3].message
    assert "Thank you for watching" in queue.items[4].message
    assert "Homestead Miami Speedway" in queue.items[4].message
    assert "Jeff and Sarah" in queue.items[4].message


def test_checkered_with_interviews_queues_handoff_instead_of_signoff():
    director = RaceDirector(post_race_interviews_enabled=True)
    queue = BroadcastQueue()
    results = [
        {"CarIdx": index, "Position": index + 1} for index in range(3)
    ]
    drivers = {
        0: {"name": "Winner Driver", "number": "1"},
        1: {"name": "Second Place", "number": "2"},
        2: {"name": "Third Place", "number": "3"},
    }

    director.handle_checkered(
        results,
        drivers,
        queue,
        {"track_name": "Homestead Miami Speedway"},
    )
    for _ in range(20):
        director.handle_post_race_results(
            results,
            drivers,
            queue,
            {"track_name": "Homestead Miami Speedway"},
        )

    categories = [item.category for item in queue.items]
    assert categories == [
        "race_control",
        "post_race_story",
        "post_race",
        "post_race_recap",
        "post_race_interviews",
    ]
    assert queue.items[0].camera_sequence_steps == ((0, "TV Mixed", 0),)
    assert "Final race recap" in queue.items[3].message
    assert "top three are headed to post-race interviews" in queue.items[4].message
    assert "Third Place first" in queue.items[4].message
    assert "Second Place" in queue.items[4].message
    assert "Winner Driver" in queue.items[4].message
    assert "Thank you for watching" not in queue.items[4].message


def test_checkered_finish_rundown_waits_for_stable_order():
    director = RaceDirector()
    queue = BroadcastQueue()
    drivers = {
        0: {"name": "Winner", "number": "1"},
        1: {"name": "Second Early", "number": "2"},
        2: {"name": "Second Final", "number": "3"},
    }
    early_results = [
        {"CarIdx": 0, "Position": 0},
        {"CarIdx": 1, "Position": 1},
        {"CarIdx": 2, "Position": 2},
    ]
    final_results = [
        {"CarIdx": 0, "Position": 0},
        {"CarIdx": 2, "Position": 1},
        {"CarIdx": 1, "Position": 2},
    ]

    director.handle_checkered(
        early_results,
        drivers,
        queue,
        {"track_name": "Homestead Miami Speedway"},
    )
    for _ in range(8):
        director.handle_post_race_results(
            early_results,
            drivers,
            queue,
            {"track_name": "Homestead Miami Speedway"},
        )
    for _ in range(8):
        director.handle_post_race_results(
            final_results,
            drivers,
            queue,
            {"track_name": "Homestead Miami Speedway"},
        )

    assert not any(item.category == "post_race" for item in queue.items)

    director.handle_post_race_results(
        final_results,
        drivers,
        queue,
        {"track_name": "Homestead Miami Speedway"},
    )

    rundown = next(item for item in queue.items if item.category == "post_race")
    assert "second, the 3 of Second Final" in rundown.message
    assert "third, the 2 of Second Early" in rundown.message


def test_checkered_finish_rundown_waits_until_leader_crosses_finish():
    director = RaceDirector()
    queue = BroadcastQueue()
    drivers = {
        0: {"name": "Winner", "number": "1"},
        1: {"name": "Second", "number": "2"},
    }
    approaching_line = [
        {"CarIdx": 0, "Position": 0, "LapsComplete": 49},
        {"CarIdx": 1, "Position": 1, "LapsComplete": 49},
    ]
    finished = [
        {"CarIdx": 0, "Position": 0, "LapsComplete": 50},
        {"CarIdx": 1, "Position": 1, "LapsComplete": 50},
    ]

    director.handle_checkered(
        approaching_line,
        drivers,
        queue,
        {"track_name": "Homestead Miami Speedway"},
    )
    assert "wins" not in queue.items[0].message

    for _ in range(10):
        director.handle_post_race_results(
            approaching_line,
            drivers,
            queue,
            {"track_name": "Homestead Miami Speedway"},
            current_lap=49,
            total_laps=50,
        )

    assert not any(item.category == "post_race" for item in queue.items)

    for _ in range(20):
        director.handle_post_race_results(
            finished,
            drivers,
            queue,
            {"track_name": "Homestead Miami Speedway"},
            current_lap=50,
            total_laps=50,
        )

    rundown = next(item for item in queue.items if item.category == "post_race")
    assert "first, the 1 of Winner" in rundown.message


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
