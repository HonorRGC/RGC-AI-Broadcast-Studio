import csv

from tools.sim_racer_hub_import import (
    clean_driver_name,
    merge_driver_roster,
    merge_stats_row,
    merge_stats_rows,
    normalize_sim_racer_hub_source,
    normalize_sim_racer_hub_schedule_source,
    resolve_track_ids,
    sim_racer_hub_query_value,
    summarize_race_schedule,
    summarize_bulk_driver_stats,
    summarize_driver_roster,
    summarize_driver_stats,
    write_race_schedule,
)


SAMPLE_HTML = """
<html>
<body>
<h1 class='m0'>T.J. Lee</h1>
<script>
ReactDOM.createRoot(document.getElementById('driver_stats')).render(
React.createElement(DriverStats,{user: {"driver_id":0},league_id: 0,rps: {
"1":{"race_participant_id":"1","driver_id":"90223","driver_number":"34","qualify_pos":"2","num_laps":"92","laps_led":"5","finish_pos":"1","race_points":"40","status":"Running","fastest_lap_time":"39.7908","incidents":"2","avg_pos":"3.2","passes":"12","quality_passes":"4","closing_passes":"1","race_date":"2026-07-01","season_id":"29247","track_config_id":"257","series_id":"3872","league_id":"1598","track_id":"105","race_timestamp":1782878400,"race_date_str":"Jul 1, 2026"},
"2":{"race_participant_id":"2","driver_id":"90223","driver_number":"34","qualify_pos":"1","num_laps":"95","laps_led":"0","finish_pos":"6","race_points":"35","status":"Running","fastest_lap_time":"39.1171","incidents":"0","avg_pos":"5.9","passes":"8","quality_passes":"2","closing_passes":"0","race_date":"2026-06-30","season_id":"29247","track_config_id":"328","series_id":"3872","league_id":"1598","track_id":"129","race_timestamp":1782792000,"race_date_str":"Jun 30, 2026"},
"3":{"race_participant_id":"3","driver_id":"90223","driver_number":"34","qualify_pos":"7","num_laps":"90","laps_led":"0","finish_pos":"12","race_points":"30","status":"Running","fastest_lap_time":"40.1171","incidents":"4","avg_pos":"9.9","passes":"2","quality_passes":"0","closing_passes":"0","race_date":"2026-06-20","season_id":"29222","track_config_id":"257","series_id":"4737","league_id":"1598","track_id":"105","race_timestamp":1781923200,"race_date_str":"Jun 20, 2026"},
"4":{"race_participant_id":"4","driver_id":"90223","driver_number":"10","qualify_pos":"3","num_laps":"90","laps_led":"0","finish_pos":"4","race_points":"38","status":"Running","incidents":"2","race_date":"2026-06-10","season_id":"29247","track_config_id":"257","series_id":"3872","league_id":"2841","track_id":"105","race_timestamp":1781059200,"race_date_str":"Jun 10, 2026"}
},seasons: {},series: {},leagues: {},cars: {},configs: {},}));
</script>
</body>
</html>
"""


DATE_ONLY_HTML = """
<html>
<body>
<h1 class='m0'>Series Stats</h1>
<script>
ReactDOM.createRoot(document.getElementById('league_stats')).render(
React.createElement(LeagueStats,{user: {"driver_id":0},league_id: 1598,series_id: 3872,season_id: 0,rps: {
"1":{"race_participant_id":"1","driver_id":"90223","driver_number":"34","qualify_pos":"2","num_laps":"92","laps_led":"5","finish_pos":"1","race_points":"40","status":"Running","incidents":"2","race_date":"2025-01-01","season_id":"1","track_config_id":"257","series_id":"3872","league_id":"1598","track_id":"105"},
"2":{"race_participant_id":"2","driver_id":"90223","driver_number":"34","qualify_pos":"1","num_laps":"95","laps_led":"0","finish_pos":"6","race_points":"35","status":"Running","incidents":"0","race_date":"2026-07-01","season_id":"2","track_config_id":"328","series_id":"3872","league_id":"1598","track_id":"129"}
},drivers: {
"90223":{"driver_id":"90223","driver_name":"T.J. Lee","driver_last_first":"Lee, T.J.","driver_is_ai":"N","flair_country_code":"US"}
},seasons: {},series: {},leagues: {},cars: {},configs: {},}));
</script>
</body>
</html>
"""


