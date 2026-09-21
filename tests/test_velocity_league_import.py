from tools.velocity_league_import import (
    driver_rows_from_stats,
    fetch_first_html,
    merge_driver_sources,
    parse_structured_career,
    parse_structured_directory,
    parse_structured_standings,
    preserve_existing_driver_details,
    parse_schedule_rows,
    parse_standings_rows,
    url_variants,
)


def rsc_page(*objects):
    import json

    payload = "".join(json.dumps(item, separators=(",", ":")) for item in objects)
    return f'<script>self.__next_f.push([1,"{payload.replace(chr(34), chr(92) + chr(34))}"])</script>'


def test_structured_velocity_pages_use_real_names_numbers_and_stats():
    standings = rsc_page(
        {
            "cust_id": 120815,
            "display_name": "Richard Holland2",
            "car_number": "31",
            "total_points": 38,
            "wins": 0,
            "top5": 1,
            "top10": 1,
            "poles": 0,
            "races": 1,
            "raceEntries": [{"finish_pos": 5}],
        }
    )
    careers = rsc_page(
        {
            "cust_id": 120815,
            "name": "Richard Holland",
            "car_number": "31",
            "active_car_number": "31",
            "starts": 2,
            "wins": 0,
            "top5": 2,
            "top10": 2,
            "avg_finish": 3.5,
            "poles": 0,
        }
    )

    season_rows = parse_structured_standings(standings)
    career_rows = parse_structured_career(careers)
    from tools.velocity_league_import import apply_canonical_driver_names

    apply_canonical_driver_names(season_rows, career_rows)

    assert season_rows[0]["name"] == "Richard Holland"
    assert season_rows[0]["car_number"] == "31"
    assert season_rows[0]["last_finish"] == 5
    assert career_rows[0]["starts"] == 2
    assert career_rows[0]["avg_finish"] == 3.5


def test_directory_adds_signed_drivers_and_career_name_wins():
    directory = rsc_page(
        {
            "cust_id": "120815",
            "name": "Richard Holland2",
            "series_key": "tuesday-night-trucks",
            "starts": 1,
            "first_raced": "2026-09-16 00:00:34+00",
            "last_car_number": "31",
            "country_code": None,
        },
        {
            "cust_id": "999",
            "name": "Signed Driver",
            "series_key": "tuesday-night-trucks",
            "starts": 0,
            "last_car_number": "44",
        },
    )
    directory_rows = parse_structured_directory(directory, "tuesday-night-trucks")
    career_rows = [
        {"_cust_id": "120815", "name": "Richard Holland", "car_number": "31"}
    ]

    drivers = merge_driver_sources(directory_rows, [], career_rows)

    assert [(row["name"], row["car_number"]) for row in drivers] == [
        ("Richard Holland", "31"),
        ("Signed Driver", "44"),
    ]


def test_velocity_driver_import_preserves_manual_profile_details(tmp_path):
    path = tmp_path / "drivers.csv"
    path.write_text(
        "name,car_number,hometown,state,country,driving_style,sponsor,about,car_image\n"
        "Richard Holland,P3,Richmond,VA,United States,,RGC,Manual story,car.png\n",
        encoding="utf-8",
    )

    rows = preserve_existing_driver_details(
        path,
        [{"name": "Richard Holland", "car_number": "31", "hometown": "", "state": "", "country": "", "driving_style": "", "sponsor": "", "about": "", "car_image": ""}],
    )

    assert rows[0]["car_number"] == "31"
    assert rows[0]["hometown"] == "Richmond"
    assert rows[0]["about"] == "Manual story"


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
