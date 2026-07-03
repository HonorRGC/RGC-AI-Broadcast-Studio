from broadcaster.race_brain import RaceBrain


def test_pass_story_uses_spoken_ordinals_and_singular_position():
    brain = RaceBrain()
    drivers = {
        0: {"name": "Leader", "number": "77"},
        1: {"name": "Eric Hudec", "number": "14"},
    }
    brain.analyze(
        [
            {"CarIdx": 0, "Position": 0, "LapsComplete": 1},
            {"CarIdx": 1, "Position": 3, "LapsComplete": 1},
        ],
        drivers,
    )

    events = brain.analyze(
        [
            {"CarIdx": 0, "Position": 0, "LapsComplete": 2},
            {"CarIdx": 1, "Position": 2, "LapsComplete": 2},
        ],
        drivers,
    )

    story = events[0].message
    assert "started fourth" in story
    assert "running third" in story
    assert "a net gain of one position" in story
    assert "Started 4" not in story
    assert "1 positions" not in story


def test_grid_seed_keeps_recovered_position_from_being_called_a_net_gain():
    brain = RaceBrain()
    drivers = {
        0: {"name": "Leader", "number": "77"},
        1: {"name": "Robert Nash", "number": "96"},
    }
    grid = [
        {"CarIdx": 0, "Position": 0},
        {"CarIdx": 1, "Position": 4},
    ]
    brain.seed_starting_positions(grid, drivers)
    brain.analyze(
        [
            {"CarIdx": 0, "Position": 0, "LapsComplete": 1},
            {"CarIdx": 1, "Position": 5, "LapsComplete": 1},
        ],
        drivers,
    )

    events = brain.analyze(
        [
            {"CarIdx": 0, "Position": 0, "LapsComplete": 2},
            {"CarIdx": 1, "Position": 4, "LapsComplete": 2},
        ],
        drivers,
    )

    assert "back in the position where it started" in events[0].message
    assert "gain of one" not in events[0].message
