from production.track_style import is_road_course, racecraft_profile


def test_detects_road_course_from_category():
    track_info = {
        "track_name": "Canadian Tire Motorsport Park",
        "category": "Road",
    }

    assert is_road_course(track_info) is True
    assert racecraft_profile(track_info)["style"] == "road_course"


def test_detects_road_course_from_name_without_category():
    track_info = {"track_name": "Watkins Glen International"}

    assert is_road_course(track_info) is True


def test_standard_oval_is_not_road_course():
    track_info = {
        "track_name": "Michigan International Speedway",
        "track_type": "oval",
        "category": "Oval",
    }

    assert is_road_course(track_info) is False
    assert racecraft_profile(track_info)["style"] == "standard_oval"
