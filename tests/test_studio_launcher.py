import sys

from studio_launcher import (
    broadcast_command,
    launcher_defaults,
    load_env_file,
    save_env_file,
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

