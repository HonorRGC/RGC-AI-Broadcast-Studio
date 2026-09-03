import sys
from pathlib import Path
from types import SimpleNamespace

from studio_launcher import (
    BROADCAST_FIELD_HELP,
    BROADCAST_FIELD_LABELS,
    BROADCAST_FIELD_SECTIONS,
    CLOSE_RUNNING_BROADCAST_MESSAGE,
    CLOSE_RUNNING_BROADCAST_TITLE,
    DEFAULT_OVERLAY_URL,
    DEFAULT_PRODUCER_URL,
    IMPORTANT_SETUP_FIELDS,
    LAUNCHER_FIELDS,
    RGC_DISCORD_URL,
    RGC_WEBSITE_URL,
    TAILSCALE_WINDOWS_DOWNLOAD_URL,
    apply_audio_file_selection,
    build_first_time_setup_checklist,
    build_health_status,
    broadcast_command,
    clear_broadcast_pid,
    delete_profile,
    format_playlist_paths,
    generate_remote_session_code,
    has_running_broadcast,
    install_overlay_brand_graphics,
    install_overlay_commercial_video,
    is_newer_version,
    is_process_running,
    driver_roster_import_target,
    league_csv_paths_for_profile,
    league_folder_slug,
    launcher_defaults,
    list_profiles,
    load_profile,
    load_env_file,
    profile_path,
    producer_assist_launch_url,
    read_broadcast_pid,
    remote_producer_link,
    running_broadcast_pids,
    save_env_file,
    ensure_empty_driver_profile_csv,
    ensure_empty_race_schedule_csv,
    save_profile,
    sanitize_asset_name,
    sanitize_video_asset_name,
    sanitize_profile_name,
    sim_racer_hub_import_command,
    stop_broadcast_processes,
    update_status_from_release,
    version_parts,
    write_broadcast_pid,
)
from tools.build_tester_zip import should_include
from tools.build_windows_setup import (
    DEFAULT_INNO_PATHS,
    build_inno_command,
    project_version,
    should_include_for_installer,
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
    assert TAILSCALE_WINDOWS_DOWNLOAD_URL == "https://tailscale.com/download/windows"
    assert DEFAULT_OVERLAY_URL == "http://127.0.0.1:8765/overlay"
    assert DEFAULT_PRODUCER_URL == "http://127.0.0.1:8765/producer"
    assert producer_assist_launch_url() == DEFAULT_PRODUCER_URL


def test_close_warning_explains_broadcast_related_process():
    assert CLOSE_RUNNING_BROADCAST_TITLE == "Broadcast process detected"
    assert "broadcast-related process" in CLOSE_RUNNING_BROADCAST_MESSAGE
    assert "broadcast/Producer Assist to keep running" in CLOSE_RUNNING_BROADCAST_MESSAGE


def test_broadcast_settings_have_friendly_labels_and_sections():
    assert BROADCAST_FIELD_LABELS["USE_OPENAI"] == "Use OpenAI Commentary"
    assert BROADCAST_FIELD_LABELS["OVERLAY_EVENT_TITLE"] == "Overlay Event Title"
    assert BROADCAST_FIELD_LABELS["OVERLAY_LEADERBOARD_STYLE"] == "Leaderboard Style"
    assert "flo uses a compact two-row top leaderboard" in BROADCAST_FIELD_HELP["OVERLAY_LEADERBOARD_STYLE"]
    assert "brazen uses a leader-focused top board" in BROADCAST_FIELD_HELP["OVERLAY_LEADERBOARD_STYLE"]
    assert BROADCAST_FIELD_LABELS["OVERLAY_HOST"] == "Remote Producer Assist Access"
    assert "trusted admins on your Tailscale network" in BROADCAST_FIELD_HELP["OVERLAY_HOST"]
    assert BROADCAST_FIELD_LABELS["USE_SIM_RACING_APPS"] == "Use SIMRacingApps Car Graphics"
    assert "set this to false" in BROADCAST_FIELD_HELP["USE_SIM_RACING_APPS"]
    assert BROADCAST_FIELD_LABELS["LEAD_BROADCASTER_NAME"] == "Lead Broadcaster Name"
    assert BROADCAST_FIELD_LABELS["COLOR_BROADCASTER_NAME"] == "Analyst Broadcaster Name"
    assert BROADCAST_FIELD_LABELS["PIT_BROADCASTER_NAME"] == "Pit Road Broadcaster Name"
    assert BROADCAST_FIELD_LABELS["LEAD_VOICE_ID"] == "Lead Voice ID"
    assert BROADCAST_FIELD_LABELS["COLOR_VOICE_ID"] == "Analyst Voice ID"
    assert BROADCAST_FIELD_LABELS["PIT_VOICE_ID"] == "Pit Road Voice ID"
    assert "introduces themselves" in BROADCAST_FIELD_HELP["LEAD_BROADCASTER_NAME"]
    assert BROADCAST_FIELD_LABELS["RACE_SPONSOR_1_NAME"] == "Sponsor 1 Name"
    assert BROADCAST_FIELD_LABELS["RACE_SPONSOR_1_LOGO"] == "Sponsor 1 Logo"
    assert BROADCAST_FIELD_LABELS["RACE_SPONSOR_1_READ"] == "Sponsor 1 Spoken Read"
    assert BROADCAST_FIELD_LABELS["RACE_SPONSOR_1_VIDEO"] == "Sponsor 1 Commercial Video"
    assert BROADCAST_FIELD_LABELS["CRANK_IT_UP_SPONSOR_NAME"] == "Crank It Up Sponsor"
    assert "Sponsor 1" in BROADCAST_FIELD_HELP["CRANK_IT_UP_SPONSOR_NAME"]
    assert BROADCAST_FIELD_LABELS["SPONSOR_READ_CAUSE_NAME"] == "Cause / Awareness Name"
    assert BROADCAST_FIELD_LABELS["SPONSOR_READ_CAUSE_LOGO"] == "Cause / Awareness Logo"
    assert BROADCAST_FIELD_LABELS["SPONSOR_READ_CAUSE_READ"] == "Cause / Awareness Spoken Read"
    assert BROADCAST_FIELD_LABELS["RACE_ADMIN_MODE"] == "Race Admin Mode"
    assert BROADCAST_FIELD_LABELS["RACE_ADMIN_SEND_MODE"] == "Race Admin Send Mode"
    assert BROADCAST_FIELD_LABELS["QUALIFYING_MUSIC_PLAYLIST"] == "Qualifying Music Playlist"
    assert "loop during qualifying" in BROADCAST_FIELD_HELP["QUALIFYING_MUSIC_PLAYLIST"]
    assert BROADCAST_FIELD_LABELS["DISCORD_RACE_REPORT_ENABLED"] == "Discord Race Report"
    assert BROADCAST_FIELD_LABELS["DISCORD_RACE_REPORT_WEBHOOK_URL"] == "Race Report Webhook URL"
    assert BROADCAST_FIELD_LABELS["DISCORD_RACE_REPORT_USE_OPENAI"] == "Use OpenAI Race Recap"
    assert "webhook" in BROADCAST_FIELD_HELP["DISCORD_RACE_REPORT_WEBHOOK_URL"].lower()
    assert "OPENAI_API_KEY" in IMPORTANT_SETUP_FIELDS
    assert "STUDIO_VOLUME" not in BROADCAST_FIELD_LABELS
    assert BROADCAST_FIELD_SECTIONS["USE_OPENAI"] == "AI Commentary"
    assert BROADCAST_FIELD_SECTIONS["OVERLAY_EVENT_TITLE"] == "Event Sponsors / Overlay Links"
    assert "OVERLAY_HOST" not in BROADCAST_FIELD_SECTIONS
    assert BROADCAST_FIELD_SECTIONS["PRACTICE_MUSIC_PLAYLIST"] == "Practice / Qualifying / Caution Music"
    assert BROADCAST_FIELD_SECTIONS["RACE_ADMIN_MODE"] == "Race Control"
    assert BROADCAST_FIELD_SECTIONS["DISCORD_RACE_REPORT_ENABLED"] == "Discord Race Report"
    saved_keys = [key for key, _default in LAUNCHER_FIELDS]
    assert "RACE_SPONSOR_5_VIDEO" in saved_keys
    assert "CRANK_IT_UP_SPONSOR_NAME" in saved_keys
    assert "USE_SIM_RACING_APPS" in saved_keys
    assert "LEAD_BROADCASTER_NAME" in saved_keys
    assert "COLOR_BROADCASTER_NAME" in saved_keys
    assert "PIT_BROADCASTER_NAME" in saved_keys
    assert "QUALIFYING_MUSIC_PLAYLIST" in saved_keys
    assert "USE_NATIONAL_ANTHEM" not in saved_keys
    assert "NATIONAL_ANTHEM_GRAPHICS" not in saved_keys
    assert "CAUTION_PRESENTATION_GRAPHICS" not in saved_keys
    assert "DISCORD_BOT_ENABLED" not in saved_keys
    assert "DISCORD_RACE_REPORT_RESULTS_URL" not in saved_keys
    assert "OVERLAY_BRAND_GRAPHICS" not in saved_keys
    assert "DISCORD_RACE_REPORT_CHAMPIONSHIP_URL" not in saved_keys
    assert "REMOTE_PRODUCER_ENABLED" not in saved_keys


def test_studio_profile_buttons_use_clear_create_delete_language():
    source = Path("studio_launcher.py").read_text(encoding="utf-8")

    assert 'text="New Profile Name"' in source
    assert 'text="Create Profile"' in source
    assert 'text="Load"' in source
    assert 'text="Delete"' in source
    assert 'text="Save Settings"' in source
    assert "Save Settings updates both the active settings file and that selected profile" in source
    assert "New / Save As" not in source
    assert "Save Profile Changes" not in source


def test_start_broadcast_auto_opens_producer_assist():
    source = Path("studio_launcher.py").read_text(encoding="utf-8")

    assert "root.after(1500, open_producer_assist_after_start)" in source
    assert "Producer Assist opens automatically after Start Broadcast" in source
    assert 'text="Producer Assist / Remote Admin Link"' in source
    assert 'text="Copy Admin Link"' in source
    assert "This is the same Producer Assist control-room page" in source
    assert "trusted admins on your Tailscale network" in source


def test_studio_mousewheel_scrolls_from_full_window():
    source = Path("studio_launcher.py").read_text(encoding="utf-8")

    assert 'root.bind_all("<MouseWheel>", on_mousewheel)' in source
    assert 'root.bind_all("<Button-4>", on_linux_scroll_up)' in source
    assert 'root.bind_all("<Button-5>", on_linux_scroll_down)' in source
    assert 'event.widget.winfo_toplevel() != root' in source
    assert 'content.bind("<Enter>", enable_mousewheel)' not in source


def test_studio_comboboxes_ignore_mousewheel_selection_changes():
    source = Path("studio_launcher.py").read_text(encoding="utf-8")

    assert "def disable_combobox_mousewheel(widget):" in source
    assert 'widget.bind("<MouseWheel>", lambda _event: "break")' in source
    assert 'widget.bind("<Button-4>", lambda _event: "break")' in source
    assert 'widget.bind("<Button-5>", lambda _event: "break")' in source
    assert "disable_combobox_mousewheel(profile_combo)" in source
    assert "disable_combobox_mousewheel(entry_widget)" in source


def test_launcher_version_comparison_helpers():
    assert version_parts("v1.2.3") == (1, 2, 3)
    assert version_parts("0.19.0-beta") == (0, 19, 0)
    assert is_newer_version("0.19.0", "0.18.0")
    assert not is_newer_version("0.18.0", "0.18.0")
    assert not is_newer_version("0.17.9", "0.18.0")


def test_update_status_from_release_detects_available_update():
    state, message, url = update_status_from_release(
        {
            "tag_name": "v0.19.0",
            "html_url": "https://example.com/release",
        },
        current_version="0.18.0",
    )

    assert state == "available"
    assert "0.19.0" in message
    assert url == "https://example.com/release"


def test_update_status_from_release_detects_current_version():
    state, message, _url = update_status_from_release(
        {
            "tag_name": "v0.18.0",
            "html_url": "https://example.com/release",
        },
        current_version="0.18.0",
    )

    assert state == "current"
    assert "up to date" in message


def test_launcher_defaults_include_split_league_stats_csvs():
    defaults = launcher_defaults({})

    assert defaults["LEAGUE_DRIVERS_CSV"] == "league/drivers.csv"
    assert defaults["LEAGUE_SEASON_STATS_CSV"] == "league/season.csv"
    assert defaults["LEAGUE_CAREER_STATS_CSV"] == "league/career.csv"
    assert defaults["STAGE_END_LAPS"] == ""
    assert defaults["LEAGUE_FUEL_PERCENT"] == ""
    assert defaults["LEAGUE_ENGINE_POWER_PERCENT"] == ""
    assert defaults["LEAGUE_TIRE_SETS"] == ""
    assert defaults["DISCORD_RACE_REPORT_ENABLED"] == "false"
    assert defaults["DISCORD_RACE_REPORT_WEBHOOK_URL"] == ""
    assert defaults["DISCORD_RACE_REPORT_USE_OPENAI"] == "true"
    assert defaults["LEAD_BROADCASTER_NAME"] == "Mike"
    assert defaults["COLOR_BROADCASTER_NAME"] == "Jeff"
    assert defaults["PIT_BROADCASTER_NAME"] == "Sarah"
    assert defaults["OVERLAY_LEADERBOARD_STYLE"] == "side"
    assert defaults["RACE_SPONSOR_2_NAME"] == ""
    assert defaults["RACE_SPONSOR_3_NAME"] == ""
    assert defaults["RACE_SPONSOR_1_READ"] == ""
    assert "/assets/rgc_motorsports.png" in defaults["OVERLAY_BRAND_GRAPHICS"]
    assert defaults["PRACTICE_MUSIC_PLAYLIST"] == ""
    assert defaults["QUALIFYING_MUSIC_PLAYLIST"] == ""
    assert defaults["STUDIO_VOLUME"] == "65"
    assert defaults["CAUTION_REPLAY_AUDIO"] == ""
    assert defaults["NATIONAL_ANTHEM_AUDIO"] == ""
    assert defaults["NATIONAL_ANTHEM_GRAPHICS"] == ""
    assert defaults["CAUTION_PRESENTATION_GRAPHICS"] == ""
    assert defaults["POST_RACE_INTERVIEWS_ENABLED"] == "false"
    assert defaults["USE_SIM_RACING_APPS"] == "true"
    assert defaults["RACE_ADMIN_MODE"] == "false"
    assert defaults["RACE_ADMIN_SEND_MODE"] == "clipboard"
    assert defaults["DISCORD_BOT_ENABLED"] == "false"
    assert defaults["DISCORD_BOT_TOKEN"] == ""
    assert defaults["DISCORD_GUILD_ID"] == ""
    assert defaults["DISCORD_BOOTH_CHANNEL_ID"] == ""
    assert defaults["DISCORD_WAITING_CHANNEL_ID"] == ""
    assert defaults["DISCORD_INTERVIEW_CHANNEL_ID"] == ""
    assert defaults["SIMRACERHUB_SOURCE"] == "https://simracerhub.com"
    assert defaults["SIMRACERHUB_LEAGUE_ID"] == ""
    assert defaults["SIMRACERHUB_SERIES_ID"] == ""
    assert defaults["SIMRACERHUB_SEASON_ID"] == ""
    assert defaults["SIMRACERHUB_RACE_SCHEDULE_CSV"] == "league/race_schedule.csv"


def test_launcher_defaults_migrate_old_anthem_audio_to_qualifying_music():
    defaults = launcher_defaults({"NATIONAL_ANTHEM_AUDIO": "D:/Music/old_anthem.mp3"})

    assert defaults["QUALIFYING_MUSIC_PLAYLIST"] == "D:/Music/old_anthem.mp3"


def test_race_admin_send_mode_includes_open_chat_option():
    source = Path("studio_launcher.py").read_text(encoding="utf-8")

    assert '("clipboard", "open_chat", "ui_paste")' in source
    assert "opens iRacing text chat for quick Ctrl+V/Enter" in source


def test_remote_producer_link_requires_enabled_relay_and_session():
    assert remote_producer_link(launcher_defaults({})) == ""
    assert (
        remote_producer_link(
            launcher_defaults(
                {
                    "REMOTE_PRODUCER_ENABLED": "true",
                    "REMOTE_PRODUCER_RELAY_URL": "https://producer.rgc-ai.com/",
                    "REMOTE_PRODUCER_SESSION_CODE": "WFO12345",
                    "REMOTE_PRODUCER_PIN": "2468",
                }
            )
        )
        == "https://producer.rgc-ai.com/producer/WFO12345?pin=2468"
    )


def test_generate_remote_session_code_is_admin_friendly():
    code = generate_remote_session_code()

    assert len(code) == 8
    assert code.isalnum()
    assert code == code.upper()


def test_launcher_health_reports_missing_ai_keys():
    values = launcher_defaults({})

    rows = build_health_status(values, root=Path("C:/RGC"), broadcast_running=False)
    row_map = {name: (state, detail, level) for name, state, detail, level in rows}

    assert row_map["OpenAI"][0] == "Needs key"
    assert row_map["ElevenLabs"][0] == "Needs setup"
    assert row_map["Discord Race Report"][0] == "Off"
    assert row_map["Remote Producer Assist"][0] == "Local only"
    assert row_map["Broadcast"][0] == "Stopped"


def test_launcher_health_reports_discord_race_report_setup():
    values = launcher_defaults({"DISCORD_RACE_REPORT_ENABLED": "true"})

    rows = build_health_status(values, root=Path("C:/RGC"), broadcast_running=False)
    row_map = {name: (state, detail, level) for name, state, detail, level in rows}

    assert row_map["Discord Race Report"][0] == "Needs webhook"

    values["DISCORD_RACE_REPORT_WEBHOOK_URL"] = "https://discord.example/webhook"
    rows = build_health_status(values, root=Path("C:/RGC"), broadcast_running=False)
    row_map = {name: (state, detail, level) for name, state, detail, level in rows}

    assert row_map["Discord Race Report"][0] == "Ready"
    assert "Season ID" in row_map["Discord Race Report"][1]


def test_launcher_health_reports_tailscale_helper_access(monkeypatch):
    import studio_launcher

    monkeypatch.setattr(studio_launcher, "best_remote_helper_ip", lambda: "100.90.80.70")
    values = launcher_defaults({"OVERLAY_HOST": "0.0.0.0"})

    rows = build_health_status(values, root=Path("C:/RGC"), broadcast_running=False)
    row_map = {name: (state, detail, level) for name, state, detail, level in rows}

    assert row_map["Remote Producer Assist"][0] == "Shared"
    assert "http://100.90.80.70:8765/producer" in row_map["Remote Producer Assist"][1]


def test_launcher_health_reports_sim_racing_apps_optional_when_not_running(monkeypatch):
    import studio_launcher

    monkeypatch.setattr(studio_launcher, "sim_racing_apps_is_running", lambda: False)
    values = launcher_defaults({})

    rows = build_health_status(values, root=Path("C:/RGC"), broadcast_running=False)
    row_map = {name: (state, detail, level) for name, state, detail, level in rows}

    assert row_map["SIMRacingApps"][0] == "Not running"
    assert "Start SIMRacingAppsServer" in row_map["SIMRacingApps"][1]
    assert row_map["SIMRacingApps"][2] == "warn"


def test_launcher_health_reports_sim_racing_apps_disabled(monkeypatch):
    import studio_launcher

    monkeypatch.setattr(studio_launcher, "sim_racing_apps_is_running", lambda: True)
    values = launcher_defaults({"USE_SIM_RACING_APPS": "false"})

    rows = build_health_status(values, root=Path("C:/RGC"), broadcast_running=False)
    row_map = {name: (state, detail, level) for name, state, detail, level in rows}

    assert row_map["SIMRacingApps"][0] == "Disabled"
    assert "fallback graphics" in row_map["SIMRacingApps"][1]
    assert row_map["SIMRacingApps"][2] == "off"


def test_launcher_health_reports_sim_racing_apps_running(monkeypatch):
    import studio_launcher

    monkeypatch.setattr(studio_launcher, "sim_racing_apps_is_running", lambda: True)
    monkeypatch.setattr(studio_launcher, "trading_paints_is_running", lambda: True)
    values = launcher_defaults({})

    rows = build_health_status(values, root=Path("C:/RGC"), broadcast_running=False)
    row_map = {name: (state, detail, level) for name, state, detail, level in rows}

    assert row_map["SIMRacingApps"][0] == "Running"
    assert "Live car renders" in row_map["SIMRacingApps"][1]
    assert row_map["SIMRacingApps"][2] == "ok"
    assert row_map["Trading Paints"][0] == "Running"
    assert "accurate car graphics" in row_map["Trading Paints"][1]
    assert row_map["Trading Paints"][2] == "ok"


def test_launcher_health_reports_trading_paints_not_detected(monkeypatch):
    import studio_launcher

    monkeypatch.setattr(studio_launcher, "sim_racing_apps_is_running", lambda: False)
    monkeypatch.setattr(studio_launcher, "trading_paints_is_running", lambda: False)
    values = launcher_defaults({})

    rows = build_health_status(values, root=Path("C:/RGC"), broadcast_running=False)
    row_map = {name: (state, detail, level) for name, state, detail, level in rows}

    assert row_map["Trading Paints"][0] == "Not detected"
    assert "Start Trading Paints" in row_map["Trading Paints"][1]
    assert row_map["Trading Paints"][2] == "warn"


def test_trading_paints_process_detection_accepts_spaced_or_compact_names():
    import studio_launcher

    assert studio_launcher.trading_paints_is_running(
        '"TradingPaints.exe","1234","Console"'
    )
    assert studio_launcher.trading_paints_is_running(
        "Trading Paints Helper\nOtherProcess"
    )
    assert not studio_launcher.trading_paints_is_running("iRacingSim64DX11.exe")


def test_first_time_setup_checklist_flags_missing_profile_and_keys(tmp_path):
    values = launcher_defaults({})

    rows = build_first_time_setup_checklist(
        values,
        root=tmp_path,
        broadcast_running=False,
        profile_names=[],
    )
    row_map = {name: (state, detail, level) for name, state, detail, level in rows}

    assert row_map["OpenAI"][0] == "Needs key"
    assert row_map["ElevenLabs"][0] == "Needs setup"
    assert row_map["Discord Race Report"][0] == "Off"
    assert row_map["Profiles"][0] == "Recommended"
    assert row_map["Broadcast process"][0] == "Stopped"


def test_first_time_setup_checklist_reports_ready_release_basics(tmp_path):
    values = launcher_defaults(
        {
            "OPENAI_API_KEY": "sk-test",
            "ELEVENLABS_API_KEY": "eleven-test",
            "LEAD_VOICE_ID": "lead",
            "COLOR_VOICE_ID": "jeff",
            "PIT_VOICE_ID": "sarah",
            "OVERLAY_EVENT_TITLE": "WFO Truck Series",
            "OVERLAY_RACE_SPONSOR": "RGC Motorsports",
            "RACE_SPONSOR_1_NAME": "RGC Motorsports",
            "RACE_SPONSOR_1_LOGO": "/assets/rgc_motorsports.png",
        }
    )

    rows = build_first_time_setup_checklist(
        values,
        root=tmp_path,
        broadcast_running=False,
        profile_names=["League Race"],
    )
    row_map = {name: (state, detail, level) for name, state, detail, level in rows}

    assert row_map["OpenAI"][0] == "Ready"
    assert row_map["ElevenLabs"][0] == "Ready"
    assert row_map["Overlay branding"][0] == "Ready"
    assert row_map["Profiles"][0] == "Ready"
    assert row_map["Producer Assist link"][1] == DEFAULT_PRODUCER_URL


def test_launcher_health_reports_disabled_ai_as_off():
    values = launcher_defaults({"USE_OPENAI": "false", "USE_ELEVENLABS": "false"})

    rows = build_health_status(values, root=Path("C:/RGC"), broadcast_running=True)
    row_map = {name: (state, detail, level) for name, state, detail, level in rows}

    assert row_map["OpenAI"][0] == "Off"
    assert row_map["ElevenLabs"][0] == "Off"
    assert row_map["Producer Assist"][1] == DEFAULT_PRODUCER_URL
    assert row_map["Broadcast"][0] == "Running"


def test_launcher_health_reports_league_files_ready(tmp_path):
    league_dir = tmp_path / "league"
    league_dir.mkdir()
    (league_dir / "drivers.csv").write_text("name,car_number\n", encoding="utf-8")
    (league_dir / "season.csv").write_text("name,starts\n", encoding="utf-8")
    (league_dir / "career.csv").write_text("name,starts\n", encoding="utf-8")
    values = launcher_defaults(
        {
            "USE_OPENAI": "false",
            "USE_ELEVENLABS": "false",
            "USE_LEAGUE_DRIVER_NOTES": "true",
            "LEAGUE_DRIVERS_CSV": "league/drivers.csv",
            "LEAGUE_SEASON_STATS_CSV": "league/season.csv",
            "LEAGUE_CAREER_STATS_CSV": "league/career.csv",
        }
    )

    rows = build_health_status(values, root=tmp_path, broadcast_running=False)
    row_map = {name: (state, detail, level) for name, state, detail, level in rows}

    assert row_map["League Profiles"][0] == "Ready"


def test_launcher_migrates_old_practice_music_volume_to_studio_volume():
    defaults = launcher_defaults({"PRACTICE_MUSIC_VOLUME": "42"})

    assert defaults["STUDIO_VOLUME"] == "42"


def test_launcher_migrates_old_sponsor_fields_to_new_slots():
    defaults = launcher_defaults(
        {
            "OVERLAY_RACE_SPONSOR": "RGC Motorsports",
            "SPONSOR_READ_NAME_2": "Autism Awareness",
            "SPONSOR_READ_CAUSE": "Autism Awareness",
            "SPONSOR_READ_MESSAGE": "Presented by {sponsor}.",
        }
    )

    assert defaults["RACE_SPONSOR_1_NAME"] == "RGC Motorsports"
    assert defaults["RACE_SPONSOR_2_NAME"] == "Autism Awareness"
    assert defaults["SPONSOR_READ_CAUSE_NAME"] == "Autism Awareness"
    assert defaults["RACE_SPONSOR_1_READ"] == "Presented by {sponsor}."
    assert defaults["CRANK_IT_UP_SPONSOR_NAME"] == "RGC Motorsports"


def test_launcher_saves_known_settings(tmp_path):
    env_path = tmp_path / ".env"

    save_env_file(
        {
            "USE_OPENAI": "false",
            "OVERLAY_EVENT_TITLE": "League Race",
            "LEAGUE_SEASON_STATS_CSV": "league/season.csv",
            "RACE_SPONSOR_2_NAME": "Second Sponsor",
            "RACE_SPONSOR_1_READ": "Presented by {sponsor}.",
            "CRANK_IT_UP_SPONSOR_NAME": "Second Sponsor",
        },
        env_path,
    )

    saved = env_path.read_text(encoding="utf-8")
    assert "USE_OPENAI=false" in saved
    assert "OVERLAY_EVENT_TITLE=League Race" in saved
    assert "LEAGUE_SEASON_STATS_CSV=league/season.csv" in saved
    assert "RACE_SPONSOR_2_NAME=Second Sponsor" in saved
    assert "RACE_SPONSOR_1_READ=Presented by {sponsor}." in saved
    assert "CRANK_IT_UP_SPONSOR_NAME=Second Sponsor" in saved


def test_launcher_saves_sim_racer_hub_settings(tmp_path):
    env_path = tmp_path / ".env"

    save_env_file(
        {
            "SIMRACERHUB_SOURCE": "https://simracerhub.com",
            "SIMRACERHUB_LEAGUE_ID": "1598",
            "SIMRACERHUB_SERIES_ID": "3872",
            "SIMRACERHUB_SEASON_ID": "29247",
            "SIMRACERHUB_TRACK_NAME": "Nashville",
            "SIMRACERHUB_CAREER_MODE": "true",
        },
        env_path,
    )
    loaded = launcher_defaults(load_env_file(env_path))

    assert loaded["SIMRACERHUB_LEAGUE_ID"] == "1598"
    assert loaded["SIMRACERHUB_SERIES_ID"] == "3872"
    assert loaded["SIMRACERHUB_SEASON_ID"] == "29247"
    assert loaded["SIMRACERHUB_TRACK_NAME"] == "Nashville"
    assert loaded["SIMRACERHUB_CAREER_MODE"] == "true"


def test_track_history_filter_is_hidden_from_visible_studio_setup():
    source = Path("studio_launcher.py").read_text(encoding="utf-8")

    assert "Track History Filter" not in source
    assert 'track_name=data.get("SIMRACERHUB_TRACK_NAME", "")' in source


def test_launcher_sanitizes_profile_names():
    assert sanitize_profile_name(" WFO / Truck: League! ") == "WFO Truck League"
    assert sanitize_profile_name("") == ""


def test_launcher_builds_profile_specific_league_csv_paths():
    assert league_folder_slug("DSR Electric Series") == "DSR_Electric_Series"
    assert league_csv_paths_for_profile("DSR Electric Series") == (
        "league/DSR_Electric_Series/drivers.csv",
        "league/DSR_Electric_Series/season.csv",
        "league/DSR_Electric_Series/career.csv",
        "league/DSR_Electric_Series/race_schedule.csv",
    )
    assert league_csv_paths_for_profile("") == (
        "league/drivers.csv",
        "league/season.csv",
        "league/career.csv",
        "league/race_schedule.csv",
    )


def test_driver_roster_import_target_prefers_visible_driver_csv():
    target = driver_roster_import_target(
        "league/DSR_Electric_Series/drivers.csv",
        "league/WFO_Truck_Series/drivers.csv",
    )

    assert target == "league/DSR_Electric_Series/drivers.csv"


def test_driver_roster_import_target_falls_back_to_import_output():
    assert (
        driver_roster_import_target("", "league/WFO_Truck_Series/drivers.csv")
        == "league/WFO_Truck_Series/drivers.csv"
    )
    assert driver_roster_import_target("", "") == "league/drivers.csv"


def test_launcher_saves_lists_and_loads_profiles(tmp_path):
    values = launcher_defaults(
        {
            "USE_OPENAI": "false",
            "OVERLAY_EVENT_TITLE": "WFO Truck Night",
        }
    )

    saved_path = save_profile("WFO Truck", values, profile_dir=tmp_path)
    profiles = list_profiles(profile_dir=tmp_path)
    loaded = load_profile("WFO Truck", profile_dir=tmp_path)

    assert saved_path == tmp_path / "WFO_Truck.env"
    assert profiles == ["WFO Truck"]
    assert loaded["USE_OPENAI"] == "false"
    assert loaded["OVERLAY_EVENT_TITLE"] == "WFO Truck Night"


def test_launcher_can_delete_saved_profile(tmp_path):
    values = launcher_defaults({"OVERLAY_EVENT_TITLE": "Delete Me"})
    saved_path = save_profile("Delete Me", values, profile_dir=tmp_path)

    deleted_path = delete_profile("Delete Me", profile_dir=tmp_path)

    assert deleted_path == saved_path
    assert list_profiles(profile_dir=tmp_path) == []


def test_launcher_profile_path_rejects_blank_name(tmp_path):
    try:
        profile_path("", profile_dir=tmp_path)
    except ValueError as error:
        assert "required" in str(error)
    else:
        raise AssertionError("Expected ValueError for blank profile name")


def test_launcher_saves_music_settings(tmp_path):
    env_path = tmp_path / ".env"

    save_env_file(
        {
            "STUDIO_VOLUME": "45",
            "PRACTICE_MUSIC_PLAYLIST": "D:/Music/practice1.mp3;D:/Music/practice2.mp3",
            "QUALIFYING_MUSIC_PLAYLIST": "D:/Music/qualifying1.mp3;D:/Music/qualifying2.mp3",
            "CAUTION_REPLAY_AUDIO": "D:/Music/caution.mp3",
            "NATIONAL_ANTHEM_AUDIO": "D:/Music/qualifying1.mp3;D:/Music/qualifying2.mp3",
        },
        env_path,
    )

    saved = env_path.read_text(encoding="utf-8")
    assert "STUDIO_VOLUME=45" in saved
    assert "PRACTICE_MUSIC_PLAYLIST=D:/Music/practice1.mp3;D:/Music/practice2.mp3" in saved
    assert "QUALIFYING_MUSIC_PLAYLIST=D:/Music/qualifying1.mp3;D:/Music/qualifying2.mp3" in saved
    assert "PRACTICE_MUSIC_VOLUME" not in saved
    assert "CAUTION_REPLAY_AUDIO=D:/Music/caution.mp3" in saved
    assert "CAUTION_PRESENTATION_GRAPHICS" in saved
    assert "NATIONAL_ANTHEM_AUDIO=D:/Music/qualifying1.mp3;D:/Music/qualifying2.mp3" in saved


def test_launcher_formats_practice_music_playlist():
    playlist = format_playlist_paths(["D:/Music/one.mp3", "D:/Music/two.mp3"])

    assert playlist.split(";") == [str(Path("D:/Music/one.mp3")), str(Path("D:/Music/two.mp3"))]


def test_launcher_sets_qualifying_music_when_audio_is_selected():
    values = apply_audio_file_selection(
        {},
        "QUALIFYING_MUSIC_PLAYLIST",
        "D:/Music/qualifying.mp3",
    )

    assert values["QUALIFYING_MUSIC_PLAYLIST"] == str(Path("D:/Music/qualifying.mp3"))


def test_launcher_can_select_multiple_qualifying_music_files():
    values = apply_audio_file_selection(
        {},
        "QUALIFYING_MUSIC_PLAYLIST",
        ["D:/Music/qualifying_one.mp3", "D:/Music/qualifying_two.mp3"],
    )

    assert values["QUALIFYING_MUSIC_PLAYLIST"].split(";") == [
        str(Path("D:/Music/qualifying_one.mp3")),
        str(Path("D:/Music/qualifying_two.mp3")),
    ]


def test_launcher_sanitizes_overlay_asset_names():
    assert sanitize_asset_name("D:/Editor/decals/RGC Motorsports Logo.PNG") == "rgc_motorsports_logo.png"
    assert sanitize_video_asset_name("D:/Commercials/RGC Motorsports Spot.MP4") == "rgc_motorsports_spot.mp4"


def test_launcher_installs_overlay_brand_graphics(tmp_path):
    source = tmp_path / "RGC Motorsports Logo.PNG"
    source.write_bytes(b"fake image")
    static_dir = tmp_path / "static"

    assets = install_overlay_brand_graphics([source], static_dir=static_dir)

    assert assets == ["/assets/rgc_motorsports_logo.png"]
    assert (static_dir / "rgc_motorsports_logo.png").read_bytes() == b"fake image"


def test_launcher_installs_overlay_commercial_video(tmp_path):
    source = tmp_path / "RGC Motorsports Spot.MP4"
    source.write_bytes(b"fake video")
    static_dir = tmp_path / "static"

    asset = install_overlay_commercial_video(source, static_dir=static_dir)

    assert asset == "/assets/rgc_motorsports_spot.mp4"
    assert (static_dir / "rgc_motorsports_spot.mp4").read_bytes() == b"fake video"


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
        output="league/season.csv",
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


def test_launcher_builds_sim_racer_hub_schedule_command():
    command = sim_racer_hub_import_command(
        "https://simracerhub.com",
        league_id="1598",
        series_id="3872",
        season_id="29247",
        first_schedule_id="356761",
        schedule_output="league/race_schedule.csv",
        schedule_only=True,
    )

    assert "--schedule-only" in command
    assert ["--first-schedule-id", "356761"] == command[
        command.index("--first-schedule-id") : command.index("--first-schedule-id") + 2
    ]
    assert ["--schedule-output", "league/race_schedule.csv"] == command[
        command.index("--schedule-output") : command.index("--schedule-output") + 2
    ]
    assert ["--season-id", "29247"] == command[command.index("--season-id") : command.index("--season-id") + 2]


def test_studio_driver_profile_rows_round_trip(tmp_path):
    from studio_launcher import load_driver_profile_rows, save_driver_profile_rows

    path = tmp_path / "drivers.csv"
    save_driver_profile_rows(
        path,
        [
            {
                "name": "T.J. Lee",
                "car_number": "34",
                "hometown": "Richmond",
                "state": "VA",
                "country": "USA",
                "driving_style": "patient",
                "sponsor": "RGC Motorsports",
                "about": "Strong on long runs",
                "car_image": "cars/tj.png",
            }
        ],
    )

    rows = load_driver_profile_rows(path)

    assert rows == [
        {
            "name": "T.J. Lee",
            "car_number": "34",
            "hometown": "Richmond",
            "state": "VA",
            "country": "USA",
            "driving_style": "patient",
            "sponsor": "RGC Motorsports",
            "about": "Strong on long runs",
            "car_image": "cars/tj.png",
        }
    ]


def test_studio_driver_profile_rows_migrate_legacy_notes_to_about(tmp_path):
    from studio_launcher import load_driver_profile_rows

    path = tmp_path / "drivers.csv"
    path.write_text(
        "name,car_number,hometown,state,country,driving_style,sponsor,notes,car_image\n"
        "T.J. Lee,34,Richmond,VA,USA,patient,RGC Motorsports,Strong on long runs,cars/tj.png\n",
        encoding="utf-8",
    )

    rows = load_driver_profile_rows(path)

    assert rows[0]["about"] == "Strong on long runs"
    assert "notes" not in rows[0]


def test_studio_can_create_empty_driver_profile_csv(tmp_path):
    path = tmp_path / "league" / "DSR_Electric_Series" / "drivers.csv"

    ensure_empty_driver_profile_csv(path)

    assert path.exists()
    assert path.read_text(encoding="utf-8").splitlines()[0].endswith(",car_image")
    assert ",about," in path.read_text(encoding="utf-8").splitlines()[0]


def test_studio_can_create_empty_race_schedule_csv(tmp_path):
    path = tmp_path / "league" / "DSR_Electric_Series" / "race_schedule.csv"

    ensure_empty_race_schedule_csv(path)

    assert path.exists()
    assert path.read_text(encoding="utf-8").splitlines()[0] == "track_name,schedule_id,notes"


def test_tester_zip_excludes_private_local_files():
    assert should_include("README.md")
    assert should_include("install_studio.bat")
    assert should_include("assets/rgc_ai_broadcast_studio.ico")
    assert should_include("production/static/rgc_motorsports.png")

    assert not should_include(".env")
    assert not should_include("league/drivers.csv")
    assert not should_include("league/race_schedule.csv")
    assert not should_include("profiles/WFO_Truck.env")
    assert not should_include(".venv/Scripts/python.exe")
    assert not should_include("recordings/test.mp4")
    assert not should_include("broadcast/__pycache__/engine.pyc")
    assert not should_include("local_song.mp3")


def test_windows_installer_helpers_build_expected_command(tmp_path):
    command = build_inno_command(
        tmp_path / "ISCC.exe",
        source_dir=tmp_path / "source",
        output_dir=tmp_path / "dist",
        version="1.2.3",
        script=tmp_path / "installer.iss",
    )

    assert str(tmp_path / "ISCC.exe") == command[0]
    assert f"/DSourceDir={tmp_path / 'source'}" in command
    assert f"/DOutputDir={tmp_path / 'dist'}" in command
    assert "/DAppVersion=1.2.3" in command
    assert str(tmp_path / "installer.iss") == command[-1]


def test_windows_installer_excludes_development_files():
    assert should_include_for_installer("README.md")
    assert should_include_for_installer("production/overlay.py")
    assert should_include_for_installer("tools/sim_racer_hub_import.py")

    assert not should_include_for_installer("tests/test_overlay.py")
    assert not should_include_for_installer(".github/workflows/tests.yml")
    assert not should_include_for_installer("league/drivers.csv")
    assert not should_include_for_installer("IDEAS.md")
    assert not should_include_for_installer("ROADMAP.md")
    assert not should_include_for_installer("docs/REMOTE_PRODUCER_RELAY.md")


def test_project_version_reads_pyproject():
    assert project_version()


def test_inno_setup_searches_version_7_and_6_paths():
    paths = [str(path) for path in DEFAULT_INNO_PATHS]

    assert any("Inno Setup 7" in path for path in paths)
    assert any("Inno Setup 6" in path for path in paths)


def test_launcher_sets_branded_window_icon():
    source = Path("studio_launcher.py").read_text(encoding="utf-8")

    assert "WINDOWS_APP_USER_MODEL_ID" in source
    assert "set_windows_app_user_model_id()" in source
    assert "set_window_icon(root)" in source
    assert "rgc_ai_broadcast_studio.ico" in source