BULK_HTML = """
<html>
<body>
<h1 class='m0'>Series Stats</h1>
<script>
ReactDOM.createRoot(document.getElementById('league_stats')).render(
React.createElement(LeagueStats,{user: {"driver_id":0},league_id: 1598,series_id: 3872,season_id: 0,rps: {
"1":{"race_participant_id":"1","driver_id":"90223","driver_number":"34","qualify_pos":"2","num_laps":"92","laps_led":"5","finish_pos":"1","race_points":"40","status":"Running","fastest_lap_time":"39.7908","incidents":"2","avg_pos":"3.2","passes":"12","quality_passes":"4","closing_passes":"1","race_date":"2026-07-01","season_id":"29247","track_config_id":"257","series_id":"3872","league_id":"1598","track_id":"105","race_timestamp":1782878400,"race_date_str":"Jul 1, 2026"},
"2":{"race_participant_id":"2","driver_id":"90223","driver_number":"34","qualify_pos":"1","num_laps":"95","laps_led":"0","finish_pos":"6","race_points":"35","status":"Running","fastest_lap_time":"39.1171","incidents":"0","avg_pos":"5.9","passes":"8","quality_passes":"2","closing_passes":"0","race_date":"2026-06-30","season_id":"29247","track_config_id":"328","series_id":"3872","league_id":"1598","track_id":"129","race_timestamp":1782792000,"race_date_str":"Jun 30, 2026"},
"3":{"race_participant_id":"3","driver_id":"1110","driver_number":"12","qualify_pos":"4","num_laps":"92","laps_led":"0","finish_pos":"4","race_points":"37","status":"Running","fastest_lap_time":"39.9000","incidents":"0","avg_pos":"4.8","passes":"5","quality_passes":"1","closing_passes":"0","race_date":"2026-07-01","season_id":"29247","track_config_id":"257","series_id":"3872","league_id":"1598","track_id":"105","race_timestamp":1782878400,"race_date_str":"Jul 1, 2026"},
"4":{"race_participant_id":"4","driver_id":"3333","driver_number":"88","qualify_pos":"10","num_laps":"90","laps_led":"0","finish_pos":"20","race_points":"20","status":"Running","incidents":"6","race_date":"2026-07-01","season_id":"29222","track_config_id":"257","series_id":"3872","league_id":"1598","track_id":"105","race_timestamp":1782878400,"race_date_str":"Jul 1, 2026"}
},drivers: {
"90223":{"driver_id":"90223","driver_name":"T.J. Lee","driver_last_first":"Lee, T.J.","driver_is_ai":"N","flair_country_code":"US"},
"1110":{"driver_id":"1110","driver_name":"Justin Gledhill","driver_last_first":"Gledhill, Justin","driver_is_ai":"N","flair_country_code":"US"},
"3333":{"driver_id":"3333","driver_name":"Other Season","driver_last_first":"Season, Other","driver_is_ai":"N","flair_country_code":"US"}
},seasons: {},series: {},leagues: {},cars: {},configs: {
"257":{"track_config_id":"257","track_config_short":"Michigan","track_id":"105","track_name":"Michigan International Speedway","type_name":"Speedway"},
"328":{"track_config_id":"328","track_config_short":"Nashville SS","track_id":"129","track_name":"Nashville Superspeedway","type_name":"Speedway"}
},}));
</script>
</body>
</html>
"""


SCHEDULE_HTML = """
<html>
<body>
<script>
ReactDOM.createRoot(document.getElementById('series_seasons')).render(
React.createElement(SeriesSeasons,{series_id: 3872, seasons: {}, schedules: {
"10":{"schedule_id":"356761","series_id":"3872","season_id":"29247","league_id":"1598","track_config_id":"257","race_date":"2026-07-01","race_name":"Race 1"},
"11":{"schedule_id":"356762","series_id":"3872","season_id":"29247","league_id":"1598","track_config_id":"328","race_date":"2026-07-08","race_name":"Race 2"},
"12":{"schedule_id":"999999","series_id":"3872","season_id":"29248","league_id":"1598","track_config_id":"257","race_date":"2026-08-01","race_name":"Wrong season"}
}, configs: {
"257":{"track_config_id":"257","track_config_short":"Michigan","track_id":"105","track_name":"Michigan International Speedway","type_name":"Speedway"},
"328":{"track_config_id":"328","track_config_short":"Nashville SS","track_id":"129","track_name":"Nashville Superspeedway","type_name":"Speedway"}
}}));
</script>
</body>
</html>
"""


