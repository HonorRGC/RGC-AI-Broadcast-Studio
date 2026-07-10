from production.field_rundown_director import FieldRundownDirector


def test_long_green_rundown_freezes_top_ten_and_airs_one_driver_at_a_time():
    director = FieldRundownDirector()
    results = [
        {"CarIdx": index, "Position": index, "StartingPosition": index + 1}
        for index in range(10)
    ]
    results[1]["StartingPosition"] = 5
    results[3]["StartingPosition"] = 2
    drivers = {
        index: {"name": f"Driver {index + 1}", "number": str(index + 1)}
        for index in range(10)
    }

    segments = director.update(
        results=results,
        driver_lookup=drivers,
        current_lap=20,
        total_laps=40,
        under_green=True,
        green_lap_count=20,
    )
    second_segment = director.update(
        results=results,
        driver_lookup=drivers,
        current_lap=21,
        total_laps=40,
        under_green=True,
        green_lap_count=21,
    )
    repeated = director.update(
        results=results,
        driver_lookup=drivers,
        current_lap=22,
        total_laps=40,
        under_green=True,
        green_lap_count=22,
    )

    assert len(segments) == 1
    assert len(second_segment) == 1
    assert segments[0].category == "long_green_field_rundown_1"
    assert segments[0].speaker == "jeff"
    assert segments[0].camera_sequence == (0,)
    assert segments[0].camera_sequence_steps == (
        (0, "TV1", 0),
        (0, "Cockpit", 0),
    )
    assert segments[0].feature_duration_seconds == 20.0
    assert second_segment[0].camera_sequence == (1,)
    assert "20-lap green flag run" in segments[0].message
    assert "top ten" in segments[0].message
    assert "First place" in segments[0].message
    assert "Driver 2" in second_segment[0].message
    assert repeated[0].category == "long_green_field_rundown_3"


def test_long_green_rundown_waits_for_twenty_green_laps():
    director = FieldRundownDirector()
    results = [{"CarIdx": 1, "Position": 1}]

    assert director.update(results, {}, 20, 40, under_green=True, green_lap_count=19) == []
    assert director.update(results, {}, 20, 40, under_green=False, green_lap_count=20) == []


def test_long_green_rundown_runs_only_once():
    director = FieldRundownDirector()
    results = [
        {"CarIdx": index, "Position": index, "StartingPosition": index + 1}
        for index in range(10)
    ]
    drivers = {
        index: {"name": f"Driver {index + 1}", "number": str(index + 1)}
        for index in range(10)
    }

    for lap in range(20, 30):
        director.update(
            results,
            drivers,
            lap,
            40,
            under_green=True,
            green_lap_count=lap,
        )
    segments = director.update(
        results,
        drivers,
        30,
        40,
        under_green=True,
        green_lap_count=30,
    )

    assert segments == []


def test_long_green_rundown_refreshes_live_order_during_passes():
    director = FieldRundownDirector()
    results = [
        {"CarIdx": index, "Position": index, "StartingPosition": index + 1}
        for index in range(10)
    ]
    drivers = {
        index: {"name": f"Driver {index + 1}", "number": str(index + 1)}
        for index in range(10)
    }

    for lap in range(20, 24):
        director.update(
            results,
            drivers,
            lap,
            60,
            under_green=True,
            green_lap_count=lap,
        )

    changed = [dict(car) for car in results]
    changed[4]["Position"] = 5
    changed[5]["Position"] = 4
    fifth_call = director.update(
        changed,
        drivers,
        24,
        60,
        under_green=True,
        green_lap_count=24,
    )

    assert fifth_call[0].category == "long_green_field_rundown_5"
    assert fifth_call[0].camera_sequence == (5,)
    assert "fifth" in fifth_call[0].message.lower()
    assert "Driver 6" in fifth_call[0].message


def test_active_long_green_rundown_cancels_under_caution():
    director = FieldRundownDirector()
    results = [
        {"CarIdx": index, "Position": index, "StartingPosition": index + 1}
        for index in range(10)
    ]
    drivers = {
        index: {"name": f"Driver {index + 1}", "number": str(index + 1)}
        for index in range(10)
    }

    first = director.update(results, drivers, 20, 40, True, green_lap_count=20)
    caution = director.update(results, drivers, 21, 40, False, green_lap_count=0)
    resumed = director.update(results, drivers, 35, 40, True, green_lap_count=30)

    assert first[0].category == "long_green_field_rundown_1"
    assert caution == []
    assert resumed == []
