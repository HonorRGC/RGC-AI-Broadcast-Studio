import csv

from tools.sim_racer_hub_import import (
    clean_driver_name,
    merge_stats_row,
    merge_stats_rows,
    normalize_sim_racer_hub_source,
    resolve_track_ids,
    summarize_bulk_driver_stats,
    summarize_driver_stats,
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
        "name,car_number,starts,wins,top_fives,top_tens,poles,avg_finish,last_finish,points_position,points_to_next,track_starts,track_wins,best_track_finish,notes\n"
        "T.J. Lee,34,1,0,0,1,0,8.0,8,,,,,,old\n",
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


def test_bulk_import_summarizes_all_matching_drivers():
    rows = summarize_bulk_driver_stats(
        BULK_HTML,
        league_id="1598",
        series_id="3872",
        season_id="29247",
        track_config_id="257",
    )

    assert [row["name"] for row in rows] == ["T.J. Lee", "Justin Gledhill"]
    assert rows[0]["starts"] == "2"
    assert rows[0]["wins"] == "1"
    assert rows[0]["track_starts"] == "1"
    assert rows[1]["starts"] == "1"
    assert rows[1]["top_fives"] == "1"
    assert "37 race points" in rows[1]["notes"]


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


def test_clean_driver_name_removes_sim_racer_hub_duplicate_suffix():
    assert clean_driver_name("Richard Holland2") == "Richard Holland"
    assert clean_driver_name("Travis Smith6") == "Travis Smith"
    assert clean_driver_name("T.J. Lee") == "T.J. Lee"
    assert clean_driver_name("Dale Earnhardt Jr.") == "Dale Earnhardt Jr."
