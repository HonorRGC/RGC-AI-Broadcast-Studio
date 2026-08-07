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
        "opening_pit_report",
    ]
    track_message = first_segments[0].message
    assert "momentum race" in track_message
    assert "I'm Mike" in track_message
    assert "partly cloudy" in track_message.lower()
    assert "mile-and-a-third oval" in track_message
    assert "81 degrees Fahrenheit" in track_message
    assert "rain chance is 0 percent" in track_message
    assert "dynamic" not in track_message.lower()
    assert "hotter track should make the tires give up faster" in track_message
    assert first_segments[1].speaker == "sarah"
    assert "I'm Sarah" in first_segments[1].message
    assert "pit road" in first_segments[1].message.lower()
    assert director.is_complete() is False

    results, drivers = build_lineup()
    assert director.update(TrackTelemetry(), results, drivers) == []
    assert director.update(TrackTelemetry(), results, drivers) == []
    assert director.update(TrackTelemetry(), results, drivers) == []
    assert director.update(TrackTelemetry(), results, drivers) == []
    lineup_segments = director.update(TrackTelemetry(), results, drivers)

    assert len(lineup_segments) == 13
    assert lineup_segments[0].category == "opening_field_rundown_1"
    assert lineup_segments[-1].category == "opening_hype"
    assert "I'm Jeff" in lineup_segments[0].message
    assert "Pole: the 1 of Driver 1" in lineup_segments[0].message
    assert "12th: the 12 of Driver 12" in lineup_segments[-2].message
    assert lineup_segments[0].camera_sequence == (0,)
    assert lineup_segments[0].camera_sequence_steps == ((0, "Rear Chase", 0),)
    assert lineup_segments[0].camera_return_home_after_sequence is False
    assert lineup_segments[-2].camera_return_home_after_sequence is True
    assert lineup_segments[0].speaker == "jeff"
    assert lineup_segments[-1].speaker == "lead"
    assert lineup_segments[-1].delay_seconds == 4.0
    assert "Let's settle in and go racing" in lineup_segments[-1].message
    assert "pace car is about to pull in" in lineup_segments[-1].message
    assert "boys and girls" not in lineup_segments[-1].message
    assert (
        "That is your 12-car field for 80 laps at Nashville Superspeedway"
        in lineup_segments[-2].message
    )
    assert director.is_complete() is True


def test_lineup_supports_one_based_positions():
    director = OpeningDirector()
    results, drivers = build_lineup(count=5, zero_based=False)

    director.update(TrackTelemetry(), results, drivers)
    director.update(TrackTelemetry(), results, drivers)
    director.update(TrackTelemetry(), results, drivers)
    director.update(TrackTelemetry(), results, drivers)
    segments = director.update(TrackTelemetry(), results, drivers)

    lineup = [
        segment for segment in segments if "rundown" in segment.category
    ]
    assert "Pole: the 1 of Driver 1" in lineup[0].message
    assert "5th: the 5 of Driver 5" in lineup[-1].message


def test_lineup_alternates_booth_by_ten_driver_blocks():
    director = OpeningDirector()
    results, drivers = build_lineup(count=45)

    segments = director.build_field_rundown(results, drivers)

    assert len(segments) == 45
    assert {segment.speaker for segment in segments[:10]} == {"jeff"}
    assert {segment.speaker for segment in segments[10:20]} == {"lead"}
    assert {segment.speaker for segment in segments[20:30]} == {"jeff"}
    assert {segment.speaker for segment in segments[30:40]} == {"lead"}
    assert {segment.speaker for segment in segments[40:]} == {"jeff"}
    assert "Mike picks it up from here" in segments[10].message
    assert "Back to Jeff for the next group" in segments[20].message


def test_opening_uses_custom_broadcaster_names():
    director = OpeningDirector(
        lead_name="Lee",
        color_name="James",
        pit_name="Amanda",
    )

    first_segments = director.update(TrackTelemetry(), [], {})

    assert "I'm Lee" in first_segments[0].message
    assert "I'm Amanda" in first_segments[1].message

    results, drivers = build_lineup(count=22)
    segments = director.build_field_rundown(results, drivers)

    assert "I'm James" in segments[0].message
    assert "Lee picks it up from here" in segments[10].message
    assert "Back to James for the next group" in segments[20].message


def test_opening_hype_follows_the_lineup():
    director = OpeningDirector()

    segment = director.build_hype()

    assert segment.category == "opening_hype"
    assert segment.speaker == "lead"
    assert segment.delay_seconds == 4.0
    assert "The field is set" in segment.message
    assert "pace car is about to pull in" in segment.message
    assert "Let's settle in and go racing" in segment.message


