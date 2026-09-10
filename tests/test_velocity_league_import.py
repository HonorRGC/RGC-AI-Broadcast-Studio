from tools.velocity_league_import import (
    driver_rows_from_stats,
    parse_schedule_rows,
    parse_standings_rows,
)


def test_parse_velocity_standings_rows_from_public_page_text():
    text = """
    Truck Series
    P1
    Jordan Traas
    #79
    584
    Leader
    5 wins
    View Profile
    P2
    Riley Martin
    #12
    544
    -40 gap
    2 wins
    View Profile
    """

    rows = parse_standings_rows(text, series_filter="Truck Series")

    assert rows[0]["name"] == "Jordan Traas"
    assert rows[0]["car_number"] == "79"
    assert rows[0]["points_position"] == "1"
    assert rows[0]["wins"] == "5"
    assert "584 points" in rows[0]["notes"]
    assert rows[1]["name"] == "Riley Martin"
    assert rows[1]["points_to_next"] == "40"


def test_velocity_stats_rows_can_seed_driver_csv_rows():
    stats_rows = [
        {"name": "Jordan Traas", "car_number": "79"},
        {"name": "Jordan Traas", "car_number": "79"},
        {"name": "Riley Martin", "car_number": "12"},
    ]

    rows = driver_rows_from_stats(stats_rows)

    assert rows == [
        {
            "name": "Jordan Traas",
            "car_number": "79",
            "hometown": "",
            "state": "",
            "country": "",
            "driving_style": "",
            "sponsor": "",
            "about": "",
            "car_image": "",
        },
        {
            "name": "Riley Martin",
            "car_number": "12",
            "hometown": "",
            "state": "",
            "country": "",
            "driving_style": "",
            "sponsor": "",
            "about": "",
            "car_image": "",
        },
    ]


def test_parse_velocity_schedule_rows_from_public_page_text():
    text = """
    RD 1
    TUE MAY 5
    8:30 PM ET
    Truck Series
    Daytona International Speedway
    83 laps
    17 lead chg
    9 cautions
    Winner
    Jordan Traas
    RD 19
    TUE SEP 15
    Truck Series
    Richmond Raceway
    160 Laps
    """

    rows = parse_schedule_rows(text)

    assert rows == [
        {
            "track_name": "Daytona International Speedway",
            "schedule_id": "velocity-rd-1",
            "notes": "TUE MAY 5",
        },
        {
            "track_name": "Richmond Raceway",
            "schedule_id": "velocity-rd-19",
            "notes": "TUE SEP 15",
        },
    ]