SCHEDULE_FROM_RPS_HTML = """
<html>
<body>
<script>
ReactDOM.createRoot(document.getElementById('league_stats')).render(
React.createElement(LeagueStats,{series_id: 3872, season_id: 29247, rps: {
"100":{"driver_id":"1","series_id":"3872","season_id":"29247","league_id":"1598","track_config_id":"257","race_date":"2026-07-01","race_name":"Race 1"},
"101":{"driver_id":"2","series_id":"3872","season_id":"29247","league_id":"1598","track_config_id":"257","race_date":"2026-07-01","race_name":"Race 1"},
"102":{"driver_id":"1","series_id":"3872","season_id":"29247","league_id":"1598","track_config_id":"328","race_date":"2026-07-08","race_name":"Race 2"},
"103":{"driver_id":"2","series_id":"3872","season_id":"29248","league_id":"1598","track_config_id":"257","race_date":"2026-08-01","race_name":"Wrong season"}
}, configs: {
"257":{"track_config_id":"257","track_config_short":"Michigan","track_id":"105","track_name":"Michigan International Speedway","type_name":"Speedway"},
"328":{"track_config_id":"328","track_config_short":"Nashville SS","track_id":"129","track_name":"Nashville Superspeedway","type_name":"Speedway"}
}}));
</script>
</body>
</html>
"""


SCHEDULE_ARRAY_HTML = """
<html>
<body>
<script>
ReactDOM.createRoot(document.getElementById('series_seasons')).render(
React.createElement(SeriesSeasons,{series_id: 3872, seasons: {}, schedules: [
{"schedule_id":"356761","series_id":"3872","season_id":"29247","league_id":"1598","track_config_id":"257","race_date":"2026-07-01","race_name":"Race 1"},
{"schedule_id":"356762","series_id":"3872","season_id":"29247","league_id":"1598","track_config_id":"328","race_date":"2026-07-08","race_name":"Race 2"},
{"schedule_id":"999999","series_id":"3872","season_id":"29248","league_id":"1598","track_config_id":"257","race_date":"2026-08-01","race_name":"Wrong season"}
], configs: {
"257":{"track_config_id":"257","track_config_short":"Michigan","track_id":"105","track_name":"Michigan International Speedway","type_name":"Speedway"},
"328":{"track_config_id":"328","track_config_short":"Nashville SS","track_id":"129","track_name":"Nashville Superspeedway","type_name":"Speedway"}
}}));
</script>
</body>
</html>
"""


FUTURE_SCHEDULE_LINKS_HTML = """
<html>
<body>
<a href="season_standings.php?season_id=29247&schedule_id=356745">Race 1 - Michigan International Speedway</a>
<a href="season_standings.php?season_id=29247&schedule_id=356746">Race 2 - Nashville Superspeedway</a>
<a href="season_standings.php?season_id=99999&schedule_id=999999">Wrong Season</a>
</body>
</html>
"""


UPCOMING_SCHEDULE_RECORDS_HTML = """
<html>
<body>
<script>
ReactDOM.createRoot(document.getElementById('series_seasons')).render(
React.createElement(SeriesSeasons,{series_id: 3872, seasons: {}, schedules: [
{"schedule_id":"356745","season_id":"29247","track_config_id":"257","race_date":"2026-08-01","race_name":"Race 1"},
{"schedule_id":"356746","season_id":"29247","track_config_id":"328","race_date":"2026-08-08","race_name":"Race 2"}
], configs: {
"257":{"track_config_id":"257","track_config_short":"Michigan","track_id":"105","track_name":"Michigan International Speedway","type_name":"Speedway"},
"328":{"track_config_id":"328","track_config_short":"Nashville SS","track_id":"129","track_name":"Nashville Superspeedway","type_name":"Speedway"}
}}));
</script>
</body>
</html>
"""


def test_summarizes_sim_racer_hub_driver_stats_for_filtered_season():
    row = summarize_driver_stats(
        SAMPLE_HTML,
        league_id="1598",
        series_id="3872",
        season_id="29247",
        track_config_id="257",
    )

    assert row["name"] == "T.J. Lee"
    assert row["car_number"] == "34"
    assert row["stats_scope"] == "season"
    assert row["starts"] == "2"
    assert row["wins"] == "1"
    assert row["top_fives"] == "1"
    assert row["top_tens"] == "2"
    assert row["poles"] == "1"
    assert row["avg_finish"] == "3.5"
    assert row["last_finish"] == "1"
    assert row["track_starts"] == "1"
    assert row["track_wins"] == "1"
    assert row["best_track_finish"] == "1"
    assert "20 passes" in row["notes"]
    assert "quality passes" in row["notes"]


