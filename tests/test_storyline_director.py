from types import SimpleNamespace

from production.driver_memory import DriverMemoryRecord
from production.storyline_director import StorylineDirector


class Memory:
    def __init__(self, records):
        self.records = {record.car_idx: record for record in records}


def race_state(is_green=True):
    return SimpleNamespace(is_green=is_green)


def test_storyline_detects_race_recovery():
    director = StorylineDirector()
    record = DriverMemoryRecord(
        car_idx=7,
        driver_name="Recovery Driver",
        car_number="7",
        current_position=8,
        best_position=6,
        worst_position=18,
        laps_recorded=12,
    )

    events = director.analyze(Memory([record]), race_state(), current_lap=22)

    assert events[0].story_type == "race_recovery"
    assert "back in eighteenth" in events[0].summary
    assert "recovered to eighth" in events[0].summary
    assert events[0].camera_target_car_idx == 7


def test_storyline_detects_driver_fading_from_top_six():
    director = StorylineDirector()
    record = DriverMemoryRecord(
        car_idx=24,
        driver_name="Fading Driver",
        car_number="24",
        current_position=12,
        best_position=4,
        worst_position=12,
        laps_recorded=15,
    )

    events = director.analyze(Memory([record]), race_state(), current_lap=24)

    assert events[0].story_type == "race_fade"
    assert "as high as fourth" in events[0].summary
    assert "now shown twelfth" in events[0].summary


def test_storyline_detects_pit_cycle_memory():
    director = StorylineDirector()
    record = DriverMemoryRecord(
        car_idx=11,
        driver_name="Pit Cycle Driver",
        car_number="11",
        current_position=9,
        best_position=5,
        worst_position=15,
        laps_recorded=20,
        pit_stops=1,
        last_pit_lap=16,
    )

    events = director.analyze(Memory([record]), race_state(), current_lap=22)

    assert any(event.story_type == "pit_cycle_memory" for event in events)
    event = next(event for event in events if event.story_type == "pit_cycle_memory")
    assert "last came to pit road around lap 16" in event.summary
    assert event.speaker == "sarah"


def test_storyline_does_not_air_under_caution():
    director = StorylineDirector()
    record = DriverMemoryRecord(
        car_idx=7,
        driver_name="Recovery Driver",
        car_number="7",
        current_position=8,
        best_position=6,
        worst_position=18,
        laps_recorded=12,
    )

    events = director.analyze(Memory([record]), race_state(is_green=False), current_lap=22)

    assert events == []
