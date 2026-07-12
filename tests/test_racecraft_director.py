from types import SimpleNamespace

from production.racecraft_director import RacecraftDirector


def race_state(green_lap_count=10, laps_remaining=40, is_green=True):
    return SimpleNamespace(
        green_lap_count=green_lap_count,
        laps_remaining=laps_remaining,
        is_green=is_green,
    )


def test_detects_driver_fighting_to_stay_on_lead_lap():
    director = RacecraftDirector()
    results = [
        {"CarIdx": 1, "Position": 1, "LapsComplete": 20},
        {"CarIdx": 8, "Position": 18, "LapsComplete": 20},
    ]
    drivers = {
        1: {"name": "Leader Driver", "number": "1"},
        8: {"name": "Lap Traffic", "number": "8"},
    }

    events = director.analyze(
        results=results,
        driver_lookup=drivers,
        current_lap=20,
        total_laps=50,
        lap_dist_pct_status=[0, 0.40, 0, 0, 0, 0, 0, 0, 0.46],
        race_state=race_state(),
    )

    assert events[0].story_type == "lead_lap_survival"
    assert "stay on the tail end of the lead lap" in events[0].summary
    assert events[0].camera_target_car_idx == 8
    assert events[0].participant_car_indices == (1, 8)


def test_detects_leader_closing_on_lap_traffic():
    director = RacecraftDirector()
    results = [
        {"CarIdx": 1, "Position": 1, "LapsComplete": 30},
        {"CarIdx": 22, "Position": 22, "LapsComplete": 29},
    ]
    drivers = {
        1: {"name": "Leader Driver", "number": "1"},
        22: {"name": "Lapped Car", "number": "22"},
    }

    events = director.analyze(
        results=results,
        driver_lookup=drivers,
        current_lap=30,
        total_laps=60,
        lap_dist_pct_status=[0, 0.72] + [0] * 20 + [0.77],
        race_state=race_state(),
    )

    assert events[0].story_type == "lap_traffic"
    assert "lap traffic" in events[0].summary


def test_detects_draft_track_fuel_save_context():
    director = RacecraftDirector()
    results = [
        {"CarIdx": index, "Position": index + 1, "LapsComplete": 18}
        for index in range(8)
    ]
    drivers = {
        index: {"name": f"Driver {index}", "number": str(index)}
        for index in range(8)
    }
    lap_pct = [0.500 + index * 0.005 for index in range(8)]

    events = director.analyze(
        results=results,
        driver_lookup=drivers,
        track_info={"track_name": "Daytona International Speedway"},
        race_state=race_state(green_lap_count=12, laps_remaining=38),
        current_lap=18,
        total_laps=60,
        lap_dist_pct_status=lap_pct,
    )

    assert any(event.story_type == "draft_fuel_save" for event in events)
    draft_event = next(event for event in events if event.story_type == "draft_fuel_save")
    assert "fuel-save draft run" in draft_event.summary


def test_detects_pit_window_on_draft_track():
    director = RacecraftDirector()

    events = director.analyze(
        results=[{"CarIdx": 1, "Position": 1, "LapsComplete": 25}],
        driver_lookup={1: {"name": "Leader Driver", "number": "1"}},
        track_info={"track_name": "Talladega Super Speedway"},
        race_state=race_state(green_lap_count=16, laps_remaining=35),
        current_lap=25,
        total_laps=60,
        lap_dist_pct_status=[0, 0.5],
    )

    pit_window = next(event for event in events if event.story_type == "pit_window")
    assert "shorter stop" in pit_window.summary
    assert pit_window.speaker == "sarah"


def test_detects_short_green_flag_pit_stop_strategy():
    director = RacecraftDirector()
    pit_state = SimpleNamespace(
        last_pit_exit_lap=31,
        last_pit_stop_seconds=6.5,
        last_pit_lane_seconds=39.0,
        last_pit_position_gain=3,
        driver_name="Short Stopper",
        car_number="44",
    )

    events = director.analyze(
        results=[{"CarIdx": 44, "Position": 8, "LapsComplete": 32}],
        driver_lookup={44: {"name": "Short Stopper", "number": "44"}},
        race_state=race_state(green_lap_count=20, laps_remaining=20),
        current_lap=32,
        total_laps=52,
        pit_states={44: pit_state},
    )

    assert events[0].story_type == "pit_strategy_context"
    assert "two tires, fuel only" in events[0].summary
    assert events[0].speaker == "sarah"