def test_merge_stats_row_updates_existing_driver_by_name(tmp_path):
    output = tmp_path / "stats.csv"
    output.write_text(
        "name,car_number,stats_scope,starts,wins,top_fives,top_tens,poles,avg_finish,last_finish,points_position,points_to_next,track_starts,track_wins,best_track_finish,notes\n"
        "T.J. Lee,34,season,1,0,0,1,0,8.0,8,,,,,,old\n",
        encoding="utf-8",
    )

    row = summarize_driver_stats(SAMPLE_HTML, league_id="1598", season_id="29247")
    merge_stats_row(output, row)

    with output.open(newline="", encoding="utf-8") as csv_file:
        rows = list(csv.DictReader(csv_file))

    assert len(rows) == 1
    assert rows[0]["name"] == "T.J. Lee"
    assert rows[0]["starts"] == "2"
    assert rows[0]["wins"] == "1"


def test_merge_stats_row_keeps_season_and_career_for_same_driver(tmp_path):
    output = tmp_path / "stats.csv"
    output.write_text(
        "name,car_number,stats_scope,starts,wins,top_fives,top_tens,poles,avg_finish,last_finish,points_position,points_to_next,track_starts,track_wins,best_track_finish,notes\n"
        "T.J. Lee,34,career,100,4,20,40,3,9.1,5,,,,,,career row\n",
        encoding="utf-8",
    )

    merge_stats_row(
        output,
        {
            "name": "T.J. Lee",
            "car_number": "34",
            "stats_scope": "season",
            "starts": "6",
            "wins": "0",
            "top_fives": "2",
            "top_tens": "4",
            "poles": "1",
            "avg_finish": "8.2",
            "last_finish": "7",
            "notes": "season row",
        },
    )

    with output.open(newline="", encoding="utf-8") as csv_file:
        rows = list(csv.DictReader(csv_file))

    assert [row["stats_scope"] for row in rows] == ["career", "season"]
    assert rows[0]["wins"] == "4"
    assert rows[1]["wins"] == "0"


def test_merge_stats_row_updates_old_sim_racer_hub_suffix_name(tmp_path):
    output = tmp_path / "stats.csv"
    output.write_text(
        "name,car_number,stats_scope,starts,wins,top_fives,top_tens,poles,avg_finish,last_finish,points_position,points_to_next,track_starts,track_wins,best_track_finish,notes\n"
        "Richard Holland2,,season,100,1,2,3,4,8.0,8,,,,,,old\n",
        encoding="utf-8",
    )

    merge_stats_row(
        output,
        {
            "name": "Richard Holland",
            "stats_scope": "season",
            "starts": "182",
            "wins": "47",
            "top_fives": "124",
            "top_tens": "158",
            "poles": "24",
            "avg_finish": "5.3",
            "last_finish": "2",
            "notes": "clean",
        },
    )

    with output.open(newline="", encoding="utf-8") as csv_file:
        rows = list(csv.DictReader(csv_file))

    assert len(rows) == 1
    assert rows[0]["name"] == "Richard Holland"
    assert rows[0]["starts"] == "182"
    assert rows[0]["notes"] == "clean"


def test_bulk_import_summarizes_all_matching_drivers():
    rows = summarize_bulk_driver_stats(
        BULK_HTML,
        league_id="1598",
        series_id="3872",
        season_id="29247",
        track_config_id="257",
    )

    assert [row["name"] for row in rows] == ["T.J. Lee", "Justin Gledhill"]
    assert rows[0]["stats_scope"] == "season"
    assert rows[0]["starts"] == "2"
    assert rows[0]["wins"] == "1"
    assert rows[0]["track_starts"] == "1"
    assert rows[1]["starts"] == "1"
    assert rows[1]["top_fives"] == "1"
    assert "37 race points" in rows[1]["notes"]


def test_bulk_import_marks_career_scope_without_season_filter():
    rows = summarize_bulk_driver_stats(
        BULK_HTML,
        league_id="1598",
        series_id="3872",
    )

    assert rows[0]["stats_scope"] == "career"


