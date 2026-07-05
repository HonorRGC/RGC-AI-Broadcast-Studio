from production.field_rundown_director import FieldRundownDirector


def test_quarter_rundown_freezes_top_ten_and_airs_one_driver_at_a_time():
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
        current_lap=10,
        total_laps=40,
        under_green=True,
    )
    second_segment = director.update(
        results=results,
        driver_lookup=drivers,
        current_lap=11,
        total_laps=40,
        under_green=True,
    )
    repeated = director.update(
        results=results,
        driver_lookup=drivers,
        current_lap=12,
        total_laps=40,
        under_green=True,
    )

    assert len(segments) == 1
    assert len(second_segment) == 1
    assert segments[0].category == "quarter_field_rundown_1"
    assert segments[0].speaker == "jeff"
    assert segments[0].camera_sequence == (0,)
    assert segments[0].camera_sequence_steps == (
        (0, "TV1", 0),
        (0, "Cockpit", 0),
    )
    assert second_segment[0].camera_sequence == (1,)
    assert "one quarter into this race" in segments[0].message
    assert "top ten" in segments[0].message
    assert "Running first" in segments[0].message
    assert "Driver 2" in second_segment[0].message
    assert repeated[0].category == "quarter_field_rundown_3"


def test_quarter_rundown_waits_for_green_and_quarter_distance():
    director = FieldRundownDirector()
    results = [{"CarIdx": 1, "Position": 1}]

    assert director.update(results, {}, 9, 40, under_green=True) == []
    assert director.update(results, {}, 10, 40, under_green=False) == []


def test_three_quarter_rundown_runs_after_quarter_rundown():
    director = FieldRundownDirector()
    results = [
        {"CarIdx": index, "Position": index, "StartingPosition": index + 1}
        for index in range(10)
    ]
    drivers = {
        index: {"name": f"Driver {index + 1}", "number": str(index + 1)}
        for index in range(10)
    }

    for lap in range(10, 20):
        director.update(results, drivers, lap, 40, under_green=True)
    segments = director.update(results, drivers, 30, 40, under_green=True)

    assert len(segments) == 1
    assert segments[0].category == "three_quarter_field_rundown_1"
    assert "three quarters into this race" in segments[0].message
