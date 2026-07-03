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
    assert "a gain of one position" in story
    assert "Started 4" not in story
    assert "1 positions" not in story