def test_summarize_driver_roster_from_bulk_page():
    rows = summarize_driver_roster(
        BULK_HTML,
        league_id="1598",
        series_id="3872",
        season_id="29247",
    )

    assert [row["name"] for row in rows] == ["Justin Gledhill", "T.J. Lee"]
    assert rows[0]["country"] == "USA"
    assert rows[0]["driving_style"] == ""
    assert rows[0]["notes"] == ""
    assert rows[0]["car_image"] == ""


def test_merge_driver_roster_preserves_manual_notes(tmp_path):
    output = tmp_path / "drivers.csv"
    output.write_text(
        "name,car_number,hometown,state,country,driving_style,sponsor,notes,car_image\n"
        "Richard Holland2,51,Richmond,VA,USA,tire saver,RGC Motorsports,Great on long runs,cars/richard.png\n",
        encoding="utf-8",
    )

    merge_driver_roster(
        output,
        [
            {
                "name": "Richard Holland",
                "car_number": "",
                "hometown": "",
                "state": "",
                "country": "USA",
                "driving_style": "",
                "sponsor": "",
                "notes": "",
                "car_image": "",
            },
            {
                "name": "T.J. Lee",
                "car_number": "34",
                "hometown": "",
                "state": "",
                "country": "USA",
                "driving_style": "",
                "sponsor": "",
                "notes": "",
                "car_image": "",
            },
        ],
    )

    with output.open(newline="", encoding="utf-8") as csv_file:
        rows = list(csv.DictReader(csv_file))

    assert rows[0]["name"] == "Richard Holland"
    assert rows[0]["car_number"] == "51"
    assert rows[0]["driving_style"] == "tire saver"
    assert rows[0]["sponsor"] == "RGC Motorsports"
    assert rows[0]["notes"] == "Great on long runs"
    assert rows[0]["car_image"] == "cars/richard.png"
    assert rows[1]["name"] == "T.J. Lee"
    assert rows[1]["car_number"] == "34"


def test_bulk_import_resolves_track_history_by_track_name():
    rows = summarize_bulk_driver_stats(
        BULK_HTML,
        league_id="1598",
        series_id="3872",
        season_id="29247",
        track_name="Michigan",
    )

    assert rows[0]["track_starts"] == "1"
    assert rows[0]["track_wins"] == "1"
    assert rows[0]["best_track_finish"] == "1"
    assert "last track race Jul 1, 2026: finished 1st" in rows[0]["notes"]
    assert rows[1]["track_starts"] == "1"


def test_resolve_track_ids_matches_track_config_short_and_track_name():
    ids = resolve_track_ids(BULK_HTML, track_name="Nashville")

    assert "129" in ids["track_ids"]
    assert "328" in ids["track_config_ids"]


def test_bulk_import_uses_race_date_when_timestamp_is_missing():
    rows = summarize_bulk_driver_stats(
        DATE_ONLY_HTML,
        league_id="1598",
        series_id="3872",
    )

    assert len(rows) == 1
    assert rows[0]["last_finish"] == "6"
    assert "last race 2026-07-01" in rows[0]["notes"]


def test_merge_stats_rows_adds_multiple_drivers(tmp_path):
    output = tmp_path / "stats.csv"
    rows = summarize_bulk_driver_stats(BULK_HTML, league_id="1598", season_id="29247")
    merge_stats_rows(output, rows)

    with output.open(newline="", encoding="utf-8") as csv_file:
        imported = list(csv.DictReader(csv_file))

    assert len(imported) == 2
    assert imported[0]["name"] == "T.J. Lee"
    assert imported[1]["name"] == "Justin Gledhill"


def test_series_seasons_url_normalizes_to_league_stats_url():
    url = normalize_sim_racer_hub_source(
        "https://simracerhub.com/series_seasons.php?series_id=3872&reset_series=y"
    )

    assert url == "https://simracerhub.com/league_stats.php?series_id=3872"


def test_sim_racer_hub_home_url_uses_series_and_season_filters():
    url = normalize_sim_racer_hub_source(
        "https://simracerhub.com",
        series_id="3872",
        season_id="29247",
    )

    assert url == "https://simracerhub.com/league_stats.php?series_id=3872&season_id=29247"


def test_sim_racer_hub_home_url_uses_series_seasons_for_schedule_import():
    url = normalize_sim_racer_hub_schedule_source(
        "https://simracerhub.com",
        series_id="3872",
        season_id="29247",
    )

    assert url == "https://simracerhub.com/series_seasons.php?series_id=3872&season_id=29247"


