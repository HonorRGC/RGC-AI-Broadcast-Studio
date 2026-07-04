from production.field_rundown_director import FieldRundownDirector


def test_quarter_rundown_freezes_and_segments_the_full_field():
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
    repeated = director.update(
        results=results,
        driver_lookup=drivers,
        current_lap=11,
        total_laps=40,
        under_green=True,
    )

    assert len(segments) == 2
    assert segments[0].category == "quarter_field_rundown_1"
    assert segments[0].speaker == "jeff"
    assert segments[0].camera_sequence == (0, 3, 2, 1, 4, 5, 6, 7)
    assert segments[0].camera_sequence_steps[:4] == (
        (0, "TV1", 0),
        (0, "Cockpit", 0),
        (3, "TV1", 0),
        (3, "Cockpit", 0),
    )
    assert segments[1].camera_sequence == (8, 9)
    assert "At quarter distance" in segments[0].message
    assert "qualifying-order reset" in segments[0].message
    assert "Driver 2 is now running second, after starting fifth, up 3 spots" in segments[0].message
    assert "Driver 4 is now running fourth, after starting second, down 2 spots" in segments[0].message
    assert "Driver 10" in segments[1].message
    assert "completes the full-field reset" in segments[1].message
    assert repeated == []


def test_quarter_rundown_waits_for_green_and_quarter_distance():
    director = FieldRundownDirector()
    results = [{"CarIdx": 1, "Position": 1}]

    assert director.update(results, {}, 9, 40, under_green=True) == []
    assert director.update(results, {}, 10, 40, under_green=False) == []
