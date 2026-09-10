from tools.velocity_league_import import (
    driver_rows_from_stats,
    fetch_first_html,
    parse_schedule_rows,
    parse_standings_rows,
    url_variants,
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
            "schedule_id": "velocity-rd-1-truck-series",
            "notes": "TUE MAY 5 - Truck Series - 83 laps",
        },
        {
            "track_name": "Richmond Raceway",
            "schedule_id": "velocity-rd-19-truck-series",
            "notes": "TUE SEP 15 - Truck Series - 160 Laps",
        },
    ]


def test_parse_velocity_schedule_rows_can_filter_by_series():
    text = """
    RD 1
    TUE SEP 15
    8:00 PM ET
    Taco Tuesday Truck Series
    Daytona
    80 Laps
    RD 1
    WED SEP 16
    8:00 PM ET
    Whiskey Throttle Wednesday
    Daytona
    85 Laps
    """

    rows = parse_schedule_rows(text, series_filter="Whiskey Throttle Wednesday")

    assert rows == [
        {
            "track_name": "Daytona",
            "schedule_id": "velocity-rd-1-whiskey-throttle-wednesday",
            "notes": "WED SEP 16 - Whiskey Throttle Wednesday - 85 Laps",
        }
    ]


def test_velocity_url_variants_try_league_subdomain_first():
    variants = url_variants("https://www.velocityleague.gg/trrl")

    assert variants[0] == "https://trrl.velocityleague.gg/"
    assert "https://www.velocityleague.gg/trrl" in variants
    assert "https://www.velocityleague.gg/trrl/" in variants


def test_fetch_first_html_retries_after_redirect_loop(monkeypatch):
    import tools.velocity_league_import as velocity_import

    attempts = []

    def fake_fetch_html(url, timeout=20):
        attempts.append(url)
        if "bad" in url:
            raise RuntimeError("Redirect loop while fetching bad")
        return "<html>Drivers</html>"

    monkeypatch.setattr(velocity_import, "fetch_html", fake_fetch_html)

    url, document = fetch_first_html(["https://bad.velocityleague.gg/", "https://good.velocityleague.gg/"])

    assert url == "https://good.velocityleague.gg/"
    assert document == "<html>Drivers</html>"
    assert attempts == ["https://bad.velocityleague.gg/", "https://good.velocityleague.gg/"]
