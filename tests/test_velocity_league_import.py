import pytest

from tools.velocity_league_import import (
    aggregate_series_career,
    build_manager_results,
    build_standings_query,
    driver_rows_from_stats,
    extract_series_season_keys,
    extract_recap_urls,
    extract_result_urls,
    fetch_first_html,
    merge_driver_sources,
    manager_schedule_events,
    parse_structured_career,
    parse_structured_directory,
    parse_structured_standings,
    parse_recap_result,
    preserve_existing_driver_details,
    parse_schedule_rows,
    parse_standings_rows,
    url_variants,
)


def test_velocity_round_history_seeds_manager_results_and_future_schedule():
    records = [{
        "cust_id": 1, "display_name": "Test Driver", "car_number": "7",
        "raceEntries": [
            {"round": 1, "finish_pos": 2, "start_pos": 5, "inc": 1, "points": 35},
            {"round": 2, "finish_pos": 1, "start_pos": 2, "inc": 0, "points": 42},
        ],
    }]
    schedule = [
        {"track_name": "Daytona", "notes": "TUE SEP 15 - Test Series - 80 laps"},
        {"track_name": "Atlanta", "notes": "TUE SEP 22 - Test Series - 100 laps"},
        {"track_name": "Las Vegas", "notes": "TUE SEP 29 - Test Series - 120 laps"},
    ]

    results = build_manager_results(records, schedule)
    events = manager_schedule_events(schedule, {race.round_number for race in results})

    assert [race.round_number for race in results] == [1, 2]
    assert results[1].entries[0].points == 42
    assert [event.status for event in events] == ["Completed", "Completed", "Scheduled"]
    assert events[2].event_date == "09-29-2026"
    assert events[2].laps == 120


def test_velocity_recap_supplies_laps_led_completed_and_fastest_lap():
    recap = rsc_page(
        {
            "cust_id": 10,
            "name": "Driver Name2",
            "car_number": "81",
            "start_pos": 5,
            "finish_pos": 1,
            "laps_comp": 125,
            "laps_led": 42,
            "inc": 2,
            "league_points": 51,
            "best_lap_ms": 312530,
            "disqualified": False,
            "team_name": "RGC Racing",
            "country_code": "US",
            "avg_lap_ms": 333330,
            "interval": "+0.125s",
            "pos_points": 40,
            "bonus_points": 11,
            "penalty_points": 1,
            "stage_points": 2,
            "time_penalty_seconds": 5,
            "lap_penalty_laps": 1,
            "reason_out": "Running",
        }
    )

    result = parse_recap_result(
        recap,
        2,
        {"track_name": "Atlanta", "notes": "WED SEP 23 - Test Series - 125 laps"},
        {"10": {"name": "Driver Name", "car_number": "81"}},
    )

    assert result.round_number == 2
    assert result.track_name == "Atlanta"
    assert result.entries[0].name == "Driver Name"
    assert result.entries[0].laps_completed == 125
    assert result.entries[0].laps_led == 42
    assert result.entries[0].fastest_lap == 31.253
    assert result.entries[0].team_name == "RGC Racing"
    assert result.entries[0].average_lap == 33.333
    assert result.entries[0].bonus_points == 11
    assert result.entries[0].penalty_points == 1


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


def test_extracts_dedicated_velocity_result_links():
    page = (
        '<a href="/trrl/results/88863839?series=whiskey-throttle-wednesday">Results</a>'
        '<a href="/trrl/results/777?series=tuesday-night-trucks">Other</a>'
    )

    urls = extract_result_urls(
        page,
        "https://www.velocityleague.gg",
        "whiskey-throttle-wednesday",
    )

    assert urls == [
        "https://www.velocityleague.gg/trrl/results/88863839?series=whiskey-throttle-wednesday"
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


def test_structured_standings_selects_requested_series_from_multiple_tables():
    page = rsc_page(
        {"key": "tuesday-night-trucks", "name": "Taco Tuesday Truck Series"},
        {"key": "whiskey-throttle-wednesday", "name": "Whiskey Throttle Wednesday"},
        {"cust_id": 100, "display_name": "Tuesday Leader", "car_number": "31", "total_points": 78, "races": 2},
        {"cust_id": 200, "display_name": "Shared Driver", "car_number": "10", "total_points": 74, "races": 2},
        {"cust_id": 200, "display_name": "Wednesday Leader", "car_number": "81", "total_points": 87, "races": 2},
        {"cust_id": 300, "display_name": "Wednesday Second", "car_number": "34", "total_points": 80, "races": 2},
    )

    tuesday = parse_structured_standings(page, "tuesday-night-trucks")
    wednesday = parse_structured_standings(page, "whiskey-throttle-wednesday")

    assert tuesday[0]["name"] == "Tuesday Leader"
    assert wednesday[0]["name"] == "Wednesday Leader"


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


@pytest.mark.parametrize("series", ["Taco Tuesday Truck Series", "Whiskey Throttle Wednesday"])
def test_repeated_manager_import_preserves_results_and_manual_schedule(tmp_path, series):
    from dataclasses import asdict
    from production.league_manager import (
        RaceResult, RaceResultEntry, ScheduleEvent, calculate_standings,
        load_race_results, load_schedule, save_race_results, save_schedule,
    )
    from tools.velocity_league_import import merge_manager_import

    original = RaceResult(1, "Manual race", "Daytona", [
        RaceResultEntry(1, "Driver", "7", points=44, manual_adjustment=4),
    ])
    manual = ScheduleEvent(2, track_name="Edited track", laps=120,
                           notes="Manual notes", race_time="8:30 PM")
    save_race_results(tmp_path / "results.json", [original])
    save_schedule(tmp_path / "schedule.json", [manual])
    incoming = [RaceResult(1, "Imported", "Daytona", [RaceResultEntry(2, "Driver", points=35)]),
                RaceResult(2, "New race", "Atlanta", [RaceResultEntry(2, "Driver", "7", points=35)])]
    schedule = [{"track_name": "Daytona", "notes": f"TUE SEP 15 - {series} - 80 laps"},
                {"track_name": "Atlanta", "notes": f"TUE SEP 22 - {series} - 100 laps"}]
    for _ in range(2):
        merge_manager_import(tmp_path, incoming, schedule)
    # A temporarily missing source round must not erase saved history.
    merge_manager_import(tmp_path, incoming[:1], schedule)
    results = load_race_results(tmp_path / "results.json")
    assert [race.round_number for race in results] == [1, 2]
    assert asdict(results[0]) == asdict(original)
    event = load_schedule(tmp_path / "schedule.json")[1]
    assert asdict(event) == {**asdict(manual), "status": "Completed"}
    stats = calculate_standings(results)[0]
    assert stats["starts"] == 2
    assert stats["points"] == 79
    assert stats["wins"] == 1
    assert stats["average_finish"] == 1.5
