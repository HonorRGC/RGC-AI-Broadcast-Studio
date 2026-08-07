from types import SimpleNamespace

from production.booth_conversation_director import BoothConversationDirector


def race_state(green_lap_count=16, laps_remaining=40):
    return SimpleNamespace(
        green_lap_count=green_lap_count,
        laps_remaining=laps_remaining,
    )


def test_builds_long_green_booth_conversation_for_draft_track():
    director = BoothConversationDirector()
    results = [
        {"CarIdx": index, "Position": index + 1, "Time": 0.4 + index * 0.05}
        for index in range(8)
    ]
    drivers = {
        index: {"name": f"Driver {index}", "number": str(index)}
        for index in range(8)
    }

    lines = director.build(
        results=results,
        driver_lookup=drivers,
        track_info={"track_name": "Daytona International Speedway"},
        race_state=race_state(green_lap_count=18, laps_remaining=35),
        current_lap=18,
        total_laps=60,
    )

    assert len(lines) == 3
    assert [line.speaker for line in lines] == ["lead", "jeff", "sarah"]
    assert "draft" in lines[0].message.lower()
    assert lines[1].delay_seconds == 0.05
    assert lines[2].delay_seconds == 0.10
    assert lines[0].camera_target_car_idx == 1
    assert lines[0].participant_car_indices == (0, 1)


def test_skips_booth_conversation_near_finish():
    director = BoothConversationDirector()
    results = [
        {"CarIdx": index, "Position": index + 1, "Time": 0.5}
        for index in range(8)
    ]

    lines = director.build(
        results=results,
        driver_lookup={},
        track_info={"track_name": "Charlotte Motor Speedway"},
        race_state=race_state(green_lap_count=20, laps_remaining=8),
        current_lap=92,
        total_laps=100,
    )

    assert lines == []


def test_booth_conversation_uses_track_specific_tire_topic():
    director = BoothConversationDirector()
    results = [
        {"CarIdx": index, "Position": index + 1, "Time": 2.0}
        for index in range(8)
    ]

    lines = director.build(
        results=results,
        driver_lookup={},
        track_info={"track_name": "Homestead-Miami Speedway"},
        race_state=race_state(green_lap_count=16, laps_remaining=45),
        current_lap=22,
        total_laps=80,
    )

    assert len(lines) == 3
    assert "tire-management" in lines[0].message
    combined = " ".join(line.message.lower() for line in lines)
    assert "patience pays off" not in combined
    assert "throttle discipline" in combined


def test_superspeedway_name_alone_does_not_force_draft_topic():
    director = BoothConversationDirector()
    results = [
        {"CarIdx": index, "Position": index + 1, "Time": 2.0}
        for index in range(8)
    ]

    lines = director.build(
        results=results,
        driver_lookup={},
        track_info={"track_name": "Nashville Superspeedway"},
        race_state=race_state(green_lap_count=16, laps_remaining=45),
        current_lap=22,
        total_laps=80,
    )

    assert len(lines) == 3
    assert "draft" not in " ".join(line.message.lower() for line in lines)
    assert "tire-management" in lines[0].message


def test_short_track_conversation_avoids_generic_patience_line():
    director = BoothConversationDirector()
    results = [
        {"CarIdx": index, "Position": index + 1, "Time": 0.7}
        for index in range(8)
    ]

    lines = director.build(
        results=results,
        driver_lookup={},
        track_info={"track_name": "Martinsville Speedway"},
        race_state=race_state(green_lap_count=16, laps_remaining=45),
        current_lap=25,
        total_laps=100,
    )

    combined = " ".join(line.message.lower() for line in lines)
    assert "patience can be just as valuable" not in combined
    assert "the smart move is not always the first move" in combined
