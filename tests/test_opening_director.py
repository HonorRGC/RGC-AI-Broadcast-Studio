from production.opening_director import OpeningDirector


class TrackTelemetry:
    def get_total_laps(self):
        return 80

    def get_track_info(self):
        return {
            "track_name": "Nashville Superspeedway",
            "track_city": "Lebanon",
            "track_state": "TN",
            "track_length": "2.14 km",
            "track_type": "oval",
            "skies": 1,
            "air_temp": 27.0,
            "track_temp": 42.0,
            "humidity": 0.55,
            "wind_speed": 4.0,
            "track_wetness": 0,
        }


def build_lineup(count=12, zero_based=True):
    offset = 0 if zero_based else 1
    results = [
        {"CarIdx": index, "Position": index + offset}
        for index in range(count)
    ]
    drivers = {
        index: {"name": f"Driver {index + 1}", "number": str(index + 1)}
        for index in range(count)
    }
    return results, drivers


def test_opening_waits_for_lineup_after_welcome_and_weather():
    director = OpeningDirector()

    first_segments = director.update(TrackTelemetry(), [], {})

    assert [segment.category for segment in first_segments] == [
        "opening_welcome",
        "opening_track_info",
    ]
    assert "partly cloudy" in first_segments[1].message.lower()
    assert "81 degrees Fahrenheit" in first_segments[1].message
    assert director.is_complete() is False

    results, drivers = build_lineup()
    lineup_segments = director.update(TrackTelemetry(), results, drivers)

    assert len(lineup_segments) == 2
    assert lineup_segments[0].category == "opening_field_rundown_1"
    assert lineup_segments[1].category == "opening_field_rundown_2"
    assert "On the pole, the 1 of Driver 1" in lineup_segments[0].message
    assert "Starting 12th, the 12 of Driver 12" in lineup_segments[1].message
    assert lineup_segments[0].camera_sequence == tuple(range(10))
    assert lineup_segments[1].camera_sequence == (10, 11)
    assert lineup_segments[0].speaker == "lead"
    assert lineup_segments[1].speaker == "jeff"
    assert (
        "That is your 12-car field for 80 laps at Nashville Superspeedway"
        in lineup_segments[1].message
    )
    assert director.is_complete() is True


def test_lineup_supports_one_based_positions():
    director = OpeningDirector()
    results, drivers = build_lineup(count=5, zero_based=False)

    segments = director.update(TrackTelemetry(), results, drivers)

    lineup = next(segment for segment in segments if "rundown" in segment.category)
    assert "On the pole, the 1 of Driver 1" in lineup.message
    assert "Starting 5th, the 5 of Driver 5" in lineup.message


def test_lineup_rotates_lead_jeff_lead_for_three_groups():
    director = OpeningDirector()
    results, drivers = build_lineup(count=25)

    segments = director.build_field_rundown(results, drivers)

    assert [segment.speaker for segment in segments] == ["lead", "jeff", "lead"]
