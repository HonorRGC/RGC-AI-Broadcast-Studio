import sys

from studio_launcher import (
    broadcast_command,
    launcher_defaults,
    load_env_file,
    save_env_file,
    sim_racer_hub_import_command,
)


def test_launcher_loads_simple_env_file(tmp_path):
    env_path = tmp_path / ".env"
    env_path.write_text(
        "\n".join(
            [
                "# comment",
                "USE_OPENAI=false",
                "OVERLAY_EVENT_TITLE=Friday Night 100",
            ]
        ),
        encoding="utf-8",
    )

    values = load_env_file(env_path)

    assert values["USE_OPENAI"] == "false"
    assert values["OVERLAY_EVENT_TITLE"] == "Friday Night 100"


def test_launcher_defaults_include_league_stats_csv():
    defaults = launcher_defaults({})

    assert defaults["LEAGUE_DRIVERS_CSV"] == "league/drivers.csv"
    assert defaults["LEAGUE_STATS_CSV"] == "league/stats.csv"


def test_launcher_saves_known_settings(tmp_path):
    env_path = tmp_path / ".env"

    save_env_file(
        {
            "USE_OPENAI": "false",
            "OVERLAY_EVENT_TITLE": "League Race",
            "LEAGUE_STATS_CSV": "league/stats.csv",
        },
        env_path,
    )

    saved = env_path.read_text(encoding="utf-8")
    assert "USE_OPENAI=false" in saved
    assert "OVERLAY_EVENT_TITLE=League Race" in saved
    assert "LEAGUE_STATS_CSV=league/stats.csv" in saved


def test_launcher_builds_default_broadcast_command():
    command = broadcast_command()

    assert command[0] == sys.executable
    assert "--overlay" in command
    assert "--camera-mode" in command
    assert "--incident-replay" in command


def test_launcher_builds_sim_racer_hub_season_import_command():
    command = sim_racer_hub_import_command(
        "https://simracerhub.com/series_seasons.php?series_id=3872&reset_series=y",
        league_id="1598",
        series_id="3872",
        season_id="29247",
        track_name="Nashville",
        min_starts="2",
        output="league/stats.csv",
    )

    assert command[0] == sys.executable
    assert "tools\\sim_racer_hub_import.py" in command[1] or "tools/sim_racer_hub_import.py" in command[1]
    assert "--bulk" in command
    assert ["--league-id", "1598"] == command[command.index("--league-id") : command.index("--league-id") + 2]
    assert ["--season-id", "29247"] == command[command.index("--season-id") : command.index("--season-id") + 2]
    assert ["--track-name", "Nashville"] == command[command.index("--track-name") : command.index("--track-name") + 2]


def test_launcher_career_import_command_omits_season_id():
    command = sim_racer_hub_import_command(
        "https://simracerhub.com/league_stats.php?series_id=3872",
        league_id="1598",
        series_id="3872",
        season_id="29247",
        career_mode=True,
        dry_run=True,
    )

    assert "--season-id" not in command
    assert "--dry-run" in command
