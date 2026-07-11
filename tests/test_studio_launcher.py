import sys
from pathlib import Path
from types import SimpleNamespace

from studio_launcher import (
    DEFAULT_OVERLAY_URL,
    RGC_DISCORD_URL,
    RGC_WEBSITE_URL,
    apply_audio_file_selection,
    broadcast_command,
    clear_broadcast_pid,
    format_playlist_paths,
    has_running_broadcast,
    install_overlay_brand_graphics,
    is_process_running,
    launcher_defaults,
    load_env_file,
    read_broadcast_pid,
    running_broadcast_pids,
    save_env_file,
    sanitize_asset_name,
    sim_racer_hub_import_command,
    stop_broadcast_processes,
    write_broadcast_pid,
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


def test_launcher_includes_rgc_links():
    assert RGC_DISCORD_URL == "https://discord.gg/Axwwa8CUqt"
    assert RGC_WEBSITE_URL == "https://www.realisticgamingcrew.com"
    assert DEFAULT_OVERLAY_URL == "http://127.0.0.1:8765/overlay"


def test_launcher_defaults_include_league_stats_csv():
    defaults = launcher_defaults({})

    assert defaults["LEAGUE_DRIVERS_CSV"] == "league/drivers.csv"
    assert defaults["LEAGUE_STATS_CSV"] == "league/stats.csv"
    assert "/assets/rgc_motorsports.png" in defaults["OVERLAY_BRAND_GRAPHICS"]
    assert defaults["PRACTICE_MUSIC_PLAYLIST"] == ""
    assert defaults["CAUTION_REPLAY_AUDIO"] == ""
    assert defaults["NATIONAL_ANTHEM_AUDIO"] == ""
    assert defaults["POST_RACE_INTERVIEWS_ENABLED"] == "false"


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


def test_launcher_saves_music_settings(tmp_path):
    env_path = tmp_path / ".env"

    save_env_file(
        {
            "PRACTICE_MUSIC_PLAYLIST": "D:/Music/practice1.mp3;D:/Music/practice2.mp3",
            "CAUTION_REPLAY_AUDIO": "D:/Music/caution.mp3",
            "NATIONAL_ANTHEM_AUDIO": "D:/Music/anthem.mp3",
        },
        env_path,
    )

    saved = env_path.read_text(encoding="utf-8")
    assert "PRACTICE_MUSIC_PLAYLIST=D:/Music/practice1.mp3;D:/Music/practice2.mp3" in saved
    assert "CAUTION_REPLAY_AUDIO=D:/Music/caution.mp3" in saved
    assert "NATIONAL_ANTHEM_AUDIO=D:/Music/anthem.mp3" in saved


def test_launcher_formats_practice_music_playlist():
    playlist = format_playlist_paths(["D:/Music/one.mp3", "D:/Music/two.mp3"])

    assert playlist.split(";") == [str(Path("D:/Music/one.mp3")), str(Path("D:/Music/two.mp3"))]


def test_launcher_turns_on_anthem_when_audio_is_selected():
    values = apply_audio_file_selection(
        {"USE_NATIONAL_ANTHEM": "false"},
        "NATIONAL_ANTHEM_AUDIO",
        "D:/Music/anthem.mp3",
    )

    assert values["USE_NATIONAL_ANTHEM"] == "true"
    assert values["NATIONAL_ANTHEM_AUDIO"] == str(Path("D:/Music/anthem.mp3"))


def test_launcher_sanitizes_overlay_asset_names():
    assert sanitize_asset_name("D:/Editor/decals/RGC Motorsports Logo.PNG") == "rgc_motorsports_logo.png"


def test_launcher_installs_overlay_brand_graphics(tmp_path):
    source = tmp_path / "RGC Motorsports Logo.PNG"
    source.write_bytes(b"fake image")
    static_dir = tmp_path / "static"

    assets = install_overlay_brand_graphics([source], static_dir=static_dir)

    assert assets == ["/assets/rgc_motorsports_logo.png"]
    assert (static_dir / "rgc_motorsports_logo.png").read_bytes() == b"fake image"


def test_launcher_builds_default_broadcast_command():
    command = broadcast_command()

    assert command[0] == sys.executable
    assert "--overlay" in command
    assert "--camera-mode" in command
    assert "--incident-replay" in command


def test_launcher_detects_running_process():
    class RunningProcess:
        def poll(self):
            return None

    class StoppedProcess:
        def poll(self):
            return 0

    assert is_process_running(RunningProcess())
    assert not is_process_running(StoppedProcess())
    assert not is_process_running(None)


def test_launcher_finds_running_broadcast_pids(monkeypatch):
    def fake_run(command, text, capture_output, check):
        assert "powershell" in command[0].lower()
        return SimpleNamespace(returncode=0, stdout="1234\nnot-a-pid\n5678\n")

    monkeypatch.setattr("studio_launcher.subprocess.run", fake_run)

    assert running_broadcast_pids(root=Path("C:/RGC")) == [1234, 5678]


def test_launcher_counts_stopped_broadcast_processes(monkeypatch):
    calls = []

    def fake_run(command, text, capture_output, check):
        calls.append(command)
        return SimpleNamespace(returncode=0, stdout="")

    monkeypatch.setattr("studio_launcher.subprocess.run", fake_run)

    assert stop_broadcast_processes([1234, 5678]) == 2
    assert calls[0] == ["taskkill", "/PID", "1234", "/T", "/F"]
    assert calls[1] == ["taskkill", "/PID", "5678", "/T", "/F"]


def test_launcher_writes_and_reads_broadcast_pid(tmp_path):
    path = tmp_path / ".runtime" / "broadcast.pid"

    write_broadcast_pid(4321, path=path)

    assert read_broadcast_pid(path=path) == 4321
    clear_broadcast_pid(path=path)
    assert read_broadcast_pid(path=path) is None


def test_launcher_detects_external_running_broadcast(monkeypatch):
    monkeypatch.setattr("studio_launcher.BROADCAST_PROCESS", None)
    monkeypatch.setattr("studio_launcher.read_broadcast_pid", lambda: None)
    monkeypatch.setattr("studio_launcher.running_broadcast_pids", lambda: [1234])

    assert has_running_broadcast()


def test_launcher_detects_saved_broadcast_pid(monkeypatch):
    monkeypatch.setattr("studio_launcher.BROADCAST_PROCESS", None)
    monkeypatch.setattr("studio_launcher.read_broadcast_pid", lambda: 4321)
    monkeypatch.setattr("studio_launcher.running_broadcast_pids", lambda: [])

    assert has_running_broadcast()


def test_launcher_builds_sim_racer_hub_season_import_command():
    command = sim_racer_hub_import_command(
        "https://simracerhub.com",
        league_id="1598",
        series_id="3872",
        season_id="29247",
        track_name="Nashville",
        min_starts="2",
        output="league/stats.csv",
    )

    assert command[0] == sys.executable
    assert "tools\\sim_racer_hub_import.py" in command[1] or "tools/sim_racer_hub_import.py" in command[1]
    assert "https://simracerhub.com" in command
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


def test_launcher_builds_sim_racer_hub_driver_roster_command():
    command = sim_racer_hub_import_command(
        "https://simracerhub.com/league_stats.php?series_id=3872",
        league_id="1598",
        series_id="3872",
        season_id="29247",
        drivers_output="league/drivers.csv",
        drivers_only=True,
    )

    assert "--drivers-only" in command
    assert ["--drivers-output", "league/drivers.csv"] == command[
        command.index("--drivers-output") : command.index("--drivers-output") + 2
    ]