def test_sim_racer_hub_standings_url_exposes_season_and_schedule_ids():
    source = "https://www.simracerhub.com/season_standings.php?season_id=29247&schedule_id=356745"

    assert sim_racer_hub_query_value(source, "season_id") == "29247"
    assert sim_racer_hub_query_value(source, "schedule_id") == "356745"


def test_summarizes_sim_racer_hub_race_schedule_for_season():
    rows = summarize_race_schedule(
        SCHEDULE_HTML,
        league_id="1598",
        series_id="3872",
        season_id="29247",
        source_url="https://simracerhub.com",
    )

    assert rows == [
        {
            "track_name": "Michigan International Speedway",
            "schedule_id": "356761",
            "results_url": "",
            "notes": "Race 1",
        },
        {
            "track_name": "Nashville Superspeedway",
            "schedule_id": "356762",
            "results_url": "",
            "notes": "Race 2",
        },
    ]


def test_summarizes_sim_racer_hub_race_schedule_from_array_data():
    rows = summarize_race_schedule(
        SCHEDULE_ARRAY_HTML,
        league_id="1598",
        series_id="3872",
        season_id="29247",
        source_url="https://simracerhub.com",
    )

    assert [row["schedule_id"] for row in rows] == ["356761", "356762"]
    assert [row["track_name"] for row in rows] == [
        "Michigan International Speedway",
        "Nashville Superspeedway",
    ]


def test_summarizes_future_schedule_links_from_season_standings():
    rows = summarize_race_schedule(
        FUTURE_SCHEDULE_LINKS_HTML,
        season_id="29247",
        source_url="https://www.simracerhub.com/season_standings.php?season_id=29247",
    )

    assert rows == [
        {
            "track_name": "Race 1 - Michigan International Speedway",
            "schedule_id": "356745",
            "results_url": "https://www.simracerhub.com/season_standings.php?season_id=29247&schedule_id=356745",
            "notes": "",
        },
        {
            "track_name": "Race 2 - Nashville Superspeedway",
            "schedule_id": "356746",
            "results_url": "https://www.simracerhub.com/season_standings.php?season_id=29247&schedule_id=356746",
            "notes": "",
        },
    ]


def test_summarizes_upcoming_schedule_records_without_completed_results():
    rows = summarize_race_schedule(
        UPCOMING_SCHEDULE_RECORDS_HTML,
        league_id="1598",
        series_id="3872",
        season_id="29247",
        source_url="https://simracerhub.com",
    )

    assert [row["schedule_id"] for row in rows] == ["356745", "356746"]
    assert [row["track_name"] for row in rows] == [
        "Michigan International Speedway",
        "Nashville Superspeedway",
    ]


def test_summarizes_race_schedule_from_participants_with_first_schedule_id():
    rows = summarize_race_schedule(
        SCHEDULE_FROM_RPS_HTML,
        league_id="1598",
        series_id="3872",
        season_id="29247",
        source_url="https://simracerhub.com",
        first_schedule_id="356761",
    )

    assert rows == [
        {
            "track_name": "Michigan International Speedway",
            "schedule_id": "356761",
            "results_url": "https://simracerhub.com/scoring/season_race.php?schedule_id=356761",
            "notes": "Race 1",
        },
        {
            "track_name": "Nashville Superspeedway",
            "schedule_id": "356762",
            "results_url": "https://simracerhub.com/scoring/season_race.php?schedule_id=356762",
            "notes": "Race 2",
        },
    ]


def test_write_race_schedule_csv(tmp_path):
    output = tmp_path / "race_schedule.csv"
    rows = summarize_race_schedule(
        SCHEDULE_HTML,
        league_id="1598",
        series_id="3872",
        season_id="29247",
    )

    write_race_schedule(output, rows)

    with output.open(newline="", encoding="utf-8") as csv_file:
        imported = list(csv.DictReader(csv_file))

    assert imported[0]["track_name"] == "Michigan International Speedway"
    assert imported[0]["schedule_id"] == "356761"


def test_clean_driver_name_removes_sim_racer_hub_duplicate_suffix():
    assert clean_driver_name("Richard Holland2") == "Richard Holland"
    assert clean_driver_name("Travis Smith6") == "Travis Smith"
    assert clean_driver_name("T.J. Lee") == "T.J. Lee"
    assert clean_driver_name("Dale Earnhardt Jr.") == "Dale Earnhardt Jr."
