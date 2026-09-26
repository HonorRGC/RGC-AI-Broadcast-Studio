from tools.velocity_league_import import (
    aggregate_series_career,
    build_standings_query,
    driver_rows_from_stats,
    extract_series_season_keys,
    extract_recap_urls,
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


def test_extracts_selected_series_velocity_recap_links():
    page = (
        '<a href="/trrl/recap/88863839?series=whiskey-throttle-wednesday">Recap</a>'
        '<a href="/trrl/recap/777?series=tuesday-night-trucks">Other</a>'
    )

    urls = extract_recap_urls(
        page,
        "https://www.velocityleague.gg",
        "whiskey-throttle-wednesday",
    )

    assert urls == [
        "https://www.velocityleague.gg/trrl/recap/88863839?series=whiskey-throttle-wednesday"
    ]


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


def test_structured_standings_uses_selected_series_table_rendered_last():
    page = rsc_page(
        {
            "cust_id": 100,
            "display_name": "Other Series Leader",
            "car_number": "1",
            "total_points": 90,
            "races": 2,
        },
        {
            "cust_id": 200,
            "display_name": "Shared Driver",
            "car_number": "2",
            "total_points": 80,
            "races": 2,
        },
        {
            "cust_id": 200,
            "display_name": "Wednesday Leader",
            "car_number": "81",
            "total_points": 87,
            "races": 2,
        },
        {
            "cust_id": 300,
            "display_name": "Wednesday Second",
            "car_number": "34",
            "total_points": 80,
            "races": 2,
        },
    )

    rows = parse_structured_standings(page)

    assert [(row["points_position"], row["name"], row["car_number"]) for row in rows] == [
        ("1", "Wednesday Leader", "81"),
        ("2", "Wednesday Second", "34"),
    ]


def test_velocity_series_career_aggregates_only_selected_series_seasons():
    season_one = [
        {
            "_cust_id": "100",
            "name": "Wednesday Driver",
            "car_number": "81",
            "starts": "2",
            "wins": "1",
            "top_fives": "2",
            "top_tens": "2",
            "poles": "0",
            "avg_finish": "2.5",
            "last_finish": "1",
            "best_track_finish": "1",
        }
    ]
    season_two = [
        {
            "_cust_id": "100",
            "name": "Wednesday Driver",
            "car_number": "81",
            "starts": "3",
            "wins": "2",
            "top_fives": "3",
            "top_tens": "3",
            "poles": "1",
            "avg_finish": "3.0",
            "last_finish": "2",
            "best_track_finish": "1",
        }
    ]

    career = aggregate_series_career([season_one, season_two])[0]

    assert career["stats_scope"] == "career"
    assert career["starts"] == 5
    assert career["wins"] == 3
    assert career["top_fives"] == 5
    assert career["top_tens"] == 5
    assert career["poles"] == 1
    assert career["avg_finish"] == "2.8"
    assert career["last_finish"] == "2"
    assert "2 seasons" in career["notes"]


def test_velocity_extracts_selected_series_season_keys():
    document = rsc_page(
        {
            "seasons": [
                {"season_key": "s1", "name": "Season 1"},
                {"season_key": "s2", "name": "Season 2"},
            ]
        }
    )

    assert extract_series_season_keys(document) == ["s1", "s2"]


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


def test_velocity_standings_query_uses_active_series_without_forcing_s1():
    query = build_standings_query(
        "whiskey-throttle-wednesday",
        "https://www.velocityleague.gg/trrl/standings?series=whiskey-throttle-wednesday",
    )

    assert query == "series=whiskey-throttle-wednesday"


def test_velocity_standings_query_preserves_explicit_season():
    query = build_standings_query(
        "whiskey-throttle-wednesday",
        "https://www.velocityleague.gg/trrl/standings?series=whiskey-throttle-wednesday&season=s2",
    )

    assert query == "series=whiskey-throttle-wednesday&season=s2"


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