def test_track_info_explains_hot_daytime_track_grip():
    director = OpeningDirector()
    segment = director.build_track_info(
        {
            "track_name": "Homestead Miami Speedway",
            "track_length": "1.5 mi",
            "track_type": "oval",
            "skies": "clear",
            "air_temp": 31.0,
            "track_temp": 43.5,
            "humidity": 0.40,
            "wind_speed": 2.0,
            "track_wetness": 0,
            "rain_chance": 0,
            "time_of_day": "afternoon",
        }
    )

    assert "rain chance is 0 percent" in segment.message
    assert "mile-and-a-half oval" in segment.message
    assert "hotter track should make the tires give up faster" in segment.message
    assert "drivers who manage throttle and corner entry" in segment.message
    assert "racing surface is dry" not in segment.message.lower()


def test_opening_expands_state_abbreviations_in_track_location():
    director = OpeningDirector()
    segment = director.build_welcome(
        {
            "track_name": "Talladega Superspeedway",
            "track_city": "Lincoln",
            "track_state": "AL",
            "track_length": "2.66 mi",
            "track_type": "oval",
            "skies": "clear",
            "air_temp": 27.0,
            "track_temp": 33.0,
            "track_wetness": 0,
            "rain_chance": 0,
        }
    )

    assert "Lincoln, Alabama" in segment.message
    assert "Lincoln, AL" not in segment.message


def test_track_info_explains_cool_night_race_grip():
    director = OpeningDirector()
    segment = director.build_track_info(
        {
            "track_name": "Nashville Superspeedway",
            "track_length": "2.14 km",
            "track_type": "oval",
            "skies": "clear",
            "air_temp": 18.0,
            "track_temp": 24.0,
            "track_wetness": 0,
            "rain_chance": 0.0,
            "time_of_day": "night",
        }
    )

    assert "cooler racing surface" in segment.message
    assert "more grip" in segment.message
    assert "racing surface is dry" not in segment.message.lower()


def test_road_course_track_info_can_include_surface_wetness():
    director = OpeningDirector()
    segment = director.build_track_info(
        {
            "track_name": "Road America",
            "track_length": "4.048 mi",
            "track_type": "road course",
            "category": "Road",
            "skies": "overcast",
            "air_temp": 19.0,
            "track_temp": 21.0,
            "track_wetness": 2,
        }
    )

    assert "racing surface is very lightly wet" in segment.message.lower()


def test_league_opening_outlook_uses_championship_and_track_history():
    director = OpeningDirector()
    segment = director.build_race_outlook(
        {"track_name": "Michigan International Speedway", "track_type": "oval"},
        {
            34: {
                "name": "T.J. Lee",
                "number": "34",
                "league_stats_by_scope": [
                    {
                        "stats_scope": "season",
                        "points_position": "2",
                        "points_to_next": "8",
                        "track_wins": "0",
                    }
                ],
            },
            24: {
                "name": "Dean Marsh",
                "number": "24",
                "league_stats_by_scope": [
                    {
                        "stats_scope": "season",
                        "points_position": "5",
                        "track_wins": "1",
                    }
                ],
            },
        },
    )

    assert segment.speaker == "jeff"
    assert "championship" in segment.message
    assert "8 points from the next spot" in segment.message
    assert "has won here before" in segment.message


def test_track_info_uses_supplied_rain_chance():
    director = OpeningDirector()
    segment = director.build_track_info(
        {
            "track_name": "Daytona International Speedway",
            "track_length": "2.5 mi",
            "track_type": "oval",
            "skies": "mostly cloudy",
            "air_temp": 27.0,
            "track_temp": 33.0,
            "track_wetness": 0,
            "rain_chance": 0.25,
        }
    )

    assert "rain chance is 25 percent" in segment.message
    assert "two-and-a-half-mile oval" in segment.message


def test_track_info_removes_simulator_weather_mode_wording():
    director = OpeningDirector()
    segment = director.build_track_info(
        {
            "track_name": "Daytona International Speedway",
            "track_length": "2.5 mi",
            "track_type": "oval",
            "skies": "dynamic partly cloudy",
            "air_temp": 27.0,
            "track_temp": 33.0,
            "track_wetness": 0,
            "rain_chance": 0,
        }
    )

    assert "dynamic" not in segment.message.lower()


def test_indianapolis_outlook_uses_long_straight_not_pack_draft_language():
    director = OpeningDirector()

    segment = director.build_race_outlook(
        {
            "track_name": "Indianapolis Motor Speedway",
            "track_type": "oval",
            "track_length": "2.5 mi",
        }
    )

    assert "long straightaways" in segment.message
    assert "draft should shape" not in segment.message.lower()
    assert "lane changes" not in segment.message.lower()


def test_road_course_opening_uses_road_racing_language():
    director = OpeningDirector()

    outlook = director.build_race_outlook(
        {
            "track_name": "Road America",
            "track_type": "road course",
            "category": "Road",
            "track_length": "4.048 mi",
        }
    )
    pit_report = director.build_pit_report(
        {
            "track_name": "Road America",
            "track_type": "road course",
            "category": "Road",
            "track_length": "4.048 mi",
        }
    )

    assert "braking zones" in outlook.message
    assert "undercut" in pit_report.message
    assert "overcut" in pit_report.message
