import csv

from tools.sim_racer_hub_import import (
    merge_stats_row,
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
