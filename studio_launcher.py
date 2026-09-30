from __future__ import annotations

import json
import os
import re
import secrets
import shutil
import socket
import subprocess
import sys
import csv
import urllib.error
from urllib.parse import quote
import urllib.request
import webbrowser
from pathlib import Path
from tkinter import messagebox

from production.league_manager import (
    LeagueProfile,
    RaceResult,
    ScheduleEvent,
    ScoringRule,
    ScoringSystem,
    active_iracing_league_snapshot,
    active_iracing_race_result,
    calculate_standings,
    default_scoring_system,
    load_league_profile,
    load_race_results,
    load_schedule,
    load_scoring_system,
    save_league_profile,
    save_race_results,
    save_schedule,
    save_scoring_system,
    score_race_result,
)
from production.wordpress_publisher import (
    WordPressPublishSettings,
    build_wordpress_payload,
    load_wordpress_settings,
    publish_league_to_wordpress,
    save_wordpress_settings,
)

try:
    import tomllib
except ModuleNotFoundError:  # pragma: no cover - Python < 3.11 fallback
    import tomli as tomllib


ROOT = Path(__file__).resolve().parent
ENV_PATH = ROOT / ".env"
STATIC_ASSET_DIR = ROOT / "production" / "static"
RUNTIME_DIR = ROOT / ".runtime"
BROADCAST_PID_PATH = RUNTIME_DIR / "broadcast.pid"
BROADCAST_LOG_PATH = ROOT / "logs" / "broadcast_latest.log"
PROFILE_DIR = ROOT / "profiles"
BROADCAST_PROCESS = None
BROADCAST_LOG_FILE = None
RGC_DISCORD_URL = "https://discord.gg/Axwwa8CUqt"
RGC_WEBSITE_URL = "https://www.realisticgamingcrew.com"
TAILSCALE_WINDOWS_DOWNLOAD_URL = "https://tailscale.com/download/windows"
SIM_RACING_APPS_HOME_URL = "https://simracingapps.com/"
SIM_RACING_APPS_PATCH_URL = (
    "https://github.com/ZoneXV/SIMRacingAppsServer/releases/tag/"
    "v1.22-paceCar-pitspeed-fix"
)
SIM_RACING_APPS_HEALTH_URL = "http://127.0.0.1/SIMRacingApps/Data/Session/Cars"
DEFAULT_OVERLAY_URL = "http://127.0.0.1:8765/overlay"
DEFAULT_PRODUCER_URL = "http://127.0.0.1:8765/producer"
CLOSE_RUNNING_BROADCAST_TITLE = "Broadcast process detected"
CLOSE_RUNNING_BROADCAST_MESSAGE = (
    "RGC AI Broadcast Studio still sees a broadcast-related process that was started from this launcher.\n\n"
    "If you are done broadcasting, choose Yes to stop it before closing. "
    "If you are only closing the setup window and want the broadcast/Producer Assist to keep running, choose No."
)
WINDOWS_APP_USER_MODEL_ID = "RGC.AIBroadcastStudio.Studio"
WINDOW_ICON_PATH = ROOT / "assets" / "rgc_ai_broadcast_studio.ico"
WINDOW_ICON_IMAGE_PATH = ROOT / "assets" / "rgc_ai_broadcast_studio_icon.png"
GITHUB_RELEASES_URL = "https://github.com/HonorRGC/RGC-AI-Broadcast-Studio/releases"
GITHUB_LATEST_RELEASE_API = (
    "https://api.github.com/repos/HonorRGC/RGC-AI-Broadcast-Studio/releases/latest"
)

DARK_BG = "#071018"
PANEL_BG = "#101a24"
FIELD_BG = "#172331"
TEXT_FG = "#f4f7fb"
MUTED_FG = "#9fb0c2"
ACCENT = "#8b1e2d"
ACCENT_HOVER = "#a72a3a"
GREEN = "#158a4d"
STOP_RED = "#b73535"

OPENAI_MODEL_CHOICES = (
    "gpt-5.6-terra",
    "gpt-5.6-luna",
    "gpt-5.6-sol",
    "gpt-6-astra",
    "gpt-5.5",
    "gpt-5.1",
    "gpt-5-mini",
    "gpt-4.1",
)

DRIVER_PROFILE_FIELDS = [
    "name",
    "car_number",
    "hometown",
    "state",
    "country",
    "driving_style",
    "sponsor",
    "about",
    "car_image",
]

RACE_SCHEDULE_FIELDS = [
    "track_name",
    "schedule_id",
    "notes",
]

LAUNCHER_FIELDS = [
    ("USE_OPENAI", "true"),
    ("OPENAI_API_KEY", ""),
    ("OPENAI_MODEL", "gpt-5.6-terra"),
    ("USE_ELEVENLABS", "true"),
    ("ELEVENLABS_API_KEY", ""),
    ("LEAD_BROADCASTER_NAME", "Mike"),
    ("COLOR_BROADCASTER_NAME", "Jeff"),
    ("PIT_BROADCASTER_NAME", "Sarah"),
    ("LEAD_VOICE_ID", ""),
    ("COLOR_VOICE_ID", ""),
    ("PIT_VOICE_ID", ""),
    ("OVERLAY_EVENT_TITLE", "RGC AI Broadcast"),
    ("OVERLAY_SERIES_NAME", ""),
    ("OVERLAY_SERIES_LOGO", ""),
    ("OVERLAY_LEADERBOARD_STYLE", "side"),
    ("USE_SIM_RACING_APPS", "true"),
    ("USE_SPONSOR_READS", "true"),
    ("SPONSOR_READ_CAUSE_NAME", ""),
    ("SPONSOR_READ_CAUSE_LOGO", ""),
    ("SPONSOR_READ_CAUSE_READ", ""),
    ("RACE_SPONSOR_1_NAME", ""),
    ("RACE_SPONSOR_1_LOGO", ""),
    ("RACE_SPONSOR_1_READ", ""),
    ("RACE_SPONSOR_1_VIDEO", ""),
    ("RACE_SPONSOR_2_NAME", ""),
    ("RACE_SPONSOR_2_LOGO", ""),
    ("RACE_SPONSOR_2_READ", ""),
    ("RACE_SPONSOR_2_VIDEO", ""),
    ("RACE_SPONSOR_3_NAME", ""),
    ("RACE_SPONSOR_3_LOGO", ""),
    ("RACE_SPONSOR_3_READ", ""),
    ("RACE_SPONSOR_3_VIDEO", ""),
    ("RACE_SPONSOR_4_NAME", ""),
    ("RACE_SPONSOR_4_LOGO", ""),
    ("RACE_SPONSOR_4_READ", ""),
    ("RACE_SPONSOR_4_VIDEO", ""),
    ("RACE_SPONSOR_5_NAME", ""),
    ("RACE_SPONSOR_5_LOGO", ""),
    ("RACE_SPONSOR_5_READ", ""),
    ("RACE_SPONSOR_5_VIDEO", ""),
    ("CRANK_IT_UP_SPONSOR_NAME", ""),
    ("STARTING_LINEUP_SPONSOR_NAME", ""),
    ("STARTING_LINEUP_SPONSOR_LOGO", ""),
    ("STARTING_LINEUP_SPONSOR_READ", ""),
    ("FINAL_RESULTS_SPONSOR_NAME", ""),
    ("FINAL_RESULTS_SPONSOR_LOGO", ""),
    ("FINAL_RESULTS_SPONSOR_READ", ""),
    ("CAUTION_REVIEW_SLATE_SPONSOR_NAME", ""),
    ("CAUTION_REVIEW_SLATE_GRAPHIC", ""),
    ("PRACTICE_MUSIC_PLAYLIST", ""),
    ("QUALIFYING_MUSIC_PLAYLIST", ""),
    ("STUDIO_VOLUME", "65"),
    ("CAUTION_REPLAY_AUDIO", ""),
    ("DRIVER_MODE", "false"),
    ("RECORDED_BROADCAST_FILE", ""),
    ("POST_RACE_INTERVIEWS_ENABLED", "false"),
    ("DISCORD_RACE_REPORT_ENABLED", "false"),
    ("DISCORD_RACE_REPORT_WEBHOOK_URL", ""),
    ("DISCORD_RACE_REPORT_USE_OPENAI", "true"),
    ("USE_LEAGUE_DRIVER_NOTES", "false"),
    ("LEAGUE_MANAGER_ENABLED", "false"),
    ("LEAGUE_DRIVERS_CSV", "league/drivers.csv"),
    ("LEAGUE_SEASON_STATS_CSV", "league/season.csv"),
    ("LEAGUE_CAREER_STATS_CSV", "league/career.csv"),
    ("STAGE_END_LAPS", ""),
    ("LEAGUE_FUEL_PERCENT", ""),
    ("LEAGUE_ENGINE_POWER_PERCENT", ""),
    ("LEAGUE_TIRE_SETS", ""),
    ("LEAGUE_PLAYOFF_CUTOFF", "0"),
]

SIM_RACER_HUB_FIELDS = [
    ("SIMRACERHUB_SOURCE", "https://simracerhub.com"),
    ("SIMRACERHUB_LEAGUE_ID", ""),
    ("SIMRACERHUB_SERIES_ID", ""),
    ("SIMRACERHUB_SEASON_ID", ""),
    ("SIMRACERHUB_TRACK_NAME", ""),
    ("SIMRACERHUB_MIN_STARTS", "2"),
    ("SIMRACERHUB_FIRST_SCHEDULE_ID", ""),
    ("SIMRACERHUB_RACE_SCHEDULE_CSV", "league/race_schedule.csv"),
    ("SIMRACERHUB_SEASON_STATS_OUTPUT", "league/season.csv"),
    ("SIMRACERHUB_CAREER_STATS_OUTPUT", "league/career.csv"),
    ("SIMRACERHUB_DRIVERS_OUTPUT", "league/drivers.csv"),
    ("SIMRACERHUB_CAREER_MODE", "false"),
]

VELOCITY_LEAGUE_FIELDS = [
    ("VELOCITY_LEAGUE_URL", ""),
    ("VELOCITY_SERIES_NAME", ""),
    ("VELOCITY_STATS_OUTPUT", "league/season.csv"),
    ("VELOCITY_CAREER_OUTPUT", "league/career.csv"),
    ("VELOCITY_DRIVERS_OUTPUT", "league/drivers.csv"),
    ("VELOCITY_SCHEDULE_OUTPUT", "league/race_schedule.csv"),
]

LEGACY_SPONSOR_FIELDS = [
    (
        "OVERLAY_BRAND_GRAPHICS",
        "/assets/rgc_motorsports.png,/assets/autism_awareness.png,/assets/keep_it_real.webp",
    ),
    ("OVERLAY_RACE_SPONSOR", ""),
    ("SPONSOR_READ_NAME", ""),
    ("SPONSOR_READ_NAME_2", ""),
    ("SPONSOR_READ_NAME_3", ""),
    ("SPONSOR_READ_CAUSE", ""),
    ("SPONSOR_READ_MESSAGE", ""),
    ("USE_NATIONAL_ANTHEM", "false"),
    ("NATIONAL_ANTHEM_AUDIO", ""),
    ("NATIONAL_ANTHEM_GRAPHICS", ""),
    ("CAUTION_PRESENTATION_GRAPHICS", ""),
]

SAVED_FIELDS = (
    LAUNCHER_FIELDS
    + LEGACY_SPONSOR_FIELDS
    + SIM_RACER_HUB_FIELDS
    + VELOCITY_LEAGUE_FIELDS
)

BROADCAST_FIELD_LABELS = {
    "USE_OPENAI": "Use OpenAI Commentary",
    "OPENAI_API_KEY": "OpenAI API Key",
    "OPENAI_MODEL": "OpenAI Model",
    "USE_ELEVENLABS": "Use ElevenLabs Voices",
    "ELEVENLABS_API_KEY": "ElevenLabs API Key",
    "LEAD_BROADCASTER_NAME": "Lead Broadcaster Name",
    "COLOR_BROADCASTER_NAME": "Analyst Broadcaster Name",
    "PIT_BROADCASTER_NAME": "Pit Road Broadcaster Name",
    "LEAD_VOICE_ID": "Lead Voice ID",
    "COLOR_VOICE_ID": "Analyst Voice ID",
    "PIT_VOICE_ID": "Pit Road Voice ID",
    "OVERLAY_EVENT_TITLE": "Overlay Event Title",
    "OVERLAY_SERIES_NAME": "Series Name",
    "OVERLAY_SERIES_LOGO": "Series Logo",
    "OVERLAY_LEADERBOARD_STYLE": "Leaderboard Style",
    "USE_SIM_RACING_APPS": "Use SIMRacingApps Car Graphics",
    "USE_SPONSOR_READS": "Use Sponsor Reads",
    "SPONSOR_READ_CAUSE_NAME": "Cause / Awareness Name",
    "SPONSOR_READ_CAUSE_LOGO": "Cause / Awareness Logo",
    "SPONSOR_READ_CAUSE_READ": "Cause / Awareness Spoken Read",
    "RACE_SPONSOR_1_NAME": "Sponsor 1 Name",
    "RACE_SPONSOR_1_LOGO": "Sponsor 1 Logo",
    "RACE_SPONSOR_1_READ": "Sponsor 1 Spoken Read",
    "RACE_SPONSOR_1_VIDEO": "Sponsor 1 Commercial Video",
    "RACE_SPONSOR_2_NAME": "Sponsor 2 Name",
    "RACE_SPONSOR_2_LOGO": "Sponsor 2 Logo",
    "RACE_SPONSOR_2_READ": "Sponsor 2 Spoken Read",
    "RACE_SPONSOR_2_VIDEO": "Sponsor 2 Commercial Video",
    "RACE_SPONSOR_3_NAME": "Sponsor 3 Name",
    "RACE_SPONSOR_3_LOGO": "Sponsor 3 Logo",
    "RACE_SPONSOR_3_READ": "Sponsor 3 Spoken Read",
    "RACE_SPONSOR_3_VIDEO": "Sponsor 3 Commercial Video",
    "RACE_SPONSOR_4_NAME": "Sponsor 4 Name",
    "RACE_SPONSOR_4_LOGO": "Sponsor 4 Logo",
    "RACE_SPONSOR_4_READ": "Sponsor 4 Spoken Read",
    "RACE_SPONSOR_4_VIDEO": "Sponsor 4 Commercial Video",
    "RACE_SPONSOR_5_NAME": "Sponsor 5 Name",
    "RACE_SPONSOR_5_LOGO": "Sponsor 5 Logo",
    "RACE_SPONSOR_5_READ": "Sponsor 5 Spoken Read",
    "RACE_SPONSOR_5_VIDEO": "Sponsor 5 Commercial Video",
    "CRANK_IT_UP_SPONSOR_NAME": "Crank It Up Sponsor",
    "STARTING_LINEUP_SPONSOR_NAME": "Starting Lineup Sponsor",
    "STARTING_LINEUP_SPONSOR_LOGO": "Starting Lineup Sponsor Logo",
    "STARTING_LINEUP_SPONSOR_READ": "Starting Lineup Sponsor Read",
    "FINAL_RESULTS_SPONSOR_NAME": "Final Results Sponsor",
    "FINAL_RESULTS_SPONSOR_LOGO": "Final Results Sponsor Logo",
    "FINAL_RESULTS_SPONSOR_READ": "Final Results Sponsor Read",
    "CAUTION_REVIEW_SLATE_SPONSOR_NAME": "Caution Review Slate Sponsor",
    "CAUTION_REVIEW_SLATE_GRAPHIC": "Caution Review Slate Image",
    "PRACTICE_MUSIC_PLAYLIST": "Practice Music Playlist",
    "QUALIFYING_MUSIC_PLAYLIST": "Qualifying Music Playlist",
    "CAUTION_REPLAY_AUDIO": "Caution Replay Music",
    "DRIVER_MODE": "Driver Mode — Record Race Silently",
    "RECORDED_BROADCAST_FILE": "Recorded Broadcast File",
    "POST_RACE_INTERVIEWS_ENABLED": "Post-Race Interviews",
    "DISCORD_RACE_REPORT_ENABLED": "Discord Race Report",
    "DISCORD_RACE_REPORT_WEBHOOK_URL": "Race Report Webhook URL",
    "DISCORD_RACE_REPORT_USE_OPENAI": "Use OpenAI Race Recap",
    "USE_LEAGUE_DRIVER_NOTES": "Use League Driver Profiles",
    "LEAGUE_MANAGER_ENABLED": "Use League Manager for This Race",
    "LEAGUE_DRIVERS_CSV": "Driver Profiles CSV",
    "LEAGUE_SEASON_STATS_CSV": "Season Stats CSV",
    "LEAGUE_CAREER_STATS_CSV": "Career Stats CSV",
    "STAGE_END_LAPS": "Stage End Laps",
    "LEAGUE_FUEL_PERCENT": "Fuel Percent",
    "LEAGUE_ENGINE_POWER_PERCENT": "Engine Power Percent",
    "LEAGUE_TIRE_SETS": "Tire Sets",
    "LEAGUE_PLAYOFF_CUTOFF": "Playoff Positions",
    "VELOCITY_LEAGUE_URL": "Velocity League URL",
    "VELOCITY_SERIES_NAME": "Velocity Series Name",
    "VELOCITY_STATS_OUTPUT": "Velocity Stats CSV",
    "VELOCITY_CAREER_OUTPUT": "Velocity Career CSV",
    "VELOCITY_DRIVERS_OUTPUT": "Velocity Drivers CSV",
    "VELOCITY_SCHEDULE_OUTPUT": "Velocity Schedule CSV",
}

BROADCAST_FIELD_SECTIONS = {
    "USE_OPENAI": "AI Commentary",
    "USE_ELEVENLABS": "Broadcaster Voices",
    "OVERLAY_EVENT_TITLE": "Event Sponsors / Overlay Links",
    "PRACTICE_MUSIC_PLAYLIST": "Practice / Qualifying / Caution Music",
    "DRIVER_MODE": "Recorded Broadcast / Driver Mode",
    "POST_RACE_INTERVIEWS_ENABLED": "Race Flow",
    "DISCORD_RACE_REPORT_ENABLED": "Discord Race Report",
    "USE_LEAGUE_DRIVER_NOTES": "League Data",
    "LEAGUE_FUEL_PERCENT": "League Race Package",
}

BROADCAST_FIELD_HELP = {
    "USE_OPENAI": "Required for the full AI broadcast. Turn this off when a human broadcaster only wants prompts, cameras, and overlays.",
    "OPENAI_API_KEY": "Required when OpenAI commentary is on. Keep this private and never show it on stream.",
    "OPENAI_MODEL": "Model used to write broadcast lines and Discord recaps. Recommended: gpt-5.6-terra. Use gpt-5.6-luna for lower cost/faster calls, gpt-5.6-sol for stronger quality, or gpt-6-astra to test the newest higher-cost model if your API account has access. You can also type a custom OpenAI model ID.",
    "USE_ELEVENLABS": "Required for spoken AI broadcasters. Turn this off for silent producer prompts or a human-only broadcast.",
    "ELEVENLABS_API_KEY": "Required when ElevenLabs voices are on. Keep this private.",
    "LEAD_BROADCASTER_NAME": "Name used when the lead play-by-play broadcaster introduces themselves. Default: Mike.",
    "COLOR_BROADCASTER_NAME": "Name used when the analyst introduces themselves and handles lineup blocks. Default: Jeff.",
    "PIT_BROADCASTER_NAME": "Name used when the pit road broadcaster introduces themselves. Default: Sarah.",
    "LEAD_VOICE_ID": "Voice ID for the lead play-by-play broadcaster.",
    "COLOR_VOICE_ID": "Voice ID for the analyst broadcaster.",
    "PIT_VOICE_ID": "Voice ID for pit road and strategy.",
    "OVERLAY_EVENT_TITLE": "Required for a polished overlay and Discord report title. Example: Autism Awareness 100.",
    "OVERLAY_SERIES_NAME": "League or series name. Example: WFO Wicked Wednesday Truck Series.",
    "OVERLAY_SERIES_LOGO": "Logo for the series. It can rotate in the title with sponsor and cause logos.",
    "OVERLAY_LEADERBOARD_STYLE": "side keeps the NASCAR-style left leaderboard. ticker scrolls across the top under the title. flo uses a compact two-row top leaderboard. brazen uses a leader-focused top board with sponsor rotation, series logo, flag status, and a scrolling field row.",
    "USE_SIM_RACING_APPS": "Uses SIMRacingAppsServer for live 3D car renders and styled car numbers. If this is true, start SIMRacingAppsServer before the broadcast. If you are not using it, set this to false so the overlay does not waste time looking for it.",
    "USE_SPONSOR_READS": "Lets the AI work sponsor mentions into pre-race, caution, and race-update moments.",
    "SPONSOR_READ_CAUSE_NAME": "Short cause or awareness name shown on overlays and used by {cause}. Example: Autism Awareness.",
    "SPONSOR_READ_CAUSE_LOGO": "Logo for the cause/awareness message. It can rotate in the title and appear on sponsor popups.",
    "SPONSOR_READ_CAUSE_READ": "Optional exact words added after sponsor reads for the cause/awareness. Leave blank for the built-in default.",
    "RACE_SPONSOR_1_NAME": "First race sponsor. Sponsor reads, caution overlays, and title rotation use sponsors in this order.",
    "RACE_SPONSOR_1_LOGO": "Logo for Sponsor 1.",
    "RACE_SPONSOR_1_READ": "Optional exact spoken read for Sponsor 1. Use {sponsor} and {cause}; leave blank for AI to write it.",
    "RACE_SPONSOR_1_VIDEO": "Optional commercial video. When this sponsor is read, the Studio can play it full screen over the broadcast.",
    "RACE_SPONSOR_2_NAME": "Second race sponsor.",
    "RACE_SPONSOR_2_LOGO": "Logo for Sponsor 2.",
    "RACE_SPONSOR_2_READ": "Optional exact spoken read for Sponsor 2.",
    "RACE_SPONSOR_2_VIDEO": "Optional commercial video path for Sponsor 2.",
    "RACE_SPONSOR_3_NAME": "Third race sponsor.",
    "RACE_SPONSOR_3_LOGO": "Logo for Sponsor 3.",
    "RACE_SPONSOR_3_READ": "Optional exact spoken read for Sponsor 3.",
    "RACE_SPONSOR_3_VIDEO": "Optional commercial video path for Sponsor 3.",
    "RACE_SPONSOR_4_NAME": "Fourth race sponsor.",
    "RACE_SPONSOR_4_LOGO": "Logo for Sponsor 4.",
    "RACE_SPONSOR_4_READ": "Optional exact spoken read for Sponsor 4.",
    "RACE_SPONSOR_4_VIDEO": "Optional commercial video path for Sponsor 4.",
    "RACE_SPONSOR_5_NAME": "Fifth race sponsor.",
    "RACE_SPONSOR_5_LOGO": "Logo for Sponsor 5.",
    "RACE_SPONSOR_5_READ": "Optional exact spoken read for Sponsor 5.",
    "RACE_SPONSOR_5_VIDEO": "Optional commercial video path for Sponsor 5.",
    "CRANK_IT_UP_SPONSOR_NAME": "Sponsor name used when the Producer or AI fires Crank It Up. Leave blank to use Sponsor 1.",
    "STARTING_LINEUP_SPONSOR_NAME": "Sponsor used for the pre-race starting lineup. Leave blank to use Sponsor 1.",
    "STARTING_LINEUP_SPONSOR_LOGO": "Logo that pops up when the starting lineup sponsor is mentioned. Leave blank to use that sponsor's main logo.",
    "STARTING_LINEUP_SPONSOR_READ": "Optional exact read for the starting lineup sponsor. Supports {sponsor}, {cause}, and {cause_read}.",
    "FINAL_RESULTS_SPONSOR_NAME": "Sponsor used for the final race results. Leave blank to use Sponsor 1.",
    "FINAL_RESULTS_SPONSOR_LOGO": "Logo that pops up when the final results sponsor is mentioned. Leave blank to use that sponsor's main logo.",
    "FINAL_RESULTS_SPONSOR_READ": "Optional exact read for the final race results sponsor. Supports {sponsor}, {cause}, and {cause_read}.",
    "CAUTION_REVIEW_SLATE_SPONSOR_NAME": "Default sponsor name shown on the full-screen caution review slate.",
    "CAUTION_REVIEW_SLATE_GRAPHIC": "Default image shown on the full-screen caution review slate while the producer searches replay angles.",
    "PRACTICE_MUSIC_PLAYLIST": "Practice music playlist. Multiple songs are separated with semicolons and loop during practice.",
    "QUALIFYING_MUSIC_PLAYLIST": "Qualifying music playlist. Multiple songs are separated with semicolons and loop during qualifying. Sponsor graphics come from Sponsor 1-5 logos.",
    "CAUTION_REPLAY_AUDIO": "Music bed used during caution replay/presentation segments.",
    "DRIVER_MODE": "Records the live session while you race. Studio voices, music, automatic cameras, and replay control remain off so they cannot interfere with driving.",
    "RECORDED_BROADCAST_FILE": "Select a Driver Mode .jsonl recording to broadcast afterward while its matching saved iRacing replay is open.",
    "POST_RACE_INTERVIEWS_ENABLED": "If true, the AI finishes the race recap/top 10 and then hands off to human post-race interviews for the top three. If false, it does the normal signoff.",
    "DISCORD_RACE_REPORT_ENABLED": "Posts an automatic post-race recap to a Discord webhook after the finish order stabilizes.",
    "DISCORD_RACE_REPORT_WEBHOOK_URL": "Required when Discord Race Report is true. Create this webhook in the Discord results channel.",
    "DISCORD_RACE_REPORT_USE_OPENAI": "Uses OpenAI for a more natural race recap. If off, the Studio posts a simpler generated recap.",
    "USE_LEAGUE_DRIVER_NOTES": "Turns on league driver profiles, about stories, season stats, career stats, teams, sponsors, hometowns, and driving styles.",
    "LEAGUE_MANAGER_ENABLED": "Automatically saves the completed iRacing results into this profile after the post-race broadcast finishes. With AI commentary off, it waits for the classified results to stabilize after the checkered flag.",
    "LEAGUE_DRIVERS_CSV": "Driver profile CSV used for About stories and league-specific info.",
    "LEAGUE_SEASON_STATS_CSV": "Current-season stats CSV imported from Sim Racer Hub.",
    "LEAGUE_CAREER_STATS_CSV": "Career/all-season stats CSV imported from Sim Racer Hub.",
    "STAGE_END_LAPS": "Optional comma-separated stage end laps. Example: 30,60.",
    "LEAGUE_FUEL_PERCENT": "Optional league race setting. Example: 65 means Mike can mention fuel is set at 65 percent during the opening.",
    "LEAGUE_ENGINE_POWER_PERCENT": "Optional league race setting. Example: 90 means Mike can mention engine power is set at 90 percent.",
    "LEAGUE_TIRE_SETS": "Optional league race tire limit. Example: 3 means Mike can mention three tire sets are available.",
    "LEAGUE_PLAYOFF_CUTOFF": "Number of championship positions highlighted as playoff eligible. Use 12 for the Tuesday and Wednesday Velocity series, or 0 when the league has no playoff cutoff.",
    "VELOCITY_LEAGUE_URL": "Public Velocity League home URL. The importer automatically checks its directory, selected-series standings, combined career stats, series page, and schedule.",
    "VELOCITY_SERIES_NAME": "Optional Velocity series name or URL key, such as tuesday-night-trucks. A Velocity standings or series URL can also supply this automatically.",
    "VELOCITY_STATS_OUTPUT": "CSV where selected-series Velocity standings are written. Usually league/season.csv.",
    "VELOCITY_CAREER_OUTPUT": "CSV where Velocity's combined league career statistics are written. Usually league/career.csv.",
    "VELOCITY_DRIVERS_OUTPUT": "CSV where Velocity driver names and numbers are written. Usually league/drivers.csv.",
    "VELOCITY_SCHEDULE_OUTPUT": "CSV where Velocity schedule rows are written. Usually league/race_schedule.csv.",
}

IMPORTANT_SETUP_FIELDS = {
    "OPENAI_API_KEY",
    "ELEVENLABS_API_KEY",
    "LEAD_VOICE_ID",
    "COLOR_VOICE_ID",
    "PIT_VOICE_ID",
    "OVERLAY_EVENT_TITLE",
    "RACE_SPONSOR_1_NAME",
    "RACE_SPONSOR_1_LOGO",
    "DISCORD_RACE_REPORT_WEBHOOK_URL",
    "LEAGUE_DRIVERS_CSV",
    "LEAGUE_SEASON_STATS_CSV",
    "LEAGUE_CAREER_STATS_CSV",
}

INLINE_HELP_FIELDS = {
    "USE_OPENAI",
    "OPENAI_API_KEY",
    "OPENAI_MODEL",
    "USE_ELEVENLABS",
    "ELEVENLABS_API_KEY",
    "LEAD_BROADCASTER_NAME",
    "COLOR_BROADCASTER_NAME",
    "PIT_BROADCASTER_NAME",
    "OVERLAY_EVENT_TITLE",
    "OVERLAY_SERIES_LOGO",
    "USE_SIM_RACING_APPS",
    "USE_SPONSOR_READS",
    "SPONSOR_READ_CAUSE_NAME",
    "SPONSOR_READ_CAUSE_LOGO",
    "SPONSOR_READ_CAUSE_READ",
    "RACE_SPONSOR_1_NAME",
    "RACE_SPONSOR_1_LOGO",
    "RACE_SPONSOR_1_READ",
    "RACE_SPONSOR_1_VIDEO",
    "RACE_SPONSOR_2_NAME",
    "RACE_SPONSOR_2_LOGO",
    "RACE_SPONSOR_2_READ",
    "RACE_SPONSOR_2_VIDEO",
    "CRANK_IT_UP_SPONSOR_NAME",
    "STARTING_LINEUP_SPONSOR_NAME",
    "STARTING_LINEUP_SPONSOR_LOGO",
    "STARTING_LINEUP_SPONSOR_READ",
    "FINAL_RESULTS_SPONSOR_NAME",
    "FINAL_RESULTS_SPONSOR_LOGO",
    "FINAL_RESULTS_SPONSOR_READ",
    "CAUTION_REVIEW_SLATE_SPONSOR_NAME",
    "CAUTION_REVIEW_SLATE_GRAPHIC",
    "PRACTICE_MUSIC_PLAYLIST",
    "QUALIFYING_MUSIC_PLAYLIST",
    "DRIVER_MODE",
    "RECORDED_BROADCAST_FILE",
    "POST_RACE_INTERVIEWS_ENABLED",
    "DISCORD_RACE_REPORT_ENABLED",
    "DISCORD_RACE_REPORT_WEBHOOK_URL",
    "USE_LEAGUE_DRIVER_NOTES",
    "LEAGUE_MANAGER_ENABLED",
    "STAGE_END_LAPS",
    "LEAGUE_FUEL_PERCENT",
    "LEAGUE_ENGINE_POWER_PERCENT",
    "LEAGUE_TIRE_SETS",
    "LEAGUE_PLAYOFF_CUTOFF",
}

BOOLEAN_SETTING_KEYS = {
    "USE_OPENAI",
    "USE_ELEVENLABS",
    "USE_SIM_RACING_APPS",
    "USE_SPONSOR_READS",
    "POST_RACE_INTERVIEWS_ENABLED",
    "DISCORD_RACE_REPORT_ENABLED",
    "DISCORD_RACE_REPORT_USE_OPENAI",
    "USE_LEAGUE_DRIVER_NOTES",
    "LEAGUE_MANAGER_ENABLED",
    "DRIVER_MODE",
}


def load_env_file(path=ENV_PATH):
    values = {}
    path = Path(path)
    if not path.exists():
        return values

    for raw_line in path.read_text(encoding="utf-8").splitlines():
        line = raw_line.strip()
        if not line or line.startswith("#") or "=" not in line:
            continue
        key, value = line.split("=", 1)
        values[key.strip()] = value.strip()
    return values


def project_version(root=ROOT):
    pyproject = Path(root) / "pyproject.toml"
    try:
        with pyproject.open("rb") as file:
            data = tomllib.load(file)
        return str(data.get("project", {}).get("version", "0.0.0"))
    except Exception:
        return "0.0.0"


APP_VERSION = project_version()


def version_parts(version):
    cleaned = str(version or "").strip().lstrip("vV")
    parts = []
    for token in re.split(r"[.+\\-]", cleaned):
        if token.isdigit():
            parts.append(int(token))
        else:
            break
    while len(parts) < 3:
        parts.append(0)
    return tuple(parts[:3])


def is_newer_version(latest, current=APP_VERSION):
    return version_parts(latest) > version_parts(current)


def fetch_latest_release(api_url=GITHUB_LATEST_RELEASE_API, timeout=6):
    request = urllib.request.Request(
        api_url,
        headers={
            "Accept": "application/vnd.github+json",
            "User-Agent": f"RGC-AI-Broadcast-Studio/{APP_VERSION}",
        },
    )
    with urllib.request.urlopen(request, timeout=timeout) as response:
        return json.loads(response.read().decode("utf-8"))


def update_status_from_release(release, current_version=APP_VERSION):
    tag = str(release.get("tag_name") or release.get("name") or "").strip()
    latest_version = tag.lstrip("vV")
    release_url = release.get("html_url") or GITHUB_RELEASES_URL
    if latest_version and is_newer_version(latest_version, current_version):
        return (
            "available",
            f"Update available: v{latest_version}",
            release_url,
        )
    if latest_version:
        return (
            "current",
            f"You are up to date. Installed v{current_version}; latest v{latest_version}.",
            release_url,
        )
    return (
        "unknown",
        "Could not read a version from the latest GitHub release.",
        GITHUB_RELEASES_URL,
    )


def save_env_file(values, path=ENV_PATH):
    lines = [
        "# Generated by RGC AI Broadcast Studio launcher.",
        "# You can still edit this file manually if needed.",
        "",
    ]
    for key, default in SAVED_FIELDS:
        lines.append(f"{key}={values.get(key, default)}")
    lines.append("")
    Path(path).write_text("\n".join(lines), encoding="utf-8")


def sanitize_profile_name(name):
    cleaned = re.sub(r"[^A-Za-z0-9 _.-]+", "", str(name or "")).strip()
    cleaned = re.sub(r"\s+", " ", cleaned)
    return cleaned[:60]


def profile_path(profile_name, profile_dir=PROFILE_DIR):
    safe_name = sanitize_profile_name(profile_name)
    if not safe_name:
        raise ValueError("Profile name is required.")
    filename = safe_name.replace(" ", "_")
    return Path(profile_dir) / f"{filename}.env"


def list_profiles(profile_dir=PROFILE_DIR):
    profile_dir = Path(profile_dir)
    if not profile_dir.exists():
        return []
    names = []
    for path in sorted(profile_dir.glob("*.env")):
        names.append(path.stem.replace("_", " "))
    return names


def save_profile(profile_name, values, profile_dir=PROFILE_DIR):
    path = profile_path(profile_name, profile_dir)
    path.parent.mkdir(parents=True, exist_ok=True)
    save_env_file(values, path)
    return path


def load_profile(profile_name, profile_dir=PROFILE_DIR):
    path = profile_path(profile_name, profile_dir)
    if not path.exists():
        raise FileNotFoundError(f"Profile not found: {profile_name}")
    values = launcher_defaults(load_env_file(path))
    return migrate_legacy_velocity_profile_paths(profile_name, values)


def delete_profile(profile_name, profile_dir=PROFILE_DIR):
    path = profile_path(profile_name, profile_dir)
    if not path.exists():
        raise FileNotFoundError(f"Profile not found: {profile_name}")
    path.unlink()
    return path


def launcher_defaults(existing=None):
    existing = existing or {}
    defaults = {key: existing.get(key, default) for key, default in SAVED_FIELDS}
    if not defaults.get("RACE_SPONSOR_1_NAME"):
        defaults["RACE_SPONSOR_1_NAME"] = (
            existing.get("SPONSOR_READ_NAME")
            or existing.get("OVERLAY_RACE_SPONSOR")
            or ""
        )
    if not defaults.get("RACE_SPONSOR_2_NAME"):
        defaults["RACE_SPONSOR_2_NAME"] = existing.get("SPONSOR_READ_NAME_2", "")
    if not defaults.get("RACE_SPONSOR_3_NAME"):
        defaults["RACE_SPONSOR_3_NAME"] = existing.get("SPONSOR_READ_NAME_3", "")
    if not defaults.get("RACE_SPONSOR_1_READ"):
        defaults["RACE_SPONSOR_1_READ"] = existing.get("SPONSOR_READ_MESSAGE", "")
    if not defaults.get("SPONSOR_READ_CAUSE_NAME"):
        defaults["SPONSOR_READ_CAUSE_NAME"] = existing.get("SPONSOR_READ_CAUSE", "")
    if not defaults.get("OVERLAY_RACE_SPONSOR"):
        defaults["OVERLAY_RACE_SPONSOR"] = defaults.get("RACE_SPONSOR_1_NAME", "")
    if not defaults.get("SPONSOR_READ_NAME"):
        defaults["SPONSOR_READ_NAME"] = defaults.get("RACE_SPONSOR_1_NAME", "")
    if not defaults.get("SPONSOR_READ_NAME_2"):
        defaults["SPONSOR_READ_NAME_2"] = defaults.get("RACE_SPONSOR_2_NAME", "")
    if not defaults.get("SPONSOR_READ_NAME_3"):
        defaults["SPONSOR_READ_NAME_3"] = defaults.get("RACE_SPONSOR_3_NAME", "")
    if not defaults.get("SPONSOR_READ_MESSAGE"):
        defaults["SPONSOR_READ_MESSAGE"] = defaults.get("RACE_SPONSOR_1_READ", "")
    if not defaults.get("CRANK_IT_UP_SPONSOR_NAME"):
        defaults["CRANK_IT_UP_SPONSOR_NAME"] = defaults.get("RACE_SPONSOR_1_NAME", "")
    if not defaults.get("QUALIFYING_MUSIC_PLAYLIST"):
        defaults["QUALIFYING_MUSIC_PLAYLIST"] = existing.get("NATIONAL_ANTHEM_AUDIO", "")
    if "STUDIO_VOLUME" not in existing and "PRACTICE_MUSIC_VOLUME" in existing:
        defaults["STUDIO_VOLUME"] = existing["PRACTICE_MUSIC_VOLUME"]
    return defaults


def new_profile_defaults(profile_name):
    """Return clean defaults with isolated league files for a brand-new profile."""
    values = launcher_defaults()
    drivers_csv, season_csv, career_csv, schedule_csv = league_csv_paths_for_profile(profile_name)
    values.update(
        {
            "LEAGUE_DRIVERS_CSV": drivers_csv,
            "LEAGUE_SEASON_STATS_CSV": season_csv,
            "LEAGUE_CAREER_STATS_CSV": career_csv,
            "SIMRACERHUB_RACE_SCHEDULE_CSV": schedule_csv,
            "SIMRACERHUB_SEASON_STATS_OUTPUT": season_csv,
            "SIMRACERHUB_CAREER_STATS_OUTPUT": career_csv,
            "SIMRACERHUB_DRIVERS_OUTPUT": drivers_csv,
            "VELOCITY_STATS_OUTPUT": season_csv,
            "VELOCITY_CAREER_OUTPUT": career_csv,
            "VELOCITY_DRIVERS_OUTPUT": drivers_csv,
            "VELOCITY_SCHEDULE_OUTPUT": schedule_csv,
        }
    )
    return values


def setting_enabled(values, key, default="false"):
    return str(values.get(key, default) or default).strip().lower() in {
        "1",
        "true",
        "yes",
        "on",
    }


def bool_setting_text(values, key, default="false"):
    return "true" if setting_enabled(values, key, default) else "false"


def resolve_project_path(path_value, root=ROOT):
    path = Path(str(path_value or "").strip())
    if not path:
        return Path(root)
    if path.is_absolute():
        return path
    return Path(root) / path


def load_driver_profile_rows(csv_path):
    path = Path(csv_path)
    if not path.exists():
        return []
    rows = []
    with path.open(newline="", encoding="utf-8-sig") as csv_file:
        reader = csv.DictReader(csv_file)
        for row in reader:
            normalized = {field: str(row.get(field, "") or "").strip() for field in DRIVER_PROFILE_FIELDS}
            if not normalized.get("about"):
                normalized["about"] = str(row.get("notes", "") or "").strip()
            if normalized["name"] or normalized["car_number"]:
                rows.append(normalized)
    return rows


def save_driver_profile_rows(csv_path, rows):
    path = Path(csv_path)
    path.parent.mkdir(parents=True, exist_ok=True)
    clean_rows = []
    for row in rows:
        clean_row = {field: str((row or {}).get(field, "") or "").strip() for field in DRIVER_PROFILE_FIELDS}
        if clean_row["name"] or clean_row["car_number"]:
            clean_rows.append(clean_row)
    with path.open("w", newline="", encoding="utf-8") as csv_file:
        writer = csv.DictWriter(csv_file, fieldnames=DRIVER_PROFILE_FIELDS)
        writer.writeheader()
        writer.writerows(clean_rows)
    return path


def driver_profile_label(row):
    name = str((row or {}).get("name", "") or "").strip() or "Unnamed Driver"
    number = str((row or {}).get("car_number", "") or "").strip()
    return f"#{number} {name}" if number else name


def league_folder_slug(name):
    cleaned = sanitize_profile_name(name)
    if not cleaned:
        return ""
    return cleaned.replace(" ", "_")


def league_csv_paths_for_profile(profile_name):
    slug = league_folder_slug(profile_name)
    if not slug:
        return (
            "league/drivers.csv",
            "league/season.csv",
            "league/career.csv",
            "league/race_schedule.csv",
        )
    return (
        f"league/{slug}/drivers.csv",
        f"league/{slug}/season.csv",
        f"league/{slug}/career.csv",
        f"league/{slug}/race_schedule.csv",
    )


def migrate_legacy_velocity_profile_paths(profile_name, values):
    """Move older Velocity profiles off the shared league CSV defaults."""
    migrated = dict(values or {})
    if not str(migrated.get("VELOCITY_LEAGUE_URL", "") or "").strip():
        return migrated

    drivers_csv, season_csv, career_csv, schedule_csv = league_csv_paths_for_profile(
        profile_name
    )
    mappings = (
        ("LEAGUE_DRIVERS_CSV", "league/drivers.csv", drivers_csv),
        ("LEAGUE_SEASON_STATS_CSV", "league/season.csv", season_csv),
        ("LEAGUE_CAREER_STATS_CSV", "league/career.csv", career_csv),
        ("SIMRACERHUB_RACE_SCHEDULE_CSV", "league/race_schedule.csv", schedule_csv),
        ("VELOCITY_DRIVERS_OUTPUT", "league/drivers.csv", drivers_csv),
        ("VELOCITY_STATS_OUTPUT", "league/season.csv", season_csv),
        ("VELOCITY_CAREER_OUTPUT", "league/career.csv", career_csv),
        ("VELOCITY_SCHEDULE_OUTPUT", "league/race_schedule.csv", schedule_csv),
    )
    for key, old_default, profile_path_value in mappings:
        current = str(migrated.get(key, "") or "").strip()
        if not current or current.replace("\\", "/").casefold() == old_default.casefold():
            migrated[key] = profile_path_value
    return migrated


def ensure_profile_league_files(profile_name="", root=ROOT):
    root = Path(root)
    drivers_csv, season_stats_csv, career_stats_csv, race_schedule_csv = league_csv_paths_for_profile(profile_name)
    created = []

    drivers_path = resolve_project_path(drivers_csv, root)
    if not drivers_path.exists():
        ensure_empty_driver_profile_csv(drivers_path)
        created.append(str(drivers_path))

    schedule_path = resolve_project_path(race_schedule_csv, root)
    if not schedule_path.exists():
        ensure_empty_race_schedule_csv(schedule_path)
        created.append(str(schedule_path))

    stats_header = (
        "name,car_number,stats_scope,starts,wins,top_fives,top_tens,poles,"
        "avg_finish,last_finish,points_position,points_to_next,"
        "track_starts,track_wins,best_track_finish,notes\n"
    )
    for stats_csv in (season_stats_csv, career_stats_csv):
        stats_path = resolve_project_path(stats_csv, root)
        stats_path.parent.mkdir(parents=True, exist_ok=True)
        if not stats_path.exists():
            stats_path.write_text(stats_header, encoding="utf-8")
            created.append(str(stats_path))

    return created, (drivers_csv, season_stats_csv, career_stats_csv, race_schedule_csv)


def driver_roster_import_target(active_driver_csv="", sim_racer_hub_output=""):
    """Return the one driver CSV the editor and Sim Racer Hub import should share."""
    active = str(active_driver_csv or "").strip()
    if active:
        return active
    configured = str(sim_racer_hub_output or "").strip()
    return configured or "league/drivers.csv"


def velocity_output_defaults(values):
    """Keep legacy Velocity output fields aligned with the active league profile."""
    values = dict(values or {})
    mappings = (
        ("VELOCITY_DRIVERS_OUTPUT", "LEAGUE_DRIVERS_CSV", "league/drivers.csv"),
        ("VELOCITY_STATS_OUTPUT", "LEAGUE_SEASON_STATS_CSV", "league/season.csv"),
        ("VELOCITY_CAREER_OUTPUT", "LEAGUE_CAREER_STATS_CSV", "league/career.csv"),
        ("VELOCITY_SCHEDULE_OUTPUT", "SIMRACERHUB_RACE_SCHEDULE_CSV", "league/race_schedule.csv"),
    )
    resolved = {}
    for velocity_key, active_key, generic_default in mappings:
        configured = str(values.get(velocity_key, "") or "").strip()
        active = str(values.get(active_key, "") or "").strip()
        resolved[velocity_key] = (
            active if active and configured in ("", generic_default) else configured or active or generic_default
        )
    return resolved


def csv_has_data_rows(path):
    try:
        with Path(path).open(newline="", encoding="utf-8-sig") as csv_file:
            return next(csv.DictReader(csv_file), None) is not None
    except (OSError, csv.Error):
        return False


def ensure_empty_driver_profile_csv(csv_path):
    path = Path(csv_path)
    if path.exists():
        return path
    return save_driver_profile_rows(path, [])


def ensure_empty_race_schedule_csv(csv_path):
    path = Path(csv_path)
    if path.exists():
        return path
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("w", newline="", encoding="utf-8") as csv_file:
        writer = csv.DictWriter(csv_file, fieldnames=RACE_SCHEDULE_FIELDS)
        writer.writeheader()
    return path


def sim_racing_apps_is_running(url=SIM_RACING_APPS_HEALTH_URL, timeout=0.35):
    try:
        with urllib.request.urlopen(url, timeout=timeout) as response:
            if not 200 <= int(getattr(response, "status", 200)) < 500:
                return False
            payload = json.loads(response.read(64_000).decode("utf-8", errors="ignore"))
            if str(payload.get("State") or "").strip().upper() == "ERROR":
                return False
            value = str(payload.get("Value") or payload.get("ValueFormatted") or "").strip()
            return bool(value) and "NO CONNECTION TO SIM" not in value.upper()
    except Exception:
        return False


def trading_paints_is_running(process_output=None):
    """Return True when the Trading Paints desktop client appears to be running."""
    try:
        if process_output is None:
            if os.name == "nt":
                process_output = subprocess.check_output(
                    ["tasklist", "/fo", "csv", "/nh"],
                    text=True,
                    stderr=subprocess.DEVNULL,
                    timeout=1.0,
                )
            else:
                process_output = subprocess.check_output(
                    ["ps", "-A", "-o", "comm="],
                    text=True,
                    stderr=subprocess.DEVNULL,
                    timeout=1.0,
                )
    except Exception:
        return False

    normalized = str(process_output or "").lower().replace(" ", "")
    return "tradingpaints" in normalized


def build_health_status(values, root=ROOT, broadcast_running=False):
    """Return launcher health rows as (name, state, detail, level)."""

    rows = []

    if setting_enabled(values, "USE_OPENAI", "true"):
        if values.get("OPENAI_API_KEY"):
            rows.append(("OpenAI", "Ready", values.get("OPENAI_MODEL", "Configured"), "ok"))
        else:
            rows.append(("OpenAI", "Needs key", "Add OPENAI_API_KEY or turn OpenAI off.", "warn"))
    else:
        rows.append(("OpenAI", "Off", "AI commentary generation disabled.", "off"))

    if setting_enabled(values, "USE_ELEVENLABS", "true"):
        missing = []
        if not values.get("ELEVENLABS_API_KEY"):
            missing.append("API key")
        if not values.get("LEAD_VOICE_ID"):
            missing.append("lead voice")
        if not values.get("COLOR_VOICE_ID"):
            missing.append("analyst voice")
        if not values.get("PIT_VOICE_ID"):
            missing.append("pit road voice")
        if missing:
            rows.append(
                (
                    "ElevenLabs",
                    "Needs setup",
                    f"Missing {', '.join(missing)}.",
                    "warn",
                )
            )
        else:
            rows.append(("ElevenLabs", "Ready", "All broadcaster voices configured.", "ok"))
    else:
        rows.append(("ElevenLabs", "Off", "Voice playback disabled.", "off"))

    rows.append(("Overlay", "Ready", DEFAULT_OVERLAY_URL, "ok"))
    rows.append(("Producer Assist", "Ready", DEFAULT_PRODUCER_URL, "ok"))
    if not setting_enabled(values, "USE_SIM_RACING_APPS", "true"):
        rows.append(
            (
                "SIMRacingApps",
                "Disabled",
                "Live car renders and styled car numbers are off. The overlay will use fallback graphics.",
                "off",
            )
        )
    elif sim_racing_apps_is_running():
        rows.append(
            (
                "SIMRacingApps",
                "Running",
                "Live car renders and styled car numbers should be available.",
                "ok",
            )
        )
    else:
        rows.append(
            (
                "SIMRacingApps",
                "Not connected",
                "Start SIMRacingAppsServer and make sure it shows a connection to iRacing, or set Use SIMRacingApps Car Graphics to false.",
                "warn",
            )
        )

    if trading_paints_is_running():
        rows.append(
            (
                "Trading Paints",
                "Running",
                "Custom paints should stay current for the most accurate car graphics.",
                "ok",
            )
        )
    else:
        rows.append(
            (
                "Trading Paints",
                "Not detected",
                "Start Trading Paints before joining iRacing if you want the most accurate current paints.",
                "warn",
            )
        )

    if setting_enabled(values, "USE_LEAGUE_DRIVER_NOTES", "false"):
        drivers_path = resolve_project_path(values.get("LEAGUE_DRIVERS_CSV"), root)
        season_path = resolve_project_path(values.get("LEAGUE_SEASON_STATS_CSV"), root)
        career_path = resolve_project_path(values.get("LEAGUE_CAREER_STATS_CSV"), root)
        missing_files = [
            label
            for label, path in (
                ("drivers", drivers_path),
                ("season stats", season_path),
                ("career stats", career_path),
            )
            if not path.exists()
        ]
        if missing_files:
            rows.append(
                (
                    "League Profiles",
                    "Needs files",
                    f"Missing {', '.join(missing_files)} CSV file(s).",
                    "warn",
                )
            )
        else:
            empty_stats = [
                label
                for label, path in (("season stats", season_path), ("career stats", career_path))
                if not csv_has_data_rows(path)
            ]
            if empty_stats:
                rows.append(
                    (
                        "League Profiles",
                        "Stats empty",
                        f"The {', '.join(empty_stats)} CSV has no driver rows. Import league data again before broadcasting.",
                        "warn",
                    )
                )
            else:
                rows.append(
                    (
                        "League Profiles",
                        "Ready",
                        "Driver, season stats, and career stats CSV files found and contain data.",
                        "ok",
                    )
                )
    else:
        rows.append(("League Profiles", "Off", "League driver context disabled.", "off"))

    if values.get("PRACTICE_MUSIC_PLAYLIST"):
        songs = [
            path
            for path in str(values.get("PRACTICE_MUSIC_PLAYLIST", "")).split(";")
            if path.strip()
        ]
        existing_songs = [path for path in songs if Path(path).expanduser().exists()]
        if existing_songs:
            rows.append(("Practice Music", "Ready", f"{len(existing_songs)} song(s) found.", "ok"))
        else:
            rows.append(("Practice Music", "Check files", "Playlist is set, but no song files were found.", "warn"))
    else:
        rows.append(("Practice Music", "Off", "No practice playlist selected.", "off"))

    if setting_enabled(values, "DISCORD_RACE_REPORT_ENABLED", "false"):
        if values.get("DISCORD_RACE_REPORT_WEBHOOK_URL"):
            detail = "Automatic post-race Discord recap is ready. Sim Racer Hub links come from Season ID and the imported schedule."
            rows.append(("Discord Race Report", "Ready", detail, "ok"))
        else:
            rows.append(
                (
                    "Discord Race Report",
                    "Needs webhook",
                    "Add a Discord webhook URL or turn Discord Race Report off.",
                    "warn",
                )
            )
    else:
        rows.append(("Discord Race Report", "Off", "No post-race Discord recap will be posted.", "off"))

    if broadcast_running:
        rows.append(("Broadcast", "Running", "Use Stop Broadcast before closing.", "ok"))
    else:
        rows.append(("Broadcast", "Stopped", "Ready to start when iRacing is open.", "off"))

    return rows


def build_first_time_setup_checklist(
    values,
    root=ROOT,
    broadcast_running=False,
    profile_names=None,
):
    """Return setup checklist rows as (name, state, detail, level)."""

    profile_names = list_profiles() if profile_names is None else list(profile_names)
    rows = []

    if sys.version_info >= (3, 11):
        rows.append(
            (
                "Python runtime",
                "Ready",
                f"Python {sys.version_info.major}.{sys.version_info.minor} detected.",
                "ok",
            )
        )
    else:
        rows.append(
            (
                "Python runtime",
                "Needs 3.11+",
                "Install Python 3.11 or newer and check Add Python to PATH.",
                "warn",
            )
        )

    health = {name: (state, detail, level) for name, state, detail, level in build_health_status(values, root, broadcast_running)}
    for name in (
        "OpenAI",
        "ElevenLabs",
        "SIMRacingApps",
        "League Profiles",
        "Practice Music",
        "Discord Race Report",
    ):
        state, detail, level = health.get(name, ("Unknown", "Refresh Broadcast Health.", "warn"))
        rows.append((name, state, detail, level))

    event_title = str(values.get("OVERLAY_EVENT_TITLE", "")).strip()
    sponsor = str(
        values.get("RACE_SPONSOR_1_NAME")
        or values.get("OVERLAY_RACE_SPONSOR", "")
    ).strip()
    graphics = [
        item.strip()
        for item in ",".join(
            [
                str(values.get("OVERLAY_SERIES_LOGO", "")),
                str(values.get("SPONSOR_READ_CAUSE_LOGO", "")),
                ",".join(
                    str(values.get(f"RACE_SPONSOR_{index}_LOGO", ""))
                    for index in range(1, 6)
                ),
            ]
        ).split(",")
        if item.strip()
    ]
    if event_title and sponsor and graphics:
        rows.append(
            (
                "Overlay branding",
                "Ready",
                "Event title, race sponsor, and title graphics are set.",
                "ok",
            )
        )
    elif event_title:
        rows.append(
            (
                "Overlay branding",
                "Usable",
                "Add race sponsor and sponsor logos when you want the overlay to look complete.",
                "off",
            )
        )
    else:
        rows.append(
            (
                "Overlay branding",
                "Needs title",
                "Add an event title before release or league-night testing.",
                "warn",
            )
        )

    if profile_names:
        rows.append(
            (
                "Profiles",
                "Ready",
                f"{len(profile_names)} saved profile(s) available.",
                "ok",
            )
        )
    else:
        rows.append(
            (
                "Profiles",
                "Recommended",
                "Save at least one profile for your league or official-race setup.",
                "warn",
            )
        )

    rows.append(("Overlay link", "Ready", DEFAULT_OVERLAY_URL, "ok"))
    rows.append(("Producer Assist link", "Ready", DEFAULT_PRODUCER_URL, "ok"))
    rows.append(
        (
            "iRacing / OBS",
            "Manual check",
            "Open iRacing, add the browser overlay in OBS/Streamlabs, then run a short smoke test.",
            "off",
        )
    )

    if broadcast_running:
        rows.append(
            (
                "Broadcast process",
                "Running",
                "Use Stop Broadcast before changing release settings.",
                "warn",
            )
        )
    else:
        rows.append(
            (
                "Broadcast process",
                "Stopped",
                "Ready for setup changes or a clean start.",
                "ok",
            )
        )

    return rows


def ensure_league_files(root=ROOT):
    created, _paths = ensure_profile_league_files("", root=root)
    return created


def sanitize_asset_name(path):
    source = Path(path)
    stem = re.sub(r"[^A-Za-z0-9_-]+", "_", source.stem).strip("_").lower()
    suffix = source.suffix.lower()
    if not stem:
        stem = "sponsor_logo"
    if suffix not in {".png", ".jpg", ".jpeg", ".webp", ".gif", ".svg"}:
        suffix = ".png"
    return f"{stem}{suffix}"


def sanitize_video_asset_name(path):
    source = Path(path)
    stem = re.sub(r"[^A-Za-z0-9_-]+", "_", source.stem).strip("_").lower()
    suffix = source.suffix.lower()
    if not stem:
        stem = "sponsor_commercial"
    if suffix not in {".mp4", ".mov", ".mkv", ".webm", ".avi"}:
        suffix = ".mp4"
    return f"{stem}{suffix}"


def install_overlay_brand_graphics(paths, static_dir=STATIC_ASSET_DIR):
    static_dir = Path(static_dir)
    static_dir.mkdir(parents=True, exist_ok=True)
    asset_paths = []

    for raw_path in paths:
        if not raw_path:
            continue
        source = Path(raw_path)
        if not source.exists() or not source.is_file():
            continue

        target = static_dir / sanitize_asset_name(source)
        if source.resolve() != target.resolve():
            shutil.copyfile(source, target)
        asset_paths.append(f"/assets/{target.name}")

    return asset_paths


def install_overlay_commercial_video(path, static_dir=STATIC_ASSET_DIR):
    if not path:
        return ""
    source = Path(path)
    if not source.exists() or not source.is_file():
        return ""

    static_dir = Path(static_dir)
    static_dir.mkdir(parents=True, exist_ok=True)
    target = static_dir / sanitize_video_asset_name(source)
    if source.resolve() != target.resolve():
        shutil.copyfile(source, target)
    return f"/assets/{target.name}"


def format_playlist_paths(paths):
    return ";".join(str(Path(path)) for path in paths if path)


def apply_audio_file_selection(values, field_name, path):
    if isinstance(path, (list, tuple)):
        values[field_name] = format_playlist_paths(path)
    else:
        values[field_name] = str(Path(path))
    return values


def open_external_link(url):
    webbrowser.open(url)


def producer_assist_launch_url():
    return DEFAULT_PRODUCER_URL


def local_lan_ip():
    try:
        with socket.socket(socket.AF_INET, socket.SOCK_DGRAM) as sock:
            sock.connect(("8.8.8.8", 80))
            return sock.getsockname()[0]
    except OSError:
        try:
            return socket.gethostbyname(socket.gethostname())
        except OSError:
            return "127.0.0.1"


def tailscale_ip():
    try:
        result = subprocess.run(
            ["tailscale", "ip", "-4"],
            capture_output=True,
            text=True,
            timeout=1.0,
            check=False,
            creationflags=broadcast_creation_flags(),
        )
    except (OSError, subprocess.TimeoutExpired):
        return ""
    if result.returncode != 0:
        return ""
    for line in result.stdout.splitlines():
        ip = line.strip()
        if ip.startswith("100."):
            return ip
    return ""


def best_remote_helper_ip():
    return tailscale_ip() or local_lan_ip()


def producer_link_for_host(host):
    host = str(host or "127.0.0.1").strip()
    display_host = best_remote_helper_ip() if host in ("0.0.0.0", "::") else host
    return f"http://{display_host}:8765/producer"


def generate_remote_session_code():
    alphabet = "ABCDEFGHJKLMNPQRSTUVWXYZ23456789"
    return "".join(secrets.choice(alphabet) for _ in range(8))


def remote_producer_link(values):
    if not setting_enabled(values, "REMOTE_PRODUCER_ENABLED", "false"):
        return ""
    relay_url = str(values.get("REMOTE_PRODUCER_RELAY_URL", "") or "").strip().rstrip("/")
    session_code = str(values.get("REMOTE_PRODUCER_SESSION_CODE", "") or "").strip()
    if not relay_url or not session_code:
        return ""
    pin = str(values.get("REMOTE_PRODUCER_PIN", "") or "").strip()
    link = f"{relay_url}/producer/{quote(session_code)}"
    if pin:
        link = f"{link}?pin={quote(pin)}"
    return link


def copy_to_clipboard(root, text):
    root.clipboard_clear()
    root.clipboard_append(text)
    root.update()


def broadcast_command(values=None, replay_path=""):
    values = values or load_env_file()
    command = [
        sys.executable,
        str(ROOT / "app.py"),
        "--overlay",
        "--camera-mode",
        "auto",
        "--incident-replay",
        "auto",
    ]
    if replay_path:
        command.extend(["--replay", str(replay_path)])
    elif setting_enabled(values, "DRIVER_MODE", "false"):
        command.append("--driver-mode")
    return command


def broadcast_creation_flags():
    if os.name != "nt":
        return 0
    return getattr(subprocess, "CREATE_NO_WINDOW", 0)


def broadcast_log_path(path=None):
    return Path(path or BROADCAST_LOG_PATH)


def open_broadcast_log(path=None, command=None):
    path = broadcast_log_path(path)
    path.parent.mkdir(parents=True, exist_ok=True)
    log_file = path.open("w", encoding="utf-8", buffering=1)
    log_file.write("RGC AI Broadcast Studio broadcast worker log\n")
    log_file.write("=" * 56 + "\n")
    command = command or broadcast_command()
    log_file.write(f"Command: {' '.join(str(part) for part in command)}\n\n")
    return log_file


def close_broadcast_log():
    global BROADCAST_LOG_FILE
    if BROADCAST_LOG_FILE:
        try:
            BROADCAST_LOG_FILE.close()
        except Exception:
            pass
    BROADCAST_LOG_FILE = None


def write_broadcast_pid(pid, path=BROADCAST_PID_PATH):
    path = Path(path)
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(str(int(pid)), encoding="utf-8")


def read_broadcast_pid(path=BROADCAST_PID_PATH):
    path = Path(path)
    if not path.exists():
        return None
    try:
        pid = int(path.read_text(encoding="utf-8").strip())
    except Exception:
        return None
    return pid if pid > 0 else None


def clear_broadcast_pid(path=BROADCAST_PID_PATH):
    try:
        Path(path).unlink(missing_ok=True)
    except Exception:
        pass


def running_broadcast_pids(root=ROOT):
    root_path = str(Path(root).resolve())
    app_path = str((Path(root) / "app.py").resolve())
    escaped_root_path = root_path.replace("'", "''")
    escaped_app_path = app_path.replace("'", "''")
    script = (
        "Get-CimInstance Win32_Process | "
        "Where-Object { "
        f"($_.CommandLine -like '*{escaped_app_path}*') -or "
        f"(($_.CommandLine -like '*app.py*') -and ($_.CommandLine -like '*{escaped_root_path}*')) "
        "} | "
        "ForEach-Object { $_.ProcessId }"
    )
    try:
        result = subprocess.run(
            ["powershell", "-NoProfile", "-Command", script],
            text=True,
            capture_output=True,
            check=False,
            creationflags=broadcast_creation_flags(),
        )
    except Exception:
        return []
    if result.returncode != 0:
        return []
    pids = []
    for line in result.stdout.splitlines():
        line = line.strip()
        if line.isdigit():
            pids.append(int(line))
    return pids


def stop_broadcast_processes(pids):
    stopped = 0
    for pid in pids:
        result = subprocess.run(
            ["taskkill", "/PID", str(pid), "/T", "/F"],
            text=True,
            capture_output=True,
            check=False,
            creationflags=broadcast_creation_flags(),
        )
        if result.returncode == 0:
            stopped += 1
    return stopped


def is_process_running(process):
    return process is not None and process.poll() is None


def sim_racer_hub_import_command(
    source,
    league_id="",
    series_id="",
    season_id="",
    track_name="",
    min_starts="1",
    first_schedule_id="",
    output="league/season.csv",
    drivers_output="league/drivers.csv",
    schedule_output="league/race_schedule.csv",
    career_mode=False,
    dry_run=False,
    drivers_only=False,
    schedule_only=False,
):
    command = [
        sys.executable,
        str(ROOT / "tools" / "sim_racer_hub_import.py"),
        source,
        "--bulk",
    ]
    if league_id:
        command.extend(["--league-id", str(league_id)])
    if series_id:
        command.extend(["--series-id", str(series_id)])
    if season_id and not career_mode:
        command.extend(["--season-id", str(season_id)])
    if track_name:
        command.extend(["--track-name", str(track_name)])
    if min_starts:
        command.extend(["--min-starts", str(min_starts)])
    if first_schedule_id and schedule_only:
        command.extend(["--first-schedule-id", str(first_schedule_id)])
    if output:
        command.extend(["--output", str(output)])
    if drivers_only:
        command.append("--drivers-only")
        command.extend(["--drivers-output", str(drivers_output)])
    if schedule_only:
        command.append("--schedule-only")
        command.extend(["--schedule-output", str(schedule_output)])
    if dry_run:
        command.append("--dry-run")
    return command


def run_sim_racer_hub_import(
    source,
    league_id="",
    series_id="",
    season_id="",
    track_name="",
    min_starts="1",
    first_schedule_id="",
    output="league/season.csv",
    drivers_output="league/drivers.csv",
    schedule_output="league/race_schedule.csv",
    career_mode=False,
    dry_run=False,
    drivers_only=False,
    schedule_only=False,
):
    command = sim_racer_hub_import_command(
        source=source,
        league_id=league_id,
        series_id=series_id,
        season_id=season_id,
        track_name=track_name,
        min_starts=min_starts,
        first_schedule_id=first_schedule_id,
        output=output,
        drivers_output=drivers_output,
        schedule_output=schedule_output,
        career_mode=career_mode,
        dry_run=dry_run,
        drivers_only=drivers_only,
        schedule_only=schedule_only,
    )
    return subprocess.run(
        command,
        cwd=ROOT,
        text=True,
        capture_output=True,
        check=False,
        creationflags=broadcast_creation_flags(),
    )


def velocity_league_import_command(
    url,
    series_name="",
    stats_output="league/season.csv",
    career_output="league/career.csv",
    drivers_output="league/drivers.csv",
    schedule_output="league/race_schedule.csv",
    manager_folder="",
    dry_run=False,
):
    command = [
        sys.executable,
        str(ROOT / "tools" / "velocity_league_import.py"),
        str(url),
    ]
    if series_name:
        command.extend(["--series", str(series_name)])
    if stats_output:
        command.extend(["--stats-output", str(stats_output)])
    if career_output:
        command.extend(["--career-output", str(career_output)])
    if drivers_output:
        command.extend(["--drivers-output", str(drivers_output)])
    if schedule_output:
        command.extend(["--schedule-output", str(schedule_output)])
    if manager_folder:
        command.extend(["--manager-folder", str(manager_folder)])
    if dry_run:
        command.append("--dry-run")
    return command


def run_velocity_league_import(
    url,
    series_name="",
    stats_output="league/season.csv",
    career_output="league/career.csv",
    drivers_output="league/drivers.csv",
    schedule_output="league/race_schedule.csv",
    manager_folder="",
    dry_run=False,
):
    return subprocess.run(
        velocity_league_import_command(
            url=url,
            series_name=series_name,
            stats_output=stats_output,
            career_output=career_output,
            drivers_output=drivers_output,
            schedule_output=schedule_output,
            manager_folder=manager_folder,
            dry_run=dry_run,
        ),
        cwd=ROOT,
        text=True,
        capture_output=True,
        check=False,
        creationflags=broadcast_creation_flags(),
    )


def launch_broadcast(command=None):
    global BROADCAST_PROCESS, BROADCAST_LOG_FILE
    if is_process_running(BROADCAST_PROCESS):
        return BROADCAST_PROCESS

    env = os.environ.copy()
    close_broadcast_log()
    command = command or broadcast_command()
    BROADCAST_LOG_FILE = open_broadcast_log(command=command)
    BROADCAST_PROCESS = subprocess.Popen(
        command,
        cwd=ROOT,
        env=env,
        stdout=BROADCAST_LOG_FILE,
        stderr=subprocess.STDOUT,
        creationflags=broadcast_creation_flags(),
    )
    write_broadcast_pid(BROADCAST_PROCESS.pid)
    return BROADCAST_PROCESS


def stop_broadcast():
    global BROADCAST_PROCESS
    pids_to_stop = []
    if is_process_running(BROADCAST_PROCESS):
        pids_to_stop.append(BROADCAST_PROCESS.pid)

    saved_pid = read_broadcast_pid()
    if saved_pid:
        pids_to_stop.append(saved_pid)

    external_pids = running_broadcast_pids()
    for pid in external_pids:
        pids_to_stop.append(pid)
    pids_to_stop = sorted(set(pid for pid in pids_to_stop if pid))
    stopped_count = stop_broadcast_processes(pids_to_stop)

    clear_broadcast_pid()
    BROADCAST_PROCESS = None
    close_broadcast_log()
    return stopped_count


def has_running_broadcast():
    return (
        is_process_running(BROADCAST_PROCESS)
        or bool(read_broadcast_pid())
        or bool(running_broadcast_pids())
    )


def set_windows_app_user_model_id(app_id=WINDOWS_APP_USER_MODEL_ID):
    """Give the Studio a stable Windows taskbar identity when launched by Python."""

    if sys.platform != "win32":
        return False
    try:
        import ctypes

        ctypes.windll.shell32.SetCurrentProcessExplicitAppUserModelID(app_id)
        return True
    except Exception:
        return False


def set_window_icon(root):
    """Use the branded RGC icon for the Studio window and taskbar when possible."""

    icon_set = False
    if WINDOW_ICON_PATH.exists():
        try:
            root.iconbitmap(default=str(WINDOW_ICON_PATH))
            icon_set = True
        except Exception:
            pass

    if WINDOW_ICON_IMAGE_PATH.exists():
        try:
            import tkinter as tk

            icon_image = tk.PhotoImage(file=str(WINDOW_ICON_IMAGE_PATH))
            root.iconphoto(True, icon_image)
            root._rgc_icon_image = icon_image
            icon_set = True
        except Exception:
            pass

    return icon_set


def run_gui():
    import tkinter as tk
    from tkinter import filedialog
    from tkinter import ttk

    existing = launcher_defaults(load_env_file())
    set_windows_app_user_model_id()
    root = tk.Tk()
    root.title("RGC AI Broadcast Studio")
    root.geometry("1040x720")
    root.minsize(920, 640)
    root.configure(bg=DARK_BG)
    set_window_icon(root)

    style = ttk.Style(root)
    style.theme_use("clam")
    style.configure("TNotebook", background=DARK_BG, borderwidth=0)
    style.configure(
        "TNotebook.Tab",
        background=PANEL_BG,
        foreground=MUTED_FG,
        padding=(18, 8),
        borderwidth=0,
    )
    style.map(
        "TNotebook.Tab",
        background=[("selected", ACCENT)],
        foreground=[("selected", TEXT_FG)],
    )

    def label(parent, **kwargs):
        defaults = {"bg": kwargs.pop("bg", DARK_BG), "fg": kwargs.pop("fg", TEXT_FG)}
        defaults.update(kwargs)
        return tk.Label(parent, **defaults)

    def frame(parent, **kwargs):
        defaults = {"bg": kwargs.pop("bg", DARK_BG)}
        defaults.update(kwargs)
        return tk.Frame(parent, **defaults)

    def entry(parent, **kwargs):
        defaults = {
            "bg": FIELD_BG,
            "fg": TEXT_FG,
            "insertbackground": TEXT_FG,
            "relief": "flat",
            "highlightthickness": 1,
            "highlightbackground": "#26384c",
            "highlightcolor": ACCENT,
        }
        defaults.update(kwargs)
        return tk.Entry(parent, **defaults)

    def button(parent, text, command, color=ACCENT):
        return tk.Button(
            parent,
            text=text,
            command=command,
            bg=color,
            fg="white",
            activebackground=ACCENT_HOVER,
            activeforeground="white",
            relief="flat",
            padx=12,
            pady=7,
            font=("Segoe UI", 9, "bold"),
        )

    def scrollable_tab(parent):
        container = frame(parent, bg=PANEL_BG)
        container.pack(fill="both", expand=True)

        canvas = tk.Canvas(
            container,
            bg=PANEL_BG,
            borderwidth=0,
            highlightthickness=0,
        )
        scrollbar = tk.Scrollbar(container, orient="vertical", command=canvas.yview)
        content = frame(canvas, bg=PANEL_BG)
        window_id = canvas.create_window((0, 0), window=content, anchor="nw")

        def update_scroll_region(_event=None):
            canvas.configure(scrollregion=canvas.bbox("all"))

        def resize_content(event):
            canvas.itemconfigure(window_id, width=event.width)

        def on_mousewheel(event):
            if event.widget.winfo_toplevel() != root:
                return
            delta = int(-1 * (event.delta / 120))
            canvas.yview_scroll(delta, "units")

        def on_linux_scroll_up(event):
            if event.widget.winfo_toplevel() == root:
                canvas.yview_scroll(-1, "units")

        def on_linux_scroll_down(event):
            if event.widget.winfo_toplevel() == root:
                canvas.yview_scroll(1, "units")

        content.bind("<Configure>", update_scroll_region)
        canvas.bind("<Configure>", resize_content)
        root.bind_all("<MouseWheel>", on_mousewheel)
        root.bind_all("<Button-4>", on_linux_scroll_up)
        root.bind_all("<Button-5>", on_linux_scroll_down)
        canvas.configure(yscrollcommand=scrollbar.set)

        canvas.pack(side="left", fill="both", expand=True)
        scrollbar.pack(side="right", fill="y")
        return content

    def disable_combobox_mousewheel(widget):
        widget.bind("<MouseWheel>", lambda _event: "break")
        widget.bind("<Button-4>", lambda _event: "break")
        widget.bind("<Button-5>", lambda _event: "break")

    header_bar = frame(root)
    header_bar.pack(fill="x", padx=18, pady=(10, 6))
    header_text = frame(header_bar)
    header_text.pack(side="left", fill="x", expand=True)
    label(
        header_text,
        text=f"RGC AI Broadcast Studio v{APP_VERSION}",
        font=("Segoe UI", 14, "bold"),
        anchor="w",
    ).pack(anchor="w")
    label(
        header_text,
        text="Configure your broadcast, league profiles, stats, voices, and overlay.",
        font=("Segoe UI", 9),
        fg=MUTED_FG,
        anchor="w",
    ).pack(anchor="w")

    link_bar = frame(header_bar)
    link_bar.pack(side="right")
    button(
        link_bar,
        text="RGC Discord",
        command=lambda: open_external_link(RGC_DISCORD_URL),
        color="#5865f2",
    ).pack(side="left", padx=5)
    button(
        link_bar,
        text="RGC Website",
        command=lambda: open_external_link(RGC_WEBSITE_URL),
        color="#334b64",
    ).pack(side="left", padx=5)
    button(
        link_bar,
        text="Check for Updates",
        command=lambda: check_for_updates(),
        color="#334b64",
    ).pack(side="left", padx=5)

    main_page = scrollable_tab(root)

    status = tk.StringVar(
        value=(
            "Launcher ready. Broadcast is not started from this window yet. "
            f"Settings file: {ENV_PATH}"
        )
    )

    profile_bar = frame(main_page, bg=PANEL_BG)
    profile_bar.pack(fill="x", padx=18, pady=(0, 8))
    label(
        profile_bar,
        text="Profile",
        bg=PANEL_BG,
        fg=MUTED_FG,
        font=("Segoe UI", 9, "bold"),
    ).pack(side="left", padx=(10, 6), pady=8)
    profile_var = tk.StringVar(value="")
    profile_combo = ttk.Combobox(
        profile_bar,
        textvariable=profile_var,
        values=list_profiles(),
        width=28,
    )
    disable_combobox_mousewheel(profile_combo)
    profile_combo.pack(side="left", padx=4, pady=8)
    button(
        profile_bar,
        text="Load",
        command=lambda: load_selected_profile(),
        color="#334b64",
    ).pack(side="left", padx=4, pady=8)
    button(
        profile_bar,
        text="Delete",
        command=lambda: delete_selected_profile(),
        color=STOP_RED,
    ).pack(side="left", padx=4, pady=8)
    label(
        profile_bar,
        text="New Profile Name",
        bg=PANEL_BG,
        fg=MUTED_FG,
    ).pack(side="left", padx=(14, 6), pady=8)
    profile_name_var = tk.StringVar(value="")
    profile_name_entry = entry(profile_bar, textvariable=profile_name_var, width=24)
    profile_name_entry.pack(side="left", padx=4, pady=8)
    button(
        profile_bar,
        text="Create Profile",
        command=lambda: create_profile_from_name(),
        color="#3d7a46",
    ).pack(side="left", padx=4, pady=8)

    broadcast_bar = frame(main_page, bg=PANEL_BG)
    broadcast_bar.pack(fill="x", padx=18, pady=(4, 6))

    profile_action_bar = frame(main_page, bg=PANEL_BG)
    profile_action_bar.pack(fill="x", padx=18, pady=(0, 10))

    health_panel = frame(main_page, bg=PANEL_BG)
    health_panel.pack(fill="x", padx=18, pady=(0, 10))
    health_header = frame(health_panel, bg=PANEL_BG)
    health_header.pack(fill="x", padx=12, pady=(10, 4))
    label(
        health_header,
        text="Broadcast Health",
        bg=PANEL_BG,
        fg=TEXT_FG,
        font=("Segoe UI", 11, "bold"),
    ).pack(side="left")
    health_summary = tk.StringVar(value="Not checked yet.")
    label(
        health_header,
        textvariable=health_summary,
        bg=PANEL_BG,
        fg=MUTED_FG,
    ).pack(side="left", padx=(12, 0))
    button(
        health_header,
        text="Refresh Health",
        command=lambda: refresh_health(),
        color="#334b64",
    ).pack(side="right")
    health_rows_frame = frame(health_panel, bg=PANEL_BG)
    health_rows_frame.pack(fill="x", padx=12, pady=(0, 10))
    health_row_widgets = []
    health_panel.pack_forget()

    notebook = ttk.Notebook(main_page)
    notebook.pack(fill="x", padx=18)
    health_panel.pack(fill="x", padx=18, pady=(8, 10))

    settings_tab = frame(notebook, bg=PANEL_BG)
    league_manager_tab = frame(notebook, bg=PANEL_BG)
    league_tab = frame(notebook, bg=PANEL_BG)
    help_tab = frame(notebook, bg=PANEL_BG)
    notebook.add(settings_tab, text="Broadcast Settings")
    notebook.add(league_manager_tab, text="League Manager")
    notebook.add(league_tab, text="League Data / Imports")
    notebook.add(help_tab, text="Help / Setup Guide")

    settings_content = settings_tab
    league_manager_content = league_manager_tab
    league_content = league_tab
    help_content = help_tab

    settings_intro = frame(settings_content, bg="#0b1520")
    settings_intro.pack(fill="x", padx=14, pady=(12, 0))
    label(
        settings_intro,
        text="Broadcast Setup",
        bg="#0b1520",
        fg=TEXT_FG,
        font=("Segoe UI", 13, "bold"),
        anchor="w",
    ).pack(fill="x", padx=12, pady=(10, 2))
    label(
        settings_intro,
        text=(
            "Fill in the required services first, then add branding, league data, Discord reports, "
            "and race-control options. Fields marked with * are important for a full league broadcast. "
            "Save Settings before starting."
        ),
        bg="#0b1520",
        fg=MUTED_FG,
        anchor="w",
        justify="left",
        wraplength=900,
    ).pack(fill="x", padx=12, pady=(0, 10))

    settings_frame = frame(settings_content, bg=PANEL_BG)
    settings_frame.pack(fill="both", expand=True, padx=14, pady=12)

    entries = {}
    settings_rows_by_key = {}
    sim_racer_hub_state = {"entries": {}, "career_mode": None, "velocity_entries": {}}
    league_tab_state = {}
    league_manager_state = {}
    settings_grid_row = 0

    def add_settings_section(title):
        nonlocal settings_grid_row
        section = frame(settings_frame, bg="#152233")
        section.grid(
            row=settings_grid_row,
            column=0,
            columnspan=3,
            sticky="ew",
            pady=(12 if settings_grid_row else 0, 6),
        )
        label(
            section,
            text=title,
            bg="#152233",
            fg=TEXT_FG,
            font=("Segoe UI", 10, "bold"),
            anchor="w",
        ).pack(fill="x", padx=10, pady=6)
        settings_grid_row += 1

    def add_settings_hint(text):
        nonlocal settings_grid_row
        label(
            settings_frame,
            text=text,
            anchor="w",
            bg=PANEL_BG,
            fg=MUTED_FG,
            wraplength=760,
            justify="left",
        ).grid(
            row=settings_grid_row,
            column=1,
            columnspan=2,
            sticky="ew",
            pady=(0, 8),
        )
        settings_grid_row += 1

    add_settings_section("Broadcast Links")
    for link_label, link_value, copied_message in (
        ("Streamlabs / OBS Link", DEFAULT_OVERLAY_URL, "Copied overlay browser-source link for Streamlabs / OBS."),
        ("Producer Assist (This PC)", DEFAULT_PRODUCER_URL, "Copied local Producer Assist link."),
    ):
        label(
            settings_frame,
            text=link_label,
            anchor="w",
            width=24,
            bg=PANEL_BG,
            fg=MUTED_FG,
        ).grid(row=settings_grid_row, column=0, sticky="w", pady=3)
        link_var = tk.StringVar(value=link_value)
        link_entry = entry(
            settings_frame,
            textvariable=link_var,
            width=72,
            state="readonly",
            readonlybackground=FIELD_BG,
        )
        link_entry.grid(row=settings_grid_row, column=1, sticky="ew", pady=3)
        button(
            settings_frame,
            text="Copy Link",
            command=lambda value=link_value, message=copied_message: (
                copy_to_clipboard(root, value),
                status.set(message),
            ),
            color="#334b64",
        ).grid(row=settings_grid_row, column=2, padx=(8, 0), sticky="w")
        settings_grid_row += 1

    for key, _default in LAUNCHER_FIELDS:
        if key == "STUDIO_VOLUME":
            continue
        if key in BROADCAST_FIELD_SECTIONS:
            add_settings_section(BROADCAST_FIELD_SECTIONS[key])
        settings_rows_by_key[key] = settings_grid_row
        label_text = BROADCAST_FIELD_LABELS.get(key, key.replace("_", " ").title())
        if key in IMPORTANT_SETUP_FIELDS:
            label_text = f"{label_text}  *"
        label(
            settings_frame,
            text=label_text,
            anchor="w",
            width=24,
            bg=PANEL_BG,
            fg=MUTED_FG,
        ).grid(
            row=settings_grid_row,
            column=0,
            sticky="w",
            pady=3,
        )
        entry_value = None
        if key == "DRIVER_MODE":
            driver_mode_value = tk.StringVar(value=bool_setting_text(existing, key, _default))
            entry_widget = tk.Checkbutton(
                settings_frame,
                text="I am driving — record this session silently for a later replay broadcast",
                variable=driver_mode_value,
                onvalue="true",
                offvalue="false",
                bg=PANEL_BG,
                fg=TEXT_FG,
                activebackground=PANEL_BG,
                activeforeground=TEXT_FG,
                selectcolor=FIELD_BG,
                anchor="w",
            )
            entry_value = driver_mode_value
        elif key == "OVERLAY_LEADERBOARD_STYLE":
            entry_widget = ttk.Combobox(
                settings_frame,
                values=("side", "ticker", "flo", "brazen"),
                width=69,
                state="readonly",
            )
            entry_widget.set(existing.get(key, "side") or "side")
        elif key == "OPENAI_MODEL":
            entry_widget = ttk.Combobox(
                settings_frame,
                values=OPENAI_MODEL_CHOICES,
                width=69,
            )
            entry_widget.set(existing.get(key, "gpt-5.6-terra") or "gpt-5.6-terra")
        elif key in BOOLEAN_SETTING_KEYS:
            entry_widget = ttk.Combobox(
                settings_frame,
                values=("false", "true"),
                width=69,
                state="readonly",
            )
            entry_widget.set(bool_setting_text(existing, key, _default))
        else:
            entry_widget = entry(settings_frame, width=72)
            entry_widget.insert(0, existing.get(key, ""))
        if isinstance(entry_widget, ttk.Combobox):
            disable_combobox_mousewheel(entry_widget)
        entry_widget.grid(row=settings_grid_row, column=1, sticky="ew", pady=3)
        entries[key] = entry_value or entry_widget
        settings_grid_row += 1

        if key in INLINE_HELP_FIELDS and key in BROADCAST_FIELD_HELP:
            add_settings_hint(BROADCAST_FIELD_HELP[key])

        if key == "SPONSOR_READ_MESSAGE":
            add_settings_hint(
                "Optional exact script for the sponsor reads. It can use {sponsor} and {cause}. "
                "The app reads Sponsor 1 first, then Sponsor 2, then Sponsor 3 during later sponsor breaks. "
                "The cause/awareness read is paired with the active sponsor. If this script is blank, "
                "RGC AI Broadcast Studio writes a natural read from the sponsor name and cause."
            )
        if key == "SPONSOR_READ_CAUSE_READ":
            add_settings_hint(
                "This is the actual sentence the broadcaster says for the cause/awareness. "
                "Example: Autism Awareness is about understanding, acceptance, and supporting families in our racing community."
            )


    def choose_graphics_for_field(field_name, title, status_label):
        paths = filedialog.askopenfilenames(
            title=title,
            filetypes=[
                ("Image files", "*.png *.jpg *.jpeg *.webp *.gif *.svg"),
                ("All files", "*.*"),
            ],
        )
        asset_paths = install_overlay_brand_graphics(paths)
        if not asset_paths:
            status.set("No graphics were copied. Choose PNG, JPG, WEBP, GIF, or SVG files.")
            return
        field = entries[field_name]
        field.delete(0, "end")
        field.insert(0, ",".join(asset_paths))
        status.set(f"Added {len(asset_paths)} graphic(s) for {status_label}.")

    def choose_single_graphic_for_field(field_name, title, status_label):
        paths = filedialog.askopenfilenames(
            title=title,
            filetypes=[
                ("Image files", "*.png *.jpg *.jpeg *.webp *.gif *.svg"),
                ("All files", "*.*"),
            ],
        )
        asset_paths = install_overlay_brand_graphics(paths[:1])
        if not asset_paths:
            status.set("No graphic was copied. Choose a PNG, JPG, WEBP, GIF, or SVG file.")
            return
        field = entries[field_name]
        field.delete(0, "end")
        field.insert(0, asset_paths[0])
        status.set(f"Set graphic for {status_label}.")

    def choose_video_for_field(field_name, title, status_label):
        path = filedialog.askopenfilename(
            title=title,
            filetypes=[
                ("Video files", "*.mp4 *.mov *.mkv *.webm *.avi"),
                ("All files", "*.*"),
            ],
        )
        if not path:
            return
        asset_path = install_overlay_commercial_video(path)
        if not asset_path:
            status.set("No video was copied. Choose an MP4, MOV, MKV, WEBM, or AVI file.")
            return
        field = entries[field_name]
        field.delete(0, "end")
        field.insert(0, asset_path)
        status.set(f"Set commercial video for {status_label}. It will play full-screen when that sponsor read is used.")

    def choose_music_playlist(field_name, title, status_label):
        paths = filedialog.askopenfilenames(
            title=title,
            filetypes=[
                ("Audio files", "*.mp3 *.wav *.m4a *.aac *.flac *.wma"),
                ("All files", "*.*"),
            ],
        )
        if not paths:
            return
        field = entries[field_name]
        field.delete(0, "end")
        field.insert(0, format_playlist_paths(paths))
        status.set(f"Added {len(paths)} {status_label} music file(s). Save settings before starting.")

    def choose_single_audio(field_name, title):
        if field_name in ("NATIONAL_ANTHEM_AUDIO", "QUALIFYING_MUSIC_PLAYLIST"):
            selected = filedialog.askopenfilenames(
                title=title,
                filetypes=[
                    ("Audio files", "*.mp3 *.wav *.m4a *.aac *.flac *.wma"),
                    ("All files", "*.*"),
                ],
            )
        else:
            selected = filedialog.askopenfilename(
                title=title,
                filetypes=[
                    ("Audio files", "*.mp3 *.wav *.m4a *.aac *.flac *.wma"),
                    ("All files", "*.*"),
                ],
            )
        if not selected:
            return
        updated_values = apply_audio_file_selection(
            collect_values(),
            field_name,
            selected,
        )
        for key, value in updated_values.items():
            if key not in entries:
                continue
            field = entries[key]
            field.delete(0, "end")
            field.insert(0, value)
        if field_name == "QUALIFYING_MUSIC_PLAYLIST":
            count = len(selected) if isinstance(selected, tuple) else 1
            status.set(
                f"Set {count} qualifying music file(s). Save settings before starting."
            )
            return
        status.set(f"Set {field_name}. Save settings before starting.")

    button(
        settings_frame,
        text="Choose Logo",
        command=lambda: choose_single_graphic_for_field(
            "OVERLAY_SERIES_LOGO",
            "Choose series logo",
            "the series",
        ),
        color="#334b64",
    ).grid(row=settings_rows_by_key["OVERLAY_SERIES_LOGO"], column=2, padx=(8, 0), sticky="w")
    button(
        settings_frame,
        text="Choose Logo",
        command=lambda: choose_single_graphic_for_field(
            "SPONSOR_READ_CAUSE_LOGO",
            "Choose cause / awareness logo",
            "the cause / awareness sponsor",
        ),
        color="#334b64",
    ).grid(row=settings_rows_by_key["SPONSOR_READ_CAUSE_LOGO"], column=2, padx=(8, 0), sticky="w")
    for sponsor_index in range(1, 6):
        logo_key = f"RACE_SPONSOR_{sponsor_index}_LOGO"
        video_key = f"RACE_SPONSOR_{sponsor_index}_VIDEO"
        if logo_key in settings_rows_by_key:
            button(
                settings_frame,
                text="Choose Logo",
                command=lambda key=logo_key, index=sponsor_index: choose_single_graphic_for_field(
                    key,
                    f"Choose Sponsor {index} logo",
                    f"Sponsor {index}",
                ),
                color="#334b64",
            ).grid(row=settings_rows_by_key[logo_key], column=2, padx=(8, 0), sticky="w")
        if video_key in settings_rows_by_key:
            button(
                settings_frame,
                text="Choose Video",
                command=lambda key=video_key, index=sponsor_index: choose_video_for_field(
                    key,
                    f"Choose Sponsor {index} commercial video",
                    f"Sponsor {index}",
                ),
                color="#334b64",
            ).grid(row=settings_rows_by_key[video_key], column=2, padx=(8, 0), sticky="w")
    for graphic_key, title, label_text in (
        (
            "STARTING_LINEUP_SPONSOR_LOGO",
            "Choose starting lineup sponsor logo",
            "the starting lineup sponsor",
        ),
        (
            "FINAL_RESULTS_SPONSOR_LOGO",
            "Choose final results sponsor logo",
            "the final results sponsor",
        ),
        (
            "CAUTION_REVIEW_SLATE_GRAPHIC",
            "Choose caution review slate image",
            "the caution review slate",
        ),
    ):
        if graphic_key in settings_rows_by_key:
            button(
                settings_frame,
                text="Choose Image",
                command=lambda key=graphic_key, picker_title=title, status_label=label_text: choose_single_graphic_for_field(
                    key,
                    picker_title,
                    status_label,
                ),
                color="#334b64",
            ).grid(row=settings_rows_by_key[graphic_key], column=2, padx=(8, 0), sticky="w")
    button(
        settings_frame,
        text="Choose Practice Music",
        command=lambda: choose_music_playlist(
            "PRACTICE_MUSIC_PLAYLIST",
            "Choose practice music files",
            "practice",
        ),
        color="#334b64",
    ).grid(row=settings_rows_by_key["PRACTICE_MUSIC_PLAYLIST"], column=2, padx=(8, 0), sticky="w")
    button(
        settings_frame,
        text="Choose Qualifying Music",
        command=lambda: choose_music_playlist(
            "QUALIFYING_MUSIC_PLAYLIST",
            "Choose qualifying music files",
            "qualifying",
        ),
        color="#334b64",
    ).grid(row=settings_rows_by_key["QUALIFYING_MUSIC_PLAYLIST"], column=2, padx=(8, 0), sticky="w")
    button(
        settings_frame,
        text="Choose Caution Audio",
        command=lambda: choose_single_audio("CAUTION_REPLAY_AUDIO", "Choose caution replay audio"),
        color="#334b64",
    ).grid(row=settings_rows_by_key["CAUTION_REPLAY_AUDIO"], column=2, padx=(8, 0), sticky="w")

    def choose_recorded_broadcast():
        selected = filedialog.askopenfilename(
            title="Choose Driver Mode recording",
            initialdir=str(ROOT / "recordings"),
            filetypes=(("RGC broadcast recording", "*.jsonl"), ("All files", "*.*")),
        )
        if not selected:
            return
        if str(selected).lower().endswith(".events.jsonl"):
            messagebox.showerror(
                "Choose the main recording",
                "Select the matching broadcast_capture_*.jsonl file, not the .events.jsonl sidecar.",
            )
            return
        widget = entries["RECORDED_BROADCAST_FILE"]
        widget.delete(0, "end")
        widget.insert(0, selected)
        status.set("Recorded broadcast selected. Save Settings, open its iRacing replay, then click Play Recorded Broadcast.")

    button(
        settings_frame,
        text="Choose Recording",
        command=choose_recorded_broadcast,
        color="#334b64",
    ).grid(row=settings_rows_by_key["RECORDED_BROADCAST_FILE"], column=2, padx=(8, 0), sticky="w")

    settings_frame.columnconfigure(1, weight=1)

    label(main_page, textvariable=status, anchor="w", fg=MUTED_FG).pack(
        fill="x",
        padx=18,
        pady=(8, 0),
    )

    def collect_values():
        values = {key: entry.get().strip() for key, entry in entries.items()}
        values["STUDIO_VOLUME"] = str(int(volume_var.get()))
        values["OVERLAY_RACE_SPONSOR"] = values.get("RACE_SPONSOR_1_NAME", "")
        values["SPONSOR_READ_NAME"] = values.get("RACE_SPONSOR_1_NAME", "")
        values["SPONSOR_READ_NAME_2"] = values.get("RACE_SPONSOR_2_NAME", "")
        values["SPONSOR_READ_NAME_3"] = values.get("RACE_SPONSOR_3_NAME", "")
        values["SPONSOR_READ_CAUSE"] = values.get("SPONSOR_READ_CAUSE_NAME", "")
        values["SPONSOR_READ_MESSAGE"] = values.get("RACE_SPONSOR_1_READ", "")
        values["NATIONAL_ANTHEM_AUDIO"] = values.get("QUALIFYING_MUSIC_PLAYLIST", "")
        values["USE_NATIONAL_ANTHEM"] = (
            "true" if values.get("QUALIFYING_MUSIC_PLAYLIST", "") else "false"
        )
        for key, widget in sim_racer_hub_state["entries"].items():
            values[key] = widget.get().strip()
        for key, widget in sim_racer_hub_state.get("velocity_entries", {}).items():
            values[key] = widget.get().strip()
        career_mode = sim_racer_hub_state.get("career_mode")
        if career_mode is not None:
            values["SIMRACERHUB_CAREER_MODE"] = "true" if career_mode.get() else "false"
        return values

    def apply_values_to_form(values):
        values = launcher_defaults(values)
        values.update(velocity_output_defaults(values))
        for key, widget in entries.items():
            if hasattr(widget, "set"):
                widget.set(values.get(key, ""))
            else:
                widget.delete(0, "end")
                widget.insert(0, values.get(key, ""))
        for key, widget in sim_racer_hub_state["entries"].items():
            widget.delete(0, "end")
            widget.insert(0, values.get(key, ""))
        for key, widget in sim_racer_hub_state.get("velocity_entries", {}).items():
            widget.delete(0, "end")
            widget.insert(0, values.get(key, ""))
        career_mode = sim_racer_hub_state.get("career_mode")
        if career_mode is not None:
            career_mode.set(setting_enabled(values, "SIMRACERHUB_CAREER_MODE", "false"))
        volume_var.set(int(values.get("STUDIO_VOLUME", "65") or 65))
        update_volume_label(volume_var.get())
        sync_league_editor = league_tab_state.get("sync_driver_csv_from_settings")
        if sync_league_editor:
            sync_league_editor(values)
        refresh_health()

    def refresh_profile_list():
        profile_combo["values"] = list_profiles()
        status.set("Profile list refreshed.")

    def save_settings():
        values = collect_values()
        save_env_file(values)
        profile_name = profile_var.get().strip()
        if profile_name:
            path = save_profile(profile_name, values)
            refresh_profile_list()
            status.set(f"Saved settings and updated profile: {path.name}")
        else:
            status.set(f"Saved settings to {ENV_PATH}")
        refresh_health()

    def create_profile_from_name():
        name = profile_name_var.get().strip()
        if not name:
            messagebox.showerror(
                "Missing profile name",
                "Type a name in New Profile Name, then click Create Profile.",
            )
            return
        clean_name = sanitize_profile_name(name)
        clean_values = new_profile_defaults(clean_name)
        ensure_profile_league_files(clean_name, root=ROOT)
        manager_folder = ROOT / "league" / league_folder_slug(clean_name)
        save_league_profile(manager_folder / "league.json", LeagueProfile(name=clean_name))
        save_schedule(manager_folder / "schedule.json", [])
        save_scoring_system(manager_folder / "scoring.json", default_scoring_system())
        profile_var.set(clean_name)
        profile_name_var.set("")
        apply_values_to_form(clean_values)
        save_env_file(clean_values)
        path = save_profile(clean_name, clean_values)
        refresh_manager = league_manager_state.get("load_profile")
        if refresh_manager:
            refresh_manager()
        refresh_league_stats = league_tab_state.get("refresh_driver_statistics")
        if refresh_league_stats:
            refresh_league_stats()
        refresh_profile_list()
        profile_var.set(clean_name)
        status.set(f"Created clean profile with default settings and separate league files: {path.name}")

    def load_selected_profile():
        name = profile_var.get().strip()
        if not name:
            messagebox.showerror("Missing profile", "Choose a profile to load first.")
            return
        try:
            values = load_profile(name)
        except Exception as error:
            messagebox.showerror("Profile load failed", str(error))
            return
        ensure_profile_league_files(name, root=ROOT)
        apply_values_to_form(values)
        refresh_manager = league_manager_state.get("load_profile")
        if refresh_manager:
            refresh_manager()
        refresh_league_stats = league_tab_state.get("refresh_driver_statistics")
        if refresh_league_stats:
            refresh_league_stats()
        migrated_values = collect_values()
        save_env_file(migrated_values)
        save_profile(name, migrated_values)
        status.set(
            f"Loaded profile '{name}', migrated its league data paths when needed, "
            "and saved it as the active broadcast settings."
        )

    def delete_selected_profile():
        name = profile_var.get().strip()
        if not name:
            messagebox.showerror("Missing profile", "Choose a profile to delete first.")
            return
        if not messagebox.askyesno(
            "Delete profile",
            f"Delete the saved profile '{name}'? This only removes that profile file.",
        ):
            return
        try:
            path = delete_profile(name)
        except Exception as error:
            messagebox.showerror("Profile delete failed", str(error))
            return
        profile_var.set("")
        profile_name_var.set("")
        refresh_profile_list()
        status.set(f"Deleted profile: {path.name}")

    def refresh_health():
        for widget in health_rows_frame.winfo_children():
            widget.destroy()
        health_row_widgets.clear()

        rows = build_health_status(
            collect_values(),
            root=ROOT,
            broadcast_running=has_running_broadcast(),
        )
        level_colors = {
            "ok": GREEN,
            "warn": "#d19a2a",
            "off": MUTED_FG,
        }
        ok_count = sum(1 for _name, _state, _detail, level in rows if level == "ok")
        warn_count = sum(1 for _name, _state, _detail, level in rows if level == "warn")
        health_summary.set(f"{ok_count} ready | {warn_count} need attention")

        for index, (name, state_text, detail, level) in enumerate(rows):
            row_frame = frame(health_rows_frame, bg=PANEL_BG)
            row_frame.grid(
                row=index // 2,
                column=index % 2,
                sticky="ew",
                padx=(0, 14),
                pady=3,
            )
            health_rows_frame.columnconfigure(index % 2, weight=1)
            label(
                row_frame,
                text=name,
                width=16,
                anchor="w",
                bg=PANEL_BG,
                fg=MUTED_FG,
                font=("Segoe UI", 9, "bold"),
            ).pack(side="left")
            label(
                row_frame,
                text=state_text,
                width=12,
                anchor="w",
                bg=PANEL_BG,
                fg=level_colors.get(level, MUTED_FG),
                font=("Segoe UI", 9, "bold"),
            ).pack(side="left")
            label(
                row_frame,
                text=detail,
                anchor="w",
                bg=PANEL_BG,
                fg=TEXT_FG,
            ).pack(side="left", fill="x", expand=True)
            health_row_widgets.append(row_frame)
        status.set("Broadcast health refreshed.")

    def create_league_files():
        profile_name = profile_var.get().strip() or profile_name_var.get().strip()
        created, paths = ensure_profile_league_files(profile_name)
        drivers_csv, season_stats_csv, career_stats_csv, race_schedule_csv = paths
        sync_league_editor = league_tab_state.get("sync_driver_csv_paths")
        if sync_league_editor:
            sync_league_editor(drivers_csv, season_stats_csv, career_stats_csv, race_schedule_csv)
        display_name = sanitize_profile_name(profile_name) or "default league"
        if created:
            messagebox.showinfo(
                "League files created",
                f"Created league files for {display_name}:\n\n" + "\n".join(created),
            )
        else:
            messagebox.showinfo(
                "League files ready",
                f"League files for {display_name} already exist:\n\n"
                f"{drivers_csv}\n{season_stats_csv}\n{career_stats_csv}\n{race_schedule_csv}",
            )

    def start_broadcast():
        save_settings()
        current_values = collect_values()
        if (
            not setting_enabled(current_values, "DRIVER_MODE", "false")
            and setting_enabled(current_values, "USE_SIM_RACING_APPS", "true")
            and not sim_racing_apps_is_running()
        ):
            messagebox.showwarning(
                "SIMRacingApps is not connected",
                "Use SIMRacingApps Car Graphics is set to true, but SIMRacingAppsServer is not connected to iRacing.\n\n"
                "Start SIMRacingAppsServer and confirm it connects to the sim before starting the broadcast, or change Use SIMRacingApps Car Graphics to false and save settings.",
            )
            status.set(
                "SIMRacingApps is enabled but not connected to iRacing. Connect it to the sim or set it to false."
            )
            refresh_health()
            return
        process = launch_broadcast()
        if process:
            if setting_enabled(current_values, "DRIVER_MODE", "false"):
                status.set(
                    "Driver Mode recording started. Studio audio and automatic cameras are off. "
                    "Stop Broadcast after the race to finish and save the recording."
                )
            else:
                status.set(
                    "Started broadcast with overlay, Producer Assist, cameras, and incident replay. "
                    "Use Producer Assist to toggle OpenAI, ElevenLabs, and auto cameras."
                )
            root.after(1500, open_producer_assist_after_start)
        refresh_health()

    def play_recorded_broadcast():
        save_settings()
        current_values = collect_values()
        recording = Path(current_values.get("RECORDED_BROADCAST_FILE", "")).expanduser()
        if not recording.is_file():
            messagebox.showerror(
                "Recording not found",
                "Choose a valid Driver Mode .jsonl recording first.",
            )
            return
        if not recording.with_suffix(".events.jsonl").is_file():
            messagebox.showerror(
                "Broadcast events not found",
                "This is not a complete Driver Mode recording. Keep the main .jsonl and matching .events.jsonl files together.",
            )
            return
        command = broadcast_command(current_values, replay_path=recording)
        process = launch_broadcast(command=command)
        if process:
            status.set(
                "Recorded broadcast started. Keep the matching iRacing replay open; "
                "Producer Assist will control cameras and caution review."
            )
            root.after(1500, open_producer_assist_after_start)
        refresh_health()

    def open_producer_assist_after_start():
        try:
            open_external_link(producer_assist_launch_url())
        except Exception as error:
            status.set(
                "Broadcast started, but Producer Assist did not open automatically: "
                f"{error}"
            )

    def stop_running_broadcast():
        stopped_count = stop_broadcast()
        if stopped_count:
            status.set(f"Stopped broadcast process(es): {stopped_count}.")
        else:
            status.set("No running broadcast found from this launcher.")
        refresh_health()

    def check_for_updates():
        status.set("Checking GitHub Releases for updates...")
        root.update_idletasks()
        try:
            release = fetch_latest_release()
            state, message, release_url = update_status_from_release(release)
        except urllib.error.HTTPError as error:
            if error.code == 404:
                status.set(
                    "No GitHub release is published yet. Use the installer build from this project for now."
                )
                return
            status.set(f"Update check failed: GitHub returned HTTP {error.code}.")
            return
        except Exception as error:
            status.set(f"Update check failed: {error}")
            return

        status.set(message)
        if state == "available":
            should_open = messagebox.askyesno(
                "Update available",
                f"{message}\n\nOpen the download/release page?",
            )
            if should_open:
                open_external_link(release_url)

    def on_close():
        if has_running_broadcast():
            should_stop = messagebox.askyesno(
                CLOSE_RUNNING_BROADCAST_TITLE,
                CLOSE_RUNNING_BROADCAST_MESSAGE,
            )
            if should_stop:
                stop_broadcast()
                root.destroy()
            return
        root.destroy()

    button(broadcast_bar, text="Start Broadcast", command=start_broadcast, color=GREEN).pack(
        side="left",
        padx=6,
        pady=8,
    )
    button(
        broadcast_bar,
        text="Play Recorded Broadcast",
        command=play_recorded_broadcast,
        color="#5d3fb8",
    ).pack(side="left", padx=6, pady=8)
    button(broadcast_bar, text="Stop Broadcast", command=stop_running_broadcast, color=STOP_RED).pack(
        side="left",
        padx=6,
        pady=8,
    )
    button(profile_action_bar, text="Save Settings", command=save_settings, color="#334b64").pack(
        side="left",
        padx=6,
        pady=8,
    )
    button(profile_action_bar, text="Refresh Profiles", command=refresh_profile_list, color="#334b64").pack(
        side="left",
        padx=6,
        pady=8,
    )
    button(profile_action_bar, text="Create League Files", command=create_league_files, color="#334b64").pack(
        side="left",
        padx=6,
        pady=8,
    )
    volume_var = tk.IntVar(value=int(existing.get("STUDIO_VOLUME", existing.get("PRACTICE_MUSIC_VOLUME", "65")) or 65))

    def update_volume_label(value):
        return None

    build_league_manager_tab(
        league_manager_content,
        status,
        label,
        frame,
        entry,
        button,
        get_profile_name=lambda: profile_var.get().strip() or profile_name_var.get().strip(),
        league_manager_state=league_manager_state,
    )
    build_league_tab(
        league_content,
        status,
        label,
        frame,
        entry,
        button,
        existing,
        sim_racer_hub_state,
        settings_entries=entries,
        get_profile_name=lambda: profile_var.get().strip() or profile_name_var.get().strip(),
        league_tab_state=league_tab_state,
    )
    build_help_tab(
        help_content,
        label,
        frame,
        button,
        get_values=collect_values,
        broadcast_running=has_running_broadcast,
        status=status,
    )

    def resize_notebook_to_selected_tab(_event=None):
        """Do not reserve the tallest tab's height for every Studio section."""
        try:
            selected_name = notebook.select()
            if not selected_name:
                return
            selected_tab = root.nametowidget(selected_name)
            selected_tab.update_idletasks()
            requested = max(120, selected_tab.winfo_reqheight())
            if int(notebook.cget("height") or 0) != requested:
                notebook.configure(height=requested)
        except (tk.TclError, ValueError):
            return

    notebook.bind(
        "<<NotebookTabChanged>>",
        lambda event: root.after_idle(lambda: resize_notebook_to_selected_tab(event)),
        add="+",
    )
    for studio_tab in (settings_tab, league_manager_tab, league_tab, help_tab):
        studio_tab.bind(
            "<Configure>",
            lambda event: root.after_idle(lambda: resize_notebook_to_selected_tab(event)),
            add="+",
        )
    root.after_idle(resize_notebook_to_selected_tab)
    refresh_health()
    root.protocol("WM_DELETE_WINDOW", on_close)

    root.mainloop()


def build_league_manager_tab(
    parent,
    status,
    label,
    frame,
    entry,
    button,
    get_profile_name=None,
    league_manager_state=None,
):
    import tkinter as tk
    from tkinter import ttk

    league_manager_state = league_manager_state if league_manager_state is not None else {}

    def league_folder():
        profile_name = (get_profile_name() if get_profile_name else "") or "default"
        return ROOT / "league" / league_folder_slug(profile_name)

    def profile_scoring_path():
        return league_folder() / "scoring.json"

    def format_finish_points(scoring):
        return "\n".join(
            f"{position}={format_points(points)}"
            for position, points in sorted(scoring.finish_points.items())
        )

    def format_rules(rules):
        return "\n".join(f"{rule.name}={format_points(rule.points)}" for rule in rules if rule.enabled)

    def format_points(value):
        number = float(value)
        return str(int(number)) if number.is_integer() else str(number)

    def parse_name_points(text, item_name):
        parsed = []
        for line_number, raw_line in enumerate(str(text or "").splitlines(), start=1):
            line = raw_line.strip()
            if not line or line.startswith("#"):
                continue
            if "=" not in line:
                raise ValueError(f"{item_name} line {line_number} must use Name=Points.")
            name, raw_points = line.split("=", 1)
            name = name.strip()
            if not name:
                raise ValueError(f"{item_name} line {line_number} needs a name.")
            parsed.append((name, float(raw_points.strip())))
        return parsed

    def scoring_from_form():
        finish_points = {}
        for name, points in parse_name_points(finish_text.get("1.0", "end"), "Finishing points"):
            try:
                position = int(name.removeprefix("P").removeprefix("p"))
            except ValueError as error:
                raise ValueError(f"Finishing position '{name}' must be a number such as 1=40.") from error
            if position in finish_points:
                raise ValueError(f"Finishing position P{position} is listed more than once.")
            finish_points[position] = points
        bonuses = [ScoringRule(name, points) for name, points in parse_name_points(bonus_text.get("1.0", "end"), "Bonus rule")]
        penalties = [ScoringRule(name, points) for name, points in parse_name_points(penalty_text.get("1.0", "end"), "Penalty rule")]
        return ScoringSystem(
            name=scoring_name_var.get().strip(),
            finish_points=finish_points,
            bonus_rules=bonuses,
            penalty_rules=penalties,
        )

    def populate(scoring):
        scoring_name_var.set(scoring.name)
        for widget, value in (
            (finish_text, format_finish_points(scoring)),
            (bonus_text, format_rules(scoring.bonus_rules)),
            (penalty_text, format_rules(scoring.penalty_rules)),
        ):
            widget.delete("1.0", "end")
            widget.insert("1.0", value)
        update_preview(scoring)

    def update_preview(scoring=None):
        try:
            scoring = scoring or scoring_from_form()
            errors = scoring.validate()
            if errors:
                raise ValueError("\n".join(errors))
            winner = scoring.calculate(1)
            preview_var.set(
                f"{len(scoring.finish_points)} finishing positions • "
                f"{len(scoring.bonus_rules)} bonus rules • "
                f"{len(scoring.penalty_rules)} penalty rules • "
                f"Winner base: {format_points(winner['total'])} points"
            )
        except Exception as error:
            preview_var.set(f"Needs attention: {error}")

    def load_current():
        path = profile_scoring_path()
        try:
            populate(load_scoring_system(path))
            status.set(f"Loaded league scoring: {path}")
        except Exception as error:
            messagebox.showerror("Scoring load failed", str(error))

    def save_current():
        path = profile_scoring_path()
        try:
            scoring = scoring_from_form()
            save_scoring_system(path, scoring)
            update_preview(scoring)
            status.set(f"Saved customizable league scoring: {path}")
        except Exception as error:
            messagebox.showerror("Scoring setup needs attention", str(error))

    intro = frame(parent, bg="#0b1520")
    intro.pack(fill="x", padx=14, pady=(12, 8))
    label(
        intro,
        text="League Manager",
        bg="#0b1520",
        fg=TEXT_FG,
        font=("Segoe UI", 14, "bold"),
        anchor="w",
    ).pack(fill="x", padx=12, pady=(10, 2))
    label(
        intro,
        text=(
            "Build the league profile, season schedule, and points system for the selected Studio profile. "
            "Import Current iRacing Session reads the live simulator only—no iRacing password is stored or requested."
        ),
        bg="#0b1520",
        fg=MUTED_FG,
        justify="left",
        anchor="w",
        wraplength=940,
    ).pack(fill="x", padx=12, pady=(0, 10))

    profile_panel = frame(parent, bg="#0b1520")
    profile_panel.pack(fill="x", padx=14, pady=(2, 8))
    label(profile_panel, text="League Profile", bg="#0b1520", fg=TEXT_FG, font=("Segoe UI", 12, "bold"), anchor="w").grid(row=0, column=0, columnspan=4, sticky="ew", padx=10, pady=(10, 6))
    league_name_var = tk.StringVar()
    league_short_var = tk.StringVar()
    season_name_var = tk.StringVar()
    league_id_var = tk.StringVar()
    profile_fields = (
        ("League Name", league_name_var), ("Short Name", league_short_var),
        ("Season Name", season_name_var), ("iRacing League ID", league_id_var),
    )
    for index, (title, variable) in enumerate(profile_fields):
        row, pair = 1 + index // 2, index % 2
        label(profile_panel, text=title, bg="#0b1520", fg=MUTED_FG, anchor="w").grid(row=row, column=pair * 2, sticky="w", padx=(10, 5), pady=4)
        entry(profile_panel, textvariable=variable, width=30).grid(row=row, column=pair * 2 + 1, sticky="ew", padx=(0, 10), pady=4)
    profile_panel.columnconfigure(1, weight=1)
    profile_panel.columnconfigure(3, weight=1)

    schedule_events = []
    schedule_panel = frame(parent, bg="#0b1520")
    schedule_panel.pack(fill="x", padx=14, pady=8)
    label(schedule_panel, text="Season Schedule", bg="#0b1520", fg=TEXT_FG, font=("Segoe UI", 12, "bold"), anchor="w").pack(fill="x", padx=10, pady=(10, 6))
    schedule_form = frame(schedule_panel, bg="#0b1520")
    schedule_form.pack(fill="x", padx=10)
    round_var, date_var, event_name_var = tk.StringVar(), tk.StringVar(), tk.StringVar()
    track_var, config_var, car_type_var = tk.StringVar(), tk.StringVar(), tk.StringVar()
    laps_var, duration_var, practice_var = tk.StringVar(), tk.StringVar(), tk.StringVar()
    qualifying_var, race_time_var = tk.StringVar(), tk.StringVar()
    event_status_var = tk.StringVar(value="Scheduled")
    first_row = (("Round", round_var, 6), ("Date MM-DD-YYYY", date_var, 13), ("Race Name", event_name_var, 24), ("Track", track_var, 24), ("Configuration", config_var, 15), ("Car Type", car_type_var, 16))
    second_row = (("Laps", laps_var, 7), ("Timed Race Minutes", duration_var, 12), ("Practice Time", practice_var, 11), ("Qualifying Time", qualifying_var, 11), ("Race Start", race_time_var, 11))
    for column, (title, variable, width) in enumerate(first_row):
        cell = frame(schedule_form, bg="#0b1520")
        cell.grid(row=0, column=column, sticky="ew", padx=(0, 6))
        label(cell, text=title, bg="#0b1520", fg=MUTED_FG, anchor="w").pack(fill="x")
        entry(cell, textvariable=variable, width=width).pack(fill="x")
        schedule_form.columnconfigure(column, weight=2 if title in {"Race Name", "Track"} else 1)
    for column, (title, variable, width) in enumerate(second_row):
        cell = frame(schedule_form, bg="#0b1520")
        cell.grid(row=1, column=column, sticky="ew", padx=(0, 6), pady=(7, 0))
        label(cell, text=title, bg="#0b1520", fg=MUTED_FG, anchor="w").pack(fill="x")
        entry(cell, textvariable=variable, width=width).pack(fill="x")
    status_cell = frame(schedule_form, bg="#0b1520")
    status_cell.grid(row=1, column=5, sticky="ew", pady=(7, 0))
    label(status_cell, text="Status", bg="#0b1520", fg=MUTED_FG, anchor="w").pack(fill="x")
    ttk.Combobox(status_cell, textvariable=event_status_var, values=("Scheduled", "Completed", "Cancelled"), state="readonly", width=11).pack(fill="x")

    schedule_table = frame(schedule_panel, bg="#0b1520")
    schedule_table.pack(fill="both", expand=True, padx=10, pady=8)
    schedule_tree = ttk.Treeview(schedule_table, columns=("round", "date", "name", "track", "car", "distance", "race", "status"), show="headings", height=11)
    for key, title, width in (("round", "Rd", 38), ("date", "Date", 85), ("name", "Race Name", 170), ("track", "Track", 190), ("car", "Car Type", 115), ("distance", "Distance", 85), ("race", "Race Start", 75), ("status", "Status", 75)):
        schedule_tree.heading(key, text=title)
        schedule_tree.column(key, width=width, anchor="center" if key in {"round", "laps"} else "w")
    schedule_scrollbar = ttk.Scrollbar(schedule_table, orient="vertical", command=schedule_tree.yview)
    schedule_tree.configure(yscrollcommand=schedule_scrollbar.set)
    schedule_tree.pack(side="left", fill="both", expand=True)
    schedule_scrollbar.pack(side="right", fill="y")
    schedule_count_var = tk.StringVar(value="No schedule rounds saved yet.")
    label(schedule_panel, textvariable=schedule_count_var, bg="#0b1520", fg=MUTED_FG, anchor="w").pack(fill="x", padx=10, pady=(0, 4))

    def refresh_schedule():
        schedule_tree.delete(*schedule_tree.get_children())
        for event in sorted(schedule_events, key=lambda item: item.round_number):
            distance = f"{event.laps} laps" if event.laps else f"{event.duration_minutes} min"
            schedule_tree.insert("", "end", values=(event.round_number, event.event_date, event.event_name, event.track_name, event.car_type, distance, event.race_time, event.status))
        schedule_count_var.set(
            f"{len(schedule_events)} schedule round{'s' if len(schedule_events) != 1 else ''} • use the scrollbar to view the complete season"
            if schedule_events else "No schedule rounds saved yet."
        )

    def save_profile_and_schedule():
        try:
            league_id = league_id_var.get().strip()
            profile = LeagueProfile(league_name_var.get().strip(), league_short_var.get().strip(), season_name_var.get().strip(), int(league_id) if league_id else None)
            save_league_profile(league_folder() / "league.json", profile)
            save_schedule(league_folder() / "schedule.json", schedule_events)
            status.set(f"Saved league profile and {len(schedule_events)} schedule events: {league_folder()}")
        except Exception as error:
            messagebox.showerror("League setup needs attention", str(error))

    def load_profile_and_schedule():
        nonlocal schedule_events
        try:
            profile = load_league_profile(league_folder() / "league.json")
            league_name_var.set(profile.name)
            league_short_var.set(profile.short_name)
            season_name_var.set(profile.season_name)
            league_id_var.set(profile.iracing_league_id or "")
            schedule_events = load_schedule(league_folder() / "schedule.json")
            refresh_schedule()
        except Exception as error:
            messagebox.showerror("League profile load failed", str(error))

    def add_schedule_event():
        try:
            event = ScheduleEvent(
                round_number=int(round_var.get()), event_date=date_var.get().strip(), track_name=track_var.get().strip(),
                configuration=config_var.get().strip(), laps=int(laps_var.get()) if laps_var.get().strip() else None,
                status=event_status_var.get(), event_name=event_name_var.get().strip(), car_type=car_type_var.get().strip(),
                duration_minutes=int(duration_var.get()) if duration_var.get().strip() else None,
                practice_time=practice_var.get().strip(), qualifying_time=qualifying_var.get().strip(), race_time=race_time_var.get().strip(),
            )
            event.validate()
            schedule_events[:] = [item for item in schedule_events if item.round_number != event.round_number]
            schedule_events.append(event)
            refresh_schedule()
            round_var.set(str(max((item.round_number for item in schedule_events), default=0) + 1))
        except Exception as error:
            messagebox.showerror("Schedule event needs attention", str(error))

    def delete_schedule_event():
        selected = schedule_tree.selection()
        if selected:
            selected_round = int(schedule_tree.item(selected[0], "values")[0])
            schedule_events[:] = [item for item in schedule_events if item.round_number != selected_round]
            refresh_schedule()

    def edit_selected_schedule_event(_event=None):
        selected = schedule_tree.selection()
        if not selected:
            return
        selected_round = int(schedule_tree.item(selected[0], "values")[0])
        event = next((item for item in schedule_events if item.round_number == selected_round), None)
        if not event:
            return
        for variable, value in (
            (round_var, event.round_number), (date_var, event.event_date), (event_name_var, event.event_name),
            (track_var, event.track_name), (config_var, event.configuration), (car_type_var, event.car_type),
            (laps_var, event.laps or ""), (duration_var, event.duration_minutes or ""),
            (practice_var, event.practice_time), (qualifying_var, event.qualifying_time),
            (race_time_var, event.race_time), (event_status_var, event.status),
        ):
            variable.set(value)

    schedule_tree.bind("<<TreeviewSelect>>", edit_selected_schedule_event)

    def import_active_session():
        try:
            snapshot = active_iracing_league_snapshot()
            if snapshot["league_id"]:
                league_id_var.set(snapshot["league_id"])
            if snapshot["league_name"]:
                league_name_var.set(snapshot["league_name"])
            if snapshot["season_name"]:
                season_name_var.set(snapshot["season_name"])
            track_var.set(snapshot["track_name"])
            config_var.set(snapshot["configuration"])
            laps_var.set(snapshot["laps"] or "")
            if not round_var.get():
                round_var.set(str(max((item.round_number for item in schedule_events), default=0) + 1))
            status.set("Imported league and current-event information from the active iRacing session. Review it, add the event, then save.")
        except Exception as error:
            messagebox.showerror("iRacing import unavailable", str(error))

    schedule_actions = frame(schedule_panel, bg="#0b1520")
    schedule_actions.pack(fill="x", padx=10, pady=(0, 10))
    button(schedule_actions, text="Load League Profile", command=load_profile_and_schedule, color="#334b64").pack(side="left", padx=(0, 6))
    button(schedule_actions, text="Import Current iRacing Session", command=import_active_session, color="#334b64").pack(side="left", padx=(0, 6))
    button(schedule_actions, text="Add / Update Round", command=add_schedule_event, color="#334b64").pack(side="left", padx=6)
    button(schedule_actions, text="Delete Selected Round", command=delete_schedule_event, color="#8b2d38").pack(side="left", padx=6)
    button(schedule_actions, text="Save League & Schedule", command=save_profile_and_schedule, color=GREEN).pack(side="right")

    name_row = frame(parent, bg=PANEL_BG)
    name_row.pack(fill="x", padx=14, pady=(2, 8))
    label(name_row, text="Scoring System Name", bg=PANEL_BG, fg=MUTED_FG, width=22, anchor="w").pack(side="left")
    scoring_name_var = tk.StringVar(value="Custom League Points")
    entry(name_row, textvariable=scoring_name_var, width=54).pack(side="left", fill="x", expand=True)

    editors = frame(parent, bg=PANEL_BG)
    editors.pack(fill="x", expand=False, padx=14)
    editor_specs = (
        ("Finishing Position Points", "Use one position per line, such as 1=40", 11),
        ("Bonus Points", "Use Name=Points, such as Fastest Lap=1", 8),
        ("Penalty Points", "Use Name=Points; these values are subtracted", 8),
    )
    text_widgets = []
    for column, (title, help_text, height) in enumerate(editor_specs):
        panel = frame(editors, bg="#0b1520")
        panel.grid(row=0, column=column, sticky="nsew", padx=(0 if column == 0 else 6, 0))
        editors.columnconfigure(column, weight=1)
        label(panel, text=title, bg="#0b1520", fg=TEXT_FG, font=("Segoe UI", 11, "bold"), anchor="w").pack(fill="x", padx=10, pady=(10, 2))
        label(panel, text=help_text, bg="#0b1520", fg=MUTED_FG, anchor="w", wraplength=280).pack(fill="x", padx=10, pady=(0, 6))
        widget = tk.Text(panel, height=height, width=28, bg=FIELD_BG, fg=TEXT_FG, insertbackground=TEXT_FG, relief="flat", font=("Consolas", 10))
        widget.pack(fill="both", expand=True, padx=10, pady=(0, 10))
        text_widgets.append(widget)
    finish_text, bonus_text, penalty_text = text_widgets

    actions = frame(parent, bg=PANEL_BG)
    actions.pack(fill="x", padx=14, pady=10)
    button(actions, text="Load Profile Scoring", command=load_current, color="#334b64").pack(side="left", padx=(0, 6))
    button(actions, text="Preview / Validate", command=update_preview, color="#334b64").pack(side="left", padx=6)
    button(actions, text="Reset Template", command=lambda: populate(default_scoring_system()), color="#8b6a1c").pack(side="left", padx=6)
    button(actions, text="Save Scoring System", command=save_current, color=GREEN).pack(side="left", padx=6)

    preview_var = tk.StringVar(value="Scoring system not loaded yet.")
    label(parent, textvariable=preview_var, bg=PANEL_BG, fg=TEXT_FG, anchor="w", justify="left", wraplength=940).pack(fill="x", padx=16, pady=(0, 12))

    race_results = []
    results_panel = frame(parent, bg="#0b1520")
    results_panel.pack(fill="x", expand=False, padx=14, pady=(2, 14))
    results_header = frame(results_panel, bg="#0b1520")
    results_header.pack(fill="x", padx=10, pady=(10, 6))
    label(results_header, text="Results & Championship Standings", bg="#0b1520", fg=TEXT_FG, font=("Segoe UI", 12, "bold"), anchor="w").pack(side="left")
    results_summary_var = tk.StringVar(value="No league results saved yet.")
    label(results_header, textvariable=results_summary_var, bg="#0b1520", fg=MUTED_FG, anchor="w").pack(side="left", padx=14)
    result_round_var = tk.StringVar()
    label(results_header, text="Review Round", bg="#0b1520", fg=MUTED_FG, anchor="w").pack(side="right", padx=(8, 4))
    result_round_combo = ttk.Combobox(results_header, textvariable=result_round_var, state="readonly", width=10)
    result_round_combo.pack(side="right")

    results_tables = frame(results_panel, bg="#0b1520")
    results_tables.pack(fill="x", expand=False, padx=10)
    result_tree = ttk.Treeview(results_tables, columns=("pos", "number", "driver", "start", "led", "points"), show="headings", height=8)
    standings_tree = ttk.Treeview(results_tables, columns=("pos", "driver", "starts", "wins", "top5", "top10", "avg", "points"), show="headings", height=8)
    for tree, specs in (
        (result_tree, (("pos", "Pos", 40), ("number", "#", 45), ("driver", "Latest Race Results", 180), ("start", "Start", 45), ("led", "Led", 45), ("points", "Pts", 55))),
        (standings_tree, (("pos", "Pos", 40), ("driver", "Championship", 160), ("starts", "Starts", 48), ("wins", "Wins", 42), ("top5", "Top 5", 45), ("top10", "Top 10", 50), ("avg", "Avg", 50), ("points", "Pts", 55))),
    ):
        for key, title, width in specs:
            tree.heading(key, text=title)
            tree.column(key, width=width, anchor="w" if key == "driver" else "center")
    result_tree.pack(side="left", fill="both", expand=True, padx=(0, 5))
    standings_tree.pack(side="left", fill="both", expand=True, padx=(5, 0))

    def results_path():
        return league_folder() / "results.json"

    def selected_result_race():
        try:
            selected_round = int(result_round_var.get())
        except (TypeError, ValueError):
            selected_round = max((race.round_number for race in race_results), default=0)
        return next((race for race in race_results if race.round_number == selected_round), None)

    def refresh_results():
        result_tree.delete(*result_tree.get_children())
        standings_tree.delete(*standings_tree.get_children())
        rounds = [str(race.round_number) for race in sorted(race_results, key=lambda item: item.round_number)]
        result_round_combo.configure(values=rounds)
        if rounds and result_round_var.get() not in rounds:
            result_round_var.set(rounds[-1])
        selected_race = selected_result_race()
        if selected_race:
            for item in sorted(selected_race.entries, key=lambda entry: entry.position):
                result_tree.insert("", "end", values=(item.position, item.car_number, item.name, item.starting_position or "-", item.laps_led, format_points(item.points)))
        standings = calculate_standings(race_results)
        for position, item in enumerate(standings, start=1):
            standings_tree.insert("", "end", values=(position, item["name"], item["starts"], item["wins"], item["top_fives"], item["top_tens"], item["average_finish"], format_points(item["points"])))
        result_tree.configure(height=max(3, min(40, len(selected_race.entries) if selected_race else 3)))
        standings_tree.configure(height=max(3, min(40, len(standings) or 3)))
        results_summary_var.set(f"{len(race_results)} race(s) • {len(standings)} driver(s) automatically tracked" if race_results else "No league results saved yet.")

    def load_results():
        nonlocal race_results
        race_results = load_race_results(results_path())
        refresh_results()

    def import_completed_race():
        nonlocal race_results
        try:
            round_number = int(round_var.get())
            scheduled = next((item for item in schedule_events if item.round_number == round_number), None)
            event_name = event_name_var.get().strip() or (scheduled.event_name if scheduled else "")
            result = score_race_result(active_iracing_race_result(round_number, event_name), scoring_from_form())
            if not result.entries:
                raise ValueError("No classified drivers were found in the completed race results.")
            race_results = [race for race in race_results if race.round_number != round_number] + [result]
            save_race_results(results_path(), race_results)
            drivers_path = league_folder() / "drivers.csv"
            driver_rows = load_driver_profile_rows(drivers_path)
            known_names = {row.get("name", "").casefold().strip() for row in driver_rows}
            known_numbers = {row.get("car_number", "").strip() for row in driver_rows if row.get("car_number", "").strip()}
            added_drivers = 0
            for entry_result in result.entries:
                if entry_result.name.casefold().strip() in known_names or (entry_result.car_number and entry_result.car_number in known_numbers):
                    continue
                driver_rows.append({field: "" for field in DRIVER_PROFILE_FIELDS} | {"name": entry_result.name, "car_number": entry_result.car_number})
                known_names.add(entry_result.name.casefold().strip())
                if entry_result.car_number:
                    known_numbers.add(entry_result.car_number)
                added_drivers += 1
            save_driver_profile_rows(drivers_path, driver_rows)
            if scheduled:
                scheduled.status = "Completed"
                save_schedule(league_folder() / "schedule.json", schedule_events)
                refresh_schedule()
            refresh_results()
            status.set(f"Imported Round {round_number}: {len(result.entries)} drivers scored, {added_drivers} new profile(s) created, and standings rebuilt.")
        except Exception as error:
            messagebox.showerror("Race results import unavailable", str(error))

    def delete_latest_result():
        nonlocal race_results
        if not race_results:
            return
        latest_round = max(race.round_number for race in race_results)
        if not messagebox.askyesno("Delete race results", f"Delete saved results for Round {latest_round} and rebuild the standings?"):
            return
        race_results = [race for race in race_results if race.round_number != latest_round]
        save_race_results(results_path(), race_results)
        refresh_results()

    points_review = frame(results_panel, bg="#101a24")
    points_review.pack(fill="x", padx=10, pady=(10, 2))
    label(points_review, text="Post-Race Points Review", bg="#101a24", fg=TEXT_FG, font=("Segoe UI", 11, "bold"), anchor="w").grid(row=0, column=0, columnspan=7, sticky="ew", padx=10, pady=(9, 2))
    review_driver_var = tk.StringVar(value="Select a driver from the race results above.")
    label(points_review, textvariable=review_driver_var, bg="#101a24", fg=MUTED_FG, anchor="w").grid(row=1, column=0, columnspan=7, sticky="ew", padx=10, pady=(0, 6))
    position_points_var = tk.StringVar()
    bonus_points_var = tk.StringVar()
    penalty_points_var = tk.StringVar()
    stage_points_var = tk.StringVar()
    manual_adjustment_var = tk.StringVar()
    adjustment_reason_var = tk.StringVar()
    total_points_var = tk.StringVar(value="—")
    review_fields = (
        ("Position Pts", position_points_var, 10),
        ("Bonus Pts", bonus_points_var, 10),
        ("Penalty Pts", penalty_points_var, 10),
        ("Stage Pts", stage_points_var, 10),
        ("Manual +/-", manual_adjustment_var, 10),
        ("Reason", adjustment_reason_var, 32),
    )
    for column, (title, variable, width) in enumerate(review_fields):
        cell = frame(points_review, bg="#101a24")
        cell.grid(row=2, column=column, sticky="ew", padx=(10 if column == 0 else 3, 3), pady=(0, 9))
        label(cell, text=title, bg="#101a24", fg=MUTED_FG, anchor="w").pack(fill="x")
        entry(cell, textvariable=variable, width=width).pack(fill="x")
        points_review.columnconfigure(column, weight=2 if title == "Reason" else 1)
    total_cell = frame(points_review, bg="#101a24")
    total_cell.grid(row=2, column=6, sticky="ew", padx=(3, 10), pady=(0, 9))
    label(total_cell, text="Final Total", bg="#101a24", fg=MUTED_FG, anchor="w").pack(fill="x")
    label(total_cell, textvariable=total_points_var, bg=FIELD_BG, fg=TEXT_FG, anchor="center", font=("Segoe UI", 10, "bold")).pack(fill="x", ipady=4)

    def selected_result_entry():
        selection = result_tree.selection()
        race = selected_result_race()
        if not selection or not race:
            return None
        values = result_tree.item(selection[0], "values")
        if not values:
            return None
        position, number, name = int(values[0]), str(values[1]), str(values[2])
        return next((item for item in race.entries if item.position == position and item.car_number == number and item.name == name), None)

    def show_selected_points(_event=None):
        item = selected_result_entry()
        if not item:
            return
        review_driver_var.set(f"P{item.position}  #{item.car_number}  {item.name}")
        has_breakdown = any((item.position_points, item.bonus_points, item.penalty_points, item.stage_points, item.manual_adjustment))
        position_points_var.set(format_points(item.position_points if has_breakdown else item.points))
        bonus_points_var.set(format_points(item.bonus_points))
        penalty_points_var.set(format_points(item.penalty_points))
        stage_points_var.set(format_points(item.stage_points))
        manual_adjustment_var.set(format_points(item.manual_adjustment))
        adjustment_reason_var.set(item.adjustment_reason)
        total_points_var.set(format_points(item.points))

    def save_reviewed_points():
        item = selected_result_entry()
        if not item:
            messagebox.showerror("Select a driver", "Select a driver from the race-result table first.")
            return
        try:
            item.position_points = float(position_points_var.get() or 0)
            item.bonus_points = float(bonus_points_var.get() or 0)
            item.penalty_points = abs(float(penalty_points_var.get() or 0))
            item.stage_points = float(stage_points_var.get() or 0)
            item.manual_adjustment = float(manual_adjustment_var.get() or 0)
            item.adjustment_reason = adjustment_reason_var.get().strip()
            item.points = item.position_points + item.bonus_points - item.penalty_points + item.stage_points + item.manual_adjustment
            save_race_results(results_path(), race_results)
            refresh_results()
            total_points_var.set(format_points(item.points))
            status.set(f"Saved the reviewed points for {item.name}. Standings rebuilt; publish when the race is finalized.")
        except ValueError:
            messagebox.showerror("Invalid points", "Position, bonus, penalty, stage, and manual adjustment values must be numbers.")

    result_tree.bind("<<TreeviewSelect>>", show_selected_points)
    result_round_combo.bind("<<ComboboxSelected>>", lambda _event: refresh_results())

    results_actions = frame(results_panel, bg="#0b1520")
    results_actions.pack(fill="x", padx=10, pady=10)
    button(results_actions, text="Import Completed iRacing Race", command=import_completed_race, color=GREEN).pack(side="left", padx=(0, 6))
    button(results_actions, text="Reload Saved Results", command=load_results, color="#334b64").pack(side="left", padx=6)
    button(results_actions, text="Delete Latest Result", command=delete_latest_result, color="#8b2d38").pack(side="left", padx=6)
    button(results_actions, text="Save Reviewed Driver Points", command=save_reviewed_points, color="#8b6a1c").pack(side="right", padx=6)

    website_panel = frame(parent, bg="#0b1520")
    website_panel.pack(fill="x", padx=14, pady=(0, 14))
    label(website_panel, text="RGC WordPress Website", bg="#0b1520", fg=TEXT_FG, font=("Segoe UI", 12, "bold"), anchor="w").grid(row=0, column=0, columnspan=4, sticky="ew", padx=10, pady=(10, 2))
    label(
        website_panel,
        text="Publishes this profile's schedule, results, standings, and driver stats. Create the Application Password in WordPress and keep it private.",
        bg="#0b1520", fg=MUTED_FG, anchor="w", justify="left", wraplength=1000,
    ).grid(row=1, column=0, columnspan=4, sticky="ew", padx=10, pady=(0, 7))
    wordpress_endpoint_var = tk.StringVar(value="https://realisticgamingcrew.com/wp-json/rgc-league-manager/v1/sync")
    wordpress_username_var = tk.StringVar()
    wordpress_password_var = tk.StringVar()
    wordpress_league_slug_var = tk.StringVar()
    wordpress_season_slug_var = tk.StringVar()
    wordpress_auto_var = tk.StringVar(value="false")
    website_fields = (
        ("Endpoint", wordpress_endpoint_var, 70, False),
        ("WordPress Username", wordpress_username_var, 28, False),
        ("Application Password", wordpress_password_var, 28, True),
        ("League URL Slug", wordpress_league_slug_var, 28, False),
        ("Season URL Slug", wordpress_season_slug_var, 28, False),
    )
    for index, (title, variable, width, secret) in enumerate(website_fields):
        row = 2 + index // 2
        pair = index % 2
        label(website_panel, text=title, bg="#0b1520", fg=MUTED_FG, anchor="w").grid(row=row, column=pair * 2, sticky="w", padx=(10, 5), pady=4)
        field = entry(website_panel, textvariable=variable, width=width)
        if secret:
            field.configure(show="•")
        field.grid(row=row, column=pair * 2 + 1, sticky="ew", padx=(0, 10), pady=4)
    label(website_panel, text="Publish Automatically After Race", bg="#0b1520", fg=MUTED_FG, anchor="w").grid(row=4, column=2, sticky="w", padx=(10, 5), pady=4)
    ttk.Combobox(website_panel, textvariable=wordpress_auto_var, values=("false", "true"), state="readonly", width=12).grid(row=4, column=3, sticky="w", padx=(0, 10), pady=4)
    website_panel.columnconfigure(1, weight=1)
    website_panel.columnconfigure(3, weight=1)

    def wordpress_settings_from_form():
        return WordPressPublishSettings(
            endpoint=wordpress_endpoint_var.get().strip(),
            username=wordpress_username_var.get().strip(),
            application_password=wordpress_password_var.get().strip(),
            league_slug=wordpress_league_slug_var.get().strip(),
            season_slug=wordpress_season_slug_var.get().strip(),
            auto_publish=wordpress_auto_var.get().strip().lower() == "true",
        )

    def load_wordpress_form():
        website = load_wordpress_settings(league_folder() / "wordpress.json")
        wordpress_endpoint_var.set(website.endpoint)
        wordpress_username_var.set(website.username)
        wordpress_password_var.set(website.application_password)
        wordpress_league_slug_var.set(website.league_slug)
        wordpress_season_slug_var.set(website.season_slug)
        wordpress_auto_var.set("true" if website.auto_publish else "false")

    def save_wordpress_form():
        website = wordpress_settings_from_form()
        save_wordpress_settings(league_folder() / "wordpress.json", website)
        status.set("Saved the WordPress connection for this league profile.")

    def preview_wordpress_payload():
        try:
            payload = build_wordpress_payload(league_folder(), wordpress_settings_from_form())
            messagebox.showinfo(
                "WordPress Publish Preview",
                f"League: {payload['league']['name']}\nSlug: {payload['league']['slug']}\nSeason: {payload['season']['name']}\nSchedule rounds: {len(payload['schedule'])}\nCompleted races: {len(payload['results'])}",
            )
        except Exception as error:
            messagebox.showerror("WordPress preview unavailable", str(error))

    def publish_wordpress_now():
        try:
            website = wordpress_settings_from_form()
            save_wordpress_settings(league_folder() / "wordpress.json", website)
            result = publish_league_to_wordpress(league_folder(), website)
            status.set(f"Published {result.get('league')} / {result.get('season')} to realisticgamingcrew.com.")
            messagebox.showinfo("Website Published", "The league schedule, results, standings, and driver stats are now on WordPress.")
        except Exception as error:
            messagebox.showerror("WordPress publish failed", str(error))

    website_actions = frame(website_panel, bg="#0b1520")
    website_actions.grid(row=5, column=0, columnspan=4, sticky="ew", padx=10, pady=(7, 10))
    button(website_actions, text="Save Website Connection", command=save_wordpress_form, color="#334b64").pack(side="left", padx=(0, 6))
    button(website_actions, text="Preview Website Data", command=preview_wordpress_payload, color="#334b64").pack(side="left", padx=6)
    button(website_actions, text="Publish to Website Now", command=publish_wordpress_now, color=GREEN).pack(side="left", padx=6)

    def reload_manager_profile():
        load_profile_and_schedule()
        load_current()
        load_results()
        load_wordpress_form()

    league_manager_state["load_profile"] = reload_manager_profile
    reload_manager_profile()


def build_league_tab(
    parent,
    status,
    label,
    frame,
    entry,
    button,
    existing=None,
    sim_racer_hub_state=None,
    settings_entries=None,
    get_profile_name=None,
    league_tab_state=None,
):
    import tkinter as tk
    from tkinter import filedialog, simpledialog, ttk

    existing = launcher_defaults(existing or {})
    sim_racer_hub_state = sim_racer_hub_state if sim_racer_hub_state is not None else {}
    settings_entries = settings_entries or {}
    league_tab_state = league_tab_state if league_tab_state is not None else {}

    intro = (
        "Import league stats from Sim Racer Hub. You can use the clean URL "
        "https://simracerhub.com with League, Series, and Season IDs. "
        "Race Schedule CSV maps each track to its Sim Racer Hub race ID so Discord post-race reports can add the correct results link automatically."
    )
    label(parent, text=intro, anchor="w", justify="left", wraplength=900, bg=PANEL_BG, fg=MUTED_FG).pack(
        fill="x",
        padx=14,
        pady=(10, 8),
    )

    form = frame(parent, bg=PANEL_BG)
    form.pack(fill="x", padx=14)

    defaults = {
        "SIMRACERHUB_SOURCE": existing.get("SIMRACERHUB_SOURCE", "https://simracerhub.com"),
        "SIMRACERHUB_LEAGUE_ID": existing.get("SIMRACERHUB_LEAGUE_ID", ""),
        "SIMRACERHUB_SERIES_ID": existing.get("SIMRACERHUB_SERIES_ID", ""),
        "SIMRACERHUB_SEASON_ID": existing.get("SIMRACERHUB_SEASON_ID", ""),
        "SIMRACERHUB_TRACK_NAME": "",
        "SIMRACERHUB_MIN_STARTS": existing.get("SIMRACERHUB_MIN_STARTS", "2"),
        "SIMRACERHUB_FIRST_SCHEDULE_ID": existing.get("SIMRACERHUB_FIRST_SCHEDULE_ID", ""),
        "SIMRACERHUB_RACE_SCHEDULE_CSV": existing.get(
            "SIMRACERHUB_RACE_SCHEDULE_CSV",
            "league/race_schedule.csv",
        ),
        "SIMRACERHUB_SEASON_STATS_OUTPUT": existing.get(
            "SIMRACERHUB_SEASON_STATS_OUTPUT",
            "league/season.csv",
        ),
        "SIMRACERHUB_CAREER_STATS_OUTPUT": existing.get(
            "SIMRACERHUB_CAREER_STATS_OUTPUT",
            "league/career.csv",
        ),
        "SIMRACERHUB_DRIVERS_OUTPUT": existing.get("SIMRACERHUB_DRIVERS_OUTPUT", "league/drivers.csv"),
    }
    entries = {}
    rows = [
        ("Sim Racer Hub URL", "SIMRACERHUB_SOURCE"),
        ("League ID", "SIMRACERHUB_LEAGUE_ID"),
        ("Series ID", "SIMRACERHUB_SERIES_ID"),
        ("Season ID", "SIMRACERHUB_SEASON_ID"),
        ("First Race Schedule ID", "SIMRACERHUB_FIRST_SCHEDULE_ID"),
        ("Minimum Starts", "SIMRACERHUB_MIN_STARTS"),
        ("Race Schedule CSV", "SIMRACERHUB_RACE_SCHEDULE_CSV"),
        ("Season Stats CSV", "SIMRACERHUB_SEASON_STATS_OUTPUT"),
        ("Career Stats CSV", "SIMRACERHUB_CAREER_STATS_OUTPUT"),
        ("Drivers Output CSV", "SIMRACERHUB_DRIVERS_OUTPUT"),
    ]
    for row_number, (label_text, key) in enumerate(rows):
        label(form, text=label_text, anchor="w", width=22, bg=PANEL_BG, fg=MUTED_FG).grid(
            row=row_number,
            column=0,
            sticky="w",
            pady=4,
        )
        entry_widget = entry(form, width=86)
        entry_widget.insert(0, defaults[key])
        entry_widget.grid(row=row_number, column=1, sticky="ew", pady=4)
        entries[key] = entry_widget
    sim_racer_hub_state["entries"] = entries
    form.columnconfigure(1, weight=1)

    career_mode = tk.BooleanVar(
        value=setting_enabled(existing, "SIMRACERHUB_CAREER_MODE", "false")
    )
    sim_racer_hub_state["career_mode"] = career_mode
    label(
        form,
        text="Use the separate Season and Career import buttons below. Season uses Season ID; Career pulls all seasons.",
        anchor="w",
        bg=PANEL_BG,
        fg=MUTED_FG,
        wraplength=760,
    ).grid(row=len(rows), column=1, sticky="w", pady=(4, 8))

    buttons = frame(parent, bg=PANEL_BG)
    buttons.pack(fill="x", padx=14, pady=(8, 4))

    def values():
        return {key: entry.get().strip() for key, entry in entries.items()}

    output_box = tk.Text(
        parent,
        height=12,
        wrap="none",
        bg="#08111a",
        fg=TEXT_FG,
        insertbackground=TEXT_FG,
        relief="flat",
        highlightthickness=1,
        highlightbackground="#26384c",
    )

    def set_output(text):
        output_box.delete("1.0", "end")
        output_box.insert("1.0", text)

    def run_import(dry_run, drivers_only=False, schedule_only=False, career_override=None):
        data = values()
        if not data["SIMRACERHUB_SOURCE"]:
            messagebox.showerror("Missing URL", "Paste a Sim Racer Hub URL first.")
            return
        if (
            schedule_only
            and not data["SIMRACERHUB_SEASON_ID"]
            and "season_id=" not in data["SIMRACERHUB_SOURCE"]
        ):
            messagebox.showerror(
                "Missing Season ID",
                "Add a Season ID or paste a Sim Racer Hub URL that includes season_id before importing the race schedule.",
            )
            return

        effective_career_mode = bool(career_override) if career_override is not None else career_mode.get()
        if drivers_only or schedule_only:
            effective_career_mode = False

        stats_output = (
            data["SIMRACERHUB_CAREER_STATS_OUTPUT"]
            if effective_career_mode
            else data["SIMRACERHUB_SEASON_STATS_OUTPUT"]
        )
        if drivers_only:
            driver_target = driver_roster_import_target(
                driver_csv_var.get(),
                data.get("SIMRACERHUB_DRIVERS_OUTPUT", ""),
            )
            data["SIMRACERHUB_DRIVERS_OUTPUT"] = driver_target
            set_driver_csv_value(driver_target)
        result = run_sim_racer_hub_import(
            source=data["SIMRACERHUB_SOURCE"],
            league_id=data["SIMRACERHUB_LEAGUE_ID"],
            series_id=data["SIMRACERHUB_SERIES_ID"],
            season_id=data["SIMRACERHUB_SEASON_ID"],
            track_name=data.get("SIMRACERHUB_TRACK_NAME", ""),
            min_starts=data["SIMRACERHUB_MIN_STARTS"],
            first_schedule_id=data.get("SIMRACERHUB_FIRST_SCHEDULE_ID", ""),
            output=stats_output,
            drivers_output=data["SIMRACERHUB_DRIVERS_OUTPUT"],
            schedule_output=data["SIMRACERHUB_RACE_SCHEDULE_CSV"],
            career_mode=effective_career_mode,
            dry_run=dry_run,
            drivers_only=drivers_only,
            schedule_only=schedule_only,
        )
        combined_output = result.stdout
        if result.stderr:
            combined_output += "\n" + result.stderr
        set_output(combined_output or "(No output)")
        if result.returncode == 0:
            action = "Previewed" if dry_run else "Imported"
            mode = "career" if effective_career_mode else "season"
            if schedule_only:
                target = data["SIMRACERHUB_RACE_SCHEDULE_CSV"] or "league/race_schedule.csv"
            elif drivers_only:
                target = data["SIMRACERHUB_DRIVERS_OUTPUT"] or driver_roster_import_target()
                if not dry_run:
                    load_driver_profiles()
            else:
                target = stats_output or (
                    "league/career.csv" if effective_career_mode else "league/season.csv"
                )
            data_type = "race schedule" if schedule_only else ("driver roster" if drivers_only else "stats")
            suffix = "" if dry_run else f" to {target}"
            status.set(f"{action} Sim Racer Hub {mode} {data_type}{suffix}.")
        else:
            status.set("Sim Racer Hub import failed. Check the output panel.")

    button(buttons, text="Preview Season Stats", command=lambda: run_import(True, career_override=False), color="#334b64").pack(
        side="left",
        padx=4,
    )
    button(buttons, text="Import Season Stats", command=lambda: run_import(False, career_override=False), color=GREEN).pack(
        side="left",
        padx=4,
    )
    button(buttons, text="Preview Career Stats", command=lambda: run_import(True, career_override=True), color="#334b64").pack(
        side="left",
        padx=4,
    )
    button(buttons, text="Import Career Stats", command=lambda: run_import(False, career_override=True), color=GREEN).pack(
        side="left",
        padx=4,
    )
    button(buttons, text="Preview Driver Roster", command=lambda: run_import(True, True), color="#334b64").pack(
        side="left",
        padx=4,
    )
    button(buttons, text="Import Driver Roster", command=lambda: run_import(False, True), color=GREEN).pack(
        side="left",
        padx=4,
    )
    button(buttons, text="Preview Schedule", command=lambda: run_import(True, False, True), color="#334b64").pack(
        side="left",
        padx=4,
    )
    button(buttons, text="Import Schedule", command=lambda: run_import(False, False, True), color=GREEN).pack(
        side="left",
        padx=4,
    )
    label(
        buttons,
        text="Tip: import the schedule once per season, then import Season Stats and Career Stats separately.",
        anchor="w",
        bg=PANEL_BG,
        fg=MUTED_FG,
    ).pack(side="left", padx=12)

    velocity_panel = frame(parent, bg="#0b1520")
    velocity_panel.pack(fill="x", padx=14, pady=(8, 4))
    label(
        velocity_panel,
        text="Velocity League Import",
        bg="#0b1520",
        fg=TEXT_FG,
        font=("Segoe UI", 12, "bold"),
        anchor="w",
    ).pack(fill="x", padx=12, pady=(10, 3))
    label(
        velocity_panel,
        text=(
            "Import the active directory, selected-series standings, combined league career stats, schedule, and correct driver names/numbers "
            "from one public league URL such as https://www.velocityleague.gg/trrl. Use Series Name only when the league runs multiple series."
        ),
        bg="#0b1520",
        fg=MUTED_FG,
        justify="left",
        wraplength=900,
        anchor="w",
    ).pack(fill="x", padx=12, pady=(0, 8))
    velocity_form = frame(velocity_panel, bg="#0b1520")
    velocity_form.pack(fill="x", padx=12)
    velocity_defaults = {
        key: existing.get(key, default)
        for key, default in VELOCITY_LEAGUE_FIELDS
    }
    velocity_defaults.update(velocity_output_defaults(existing))
    velocity_entries = {}
    for row_number, (label_text, key) in enumerate(
        (
            ("Velocity League URL", "VELOCITY_LEAGUE_URL"),
            ("Series Name", "VELOCITY_SERIES_NAME"),
            ("Stats CSV", "VELOCITY_STATS_OUTPUT"),
            ("Career CSV", "VELOCITY_CAREER_OUTPUT"),
            ("Drivers CSV", "VELOCITY_DRIVERS_OUTPUT"),
            ("Schedule CSV", "VELOCITY_SCHEDULE_OUTPUT"),
        )
    ):
        label(velocity_form, text=label_text, anchor="w", width=22, bg="#0b1520", fg=MUTED_FG).grid(
            row=row_number,
            column=0,
            sticky="w",
            pady=3,
        )
        velocity_entry = entry(velocity_form, width=86)
        velocity_entry.insert(0, velocity_defaults[key])
        velocity_entry.grid(row=row_number, column=1, sticky="ew", pady=3)
        velocity_entries[key] = velocity_entry
    velocity_form.columnconfigure(1, weight=1)
    sim_racer_hub_state["velocity_entries"] = velocity_entries

    def velocity_values():
        return {key: widget.get().strip() for key, widget in velocity_entries.items()}

    def run_velocity_import(dry_run):
        data = velocity_values()
        if not data["VELOCITY_LEAGUE_URL"]:
            messagebox.showerror("Missing Velocity URL", "Paste a public Velocity League URL first.")
            return
        if not data["VELOCITY_DRIVERS_OUTPUT"]:
            data["VELOCITY_DRIVERS_OUTPUT"] = driver_roster_import_target(driver_csv_var.get(), "league/drivers.csv")
        result = run_velocity_league_import(
            url=data["VELOCITY_LEAGUE_URL"],
            series_name=data["VELOCITY_SERIES_NAME"],
            stats_output=data["VELOCITY_STATS_OUTPUT"],
            career_output=data["VELOCITY_CAREER_OUTPUT"],
            drivers_output=data["VELOCITY_DRIVERS_OUTPUT"],
            schedule_output=data["VELOCITY_SCHEDULE_OUTPUT"],
            manager_folder=(
                str(ROOT / "league" / league_folder_slug(get_profile_name() or "default"))
                if not dry_run and get_profile_name
                else ""
            ),
            dry_run=dry_run,
        )
        combined_output = result.stdout
        if result.stderr:
            combined_output += "\n" + result.stderr
        set_output(combined_output or "(No output)")
        if result.returncode == 0:
            if not dry_run:
                set_driver_csv_value(
                    data["VELOCITY_DRIVERS_OUTPUT"],
                    data["VELOCITY_STATS_OUTPUT"],
                    data["VELOCITY_CAREER_OUTPUT"],
                    data["VELOCITY_SCHEDULE_OUTPUT"],
                )
                load_driver_profiles()
            status.set(
                ("Previewed" if dry_run else "Imported")
                + " Velocity League stats, drivers, and schedule."
            )
        else:
            status.set("Velocity League import failed. Check the output panel.")

    velocity_buttons = frame(velocity_panel, bg="#0b1520")
    velocity_buttons.pack(fill="x", padx=12, pady=(8, 10))
    button(
        velocity_buttons,
        text="Preview Velocity Import",
        command=lambda: run_velocity_import(True),
        color="#334b64",
    ).pack(side="left", padx=4)
    button(
        velocity_buttons,
        text="Import Velocity Data",
        command=lambda: run_velocity_import(False),
        color=GREEN,
    ).pack(side="left", padx=4)

    output_box.pack(fill="x", expand=False, padx=14, pady=(8, 0))

    editor_panel = frame(parent, bg="#0b1520")
    editor_panel.pack(fill="x", expand=False, padx=14, pady=(4, 14))
    label(
        editor_panel,
        text="League Driver Profile Editor",
        bg="#0b1520",
        fg=TEXT_FG,
        font=("Segoe UI", 13, "bold"),
        anchor="w",
    ).pack(fill="x", padx=12, pady=(12, 4))
    label(
        editor_panel,
        text=(
            "Use this for league-only driver information. These fields update drivers.csv "
            "and are preserved when you import a Sim Racer Hub roster."
        ),
        bg="#0b1520",
        fg=MUTED_FG,
        justify="left",
        anchor="w",
        wraplength=900,
    ).pack(fill="x", padx=12, pady=(0, 8))

    editor_body = frame(editor_panel, bg="#0b1520")
    editor_body.pack(fill="x", expand=False, padx=12, pady=(0, 12))

    list_panel = frame(editor_body, bg="#0b1520")
    list_panel.pack(side="left", fill="both", expand=False, padx=(0, 14))
    label(
        list_panel,
        text="Drivers",
        bg="#0b1520",
        fg=MUTED_FG,
        font=("Segoe UI", 9, "bold"),
        anchor="w",
    ).pack(fill="x", pady=(0, 4))
    driver_list = tk.Listbox(
        list_panel,
        height=18,
        width=34,
        bg=FIELD_BG,
        fg=TEXT_FG,
        selectbackground=ACCENT,
        selectforeground="white",
        relief="flat",
        highlightthickness=1,
        highlightbackground="#26384c",
    )
    driver_list.pack(fill="both", expand=True)

    edit_panel = frame(editor_body, bg="#0b1520")
    edit_panel.pack(side="left", fill="both", expand=True)

    editor_path_row = frame(edit_panel, bg="#0b1520")
    editor_path_row.pack(fill="x", pady=(0, 8))
    label(
        editor_path_row,
        text="Driver CSV",
        bg="#0b1520",
        fg=MUTED_FG,
        width=14,
        anchor="w",
    ).pack(side="left")
    driver_csv_var = tk.StringVar(
        value=existing.get("LEAGUE_DRIVERS_CSV")
        or existing.get("SIMRACERHUB_DRIVERS_OUTPUT")
        or "league/drivers.csv"
    )
    driver_csv_entry = entry(editor_path_row, textvariable=driver_csv_var, width=72)
    driver_csv_entry.pack(side="left", fill="x", expand=True)

    editor_state = {"rows": [], "selected_index": None}
    profile_entries = {}

    def selected_driver_csv_path():
        return resolve_project_path(driver_csv_var.get() or "league/drivers.csv", ROOT)

    def set_entry_value(entry_widget, value):
        if hasattr(entry_widget, "set"):
            entry_widget.set(value)
            return
        entry_widget.delete(0, "end")
        entry_widget.insert(0, value)

    def set_driver_csv_value(driver_csv, season_stats_csv="", career_stats_csv="", race_schedule_csv=""):
        driver_csv = str(driver_csv or "league/drivers.csv").strip()
        driver_csv_var.set(driver_csv)
        if "LEAGUE_DRIVERS_CSV" in settings_entries:
            set_entry_value(settings_entries["LEAGUE_DRIVERS_CSV"], driver_csv)
        if "SIMRACERHUB_DRIVERS_OUTPUT" in entries:
            set_entry_value(entries["SIMRACERHUB_DRIVERS_OUTPUT"], driver_csv)
        if "VELOCITY_DRIVERS_OUTPUT" in entries:
            set_entry_value(entries["VELOCITY_DRIVERS_OUTPUT"], driver_csv)
        if season_stats_csv:
            if "LEAGUE_SEASON_STATS_CSV" in settings_entries:
                set_entry_value(settings_entries["LEAGUE_SEASON_STATS_CSV"], season_stats_csv)
            if "SIMRACERHUB_SEASON_STATS_OUTPUT" in entries:
                set_entry_value(entries["SIMRACERHUB_SEASON_STATS_OUTPUT"], season_stats_csv)
            if "VELOCITY_STATS_OUTPUT" in entries:
                set_entry_value(entries["VELOCITY_STATS_OUTPUT"], season_stats_csv)
            if "VELOCITY_CAREER_OUTPUT" in entries:
                set_entry_value(entries["VELOCITY_CAREER_OUTPUT"], career_stats_csv)
        if career_stats_csv:
            if "LEAGUE_CAREER_STATS_CSV" in settings_entries:
                set_entry_value(settings_entries["LEAGUE_CAREER_STATS_CSV"], career_stats_csv)
            if "SIMRACERHUB_CAREER_STATS_OUTPUT" in entries:
                set_entry_value(entries["SIMRACERHUB_CAREER_STATS_OUTPUT"], career_stats_csv)
        if race_schedule_csv:
            if "SIMRACERHUB_RACE_SCHEDULE_CSV" in entries:
                set_entry_value(entries["SIMRACERHUB_RACE_SCHEDULE_CSV"], race_schedule_csv)
            if "VELOCITY_SCHEDULE_OUTPUT" in entries:
                set_entry_value(entries["VELOCITY_SCHEDULE_OUTPUT"], race_schedule_csv)

    def sync_driver_csv_from_settings(values):
        set_driver_csv_value(
            values.get("LEAGUE_DRIVERS_CSV")
            or values.get("SIMRACERHUB_DRIVERS_OUTPUT")
            or "league/drivers.csv",
            values.get("LEAGUE_SEASON_STATS_CSV")
            or values.get("SIMRACERHUB_SEASON_STATS_OUTPUT")
            or "",
            values.get("LEAGUE_CAREER_STATS_CSV")
            or values.get("SIMRACERHUB_CAREER_STATS_OUTPUT")
            or "",
            values.get("SIMRACERHUB_RACE_SCHEDULE_CSV") or "",
        )
        load_driver_profiles()

    league_tab_state["sync_driver_csv_from_settings"] = sync_driver_csv_from_settings
    league_tab_state["sync_driver_csv_paths"] = set_driver_csv_value

    field_labels = [
        ("Name", "name"),
        ("Car Number", "car_number"),
        ("Hometown", "hometown"),
        ("State", "state"),
        ("Country", "country"),
        ("Driving Style", "driving_style"),
        ("Sponsor", "sponsor"),
        ("About / Driver Story", "about"),
        ("Car Image", "car_image"),
    ]

    fields_frame = frame(edit_panel, bg="#0b1520")
    fields_frame.pack(fill="x")
    for row_number, (label_text, key) in enumerate(field_labels):
        label(
            fields_frame,
            text=label_text,
            bg="#0b1520",
            fg=MUTED_FG,
            width=14,
            anchor="w",
        ).grid(row=row_number, column=0, sticky="w", pady=3)
        widget = entry(fields_frame, width=76)
        widget.grid(row=row_number, column=1, sticky="ew", pady=3)
        profile_entries[key] = widget
    fields_frame.columnconfigure(1, weight=1)

    def clear_profile_fields():
        for widget in profile_entries.values():
            widget.delete(0, "end")
        editor_state["selected_index"] = None
        driver_list.selection_clear(0, "end")

    def set_profile_fields(row):
        for key, widget in profile_entries.items():
            widget.delete(0, "end")
            widget.insert(0, row.get(key, ""))

    def current_profile_row():
        return {key: widget.get().strip() for key, widget in profile_entries.items()}

    def refresh_driver_list(select_index=None):
        driver_list.delete(0, "end")
        for row in editor_state["rows"]:
            driver_list.insert("end", driver_profile_label(row))
        if select_index is not None and 0 <= select_index < len(editor_state["rows"]):
            driver_list.selection_set(select_index)
            driver_list.see(select_index)
            editor_state["selected_index"] = select_index
            set_profile_fields(editor_state["rows"][select_index])

    def load_driver_profiles():
        path = selected_driver_csv_path()
        editor_state["rows"] = load_driver_profile_rows(path)
        editor_state["selected_index"] = None
        clear_profile_fields()
        refresh_driver_list()
        status.set(f"Loaded {len(editor_state['rows'])} driver profile(s) from {path}.")

    def browse_driver_csv():
        selected = filedialog.askopenfilename(
            title="Choose league drivers.csv",
            initialdir=str(ROOT / "league"),
            filetypes=[
                ("CSV files", "*.csv"),
                ("All files", "*.*"),
            ],
        )
        if not selected:
            return
        path = Path(selected)
        try:
            relative = path.relative_to(ROOT)
            display_path = str(relative).replace("\\", "/")
        except ValueError:
            display_path = str(path)
        set_driver_csv_value(display_path)
        load_driver_profiles()

    def create_profile_league_csv():
        profile_name = get_profile_name() if get_profile_name else ""
        if not profile_name:
            profile_name = simpledialog.askstring(
                "League profile name",
                "Enter a name for this league/profile:",
            )
        profile_name = sanitize_profile_name(profile_name)
        if not profile_name:
            messagebox.showerror("Missing profile", "Enter or select a profile name first.")
            return
        drivers_csv, season_stats_csv, career_stats_csv, race_schedule_csv = league_csv_paths_for_profile(profile_name)
        ensure_empty_driver_profile_csv(resolve_project_path(drivers_csv, ROOT))
        ensure_empty_race_schedule_csv(resolve_project_path(race_schedule_csv, ROOT))
        stats_header = (
            "name,car_number,stats_scope,starts,wins,top_fives,top_tens,poles,"
            "avg_finish,last_finish,points_position,points_to_next,"
            "track_starts,track_wins,best_track_finish,notes\n"
        )
        for stats_csv in (season_stats_csv, career_stats_csv):
            stats_path = resolve_project_path(stats_csv, ROOT)
            stats_path.parent.mkdir(parents=True, exist_ok=True)
            if not stats_path.exists():
                stats_path.write_text(stats_header, encoding="utf-8")
        set_driver_csv_value(drivers_csv, season_stats_csv, career_stats_csv, race_schedule_csv)
        load_driver_profiles()
        status.set(
            f"Created/selected league CSVs for {profile_name}: drivers, season, career, and race schedule."
        )

    def save_driver_profiles():
        path = save_driver_profile_rows(selected_driver_csv_path(), editor_state["rows"])
        status.set(f"Saved {len(editor_state['rows'])} driver profile(s) to {path}.")

    def save_current_driver():
        row = current_profile_row()
        if not row["name"] and not row["car_number"]:
            messagebox.showerror("Missing driver", "Add at least a driver name or car number.")
            return
        index = editor_state.get("selected_index")
        if index is None or index >= len(editor_state["rows"]):
            editor_state["rows"].append(row)
            index = len(editor_state["rows"]) - 1
        else:
            editor_state["rows"][index] = row
        save_driver_profiles()
        refresh_driver_list(index)

    def delete_current_driver():
        index = editor_state.get("selected_index")
        if index is None or index >= len(editor_state["rows"]):
            return
        removed = driver_profile_label(editor_state["rows"][index])
        del editor_state["rows"][index]
        clear_profile_fields()
        save_driver_profiles()
        refresh_driver_list()
        status.set(f"Deleted driver profile: {removed}.")

    def choose_driver_image():
        selected = filedialog.askopenfilename(
            title="Choose driver car image",
            filetypes=[
                ("Image files", "*.png *.jpg *.jpeg *.webp *.gif *.tga"),
                ("All files", "*.*"),
            ],
        )
        if not selected:
            return
        widget = profile_entries["car_image"]
        widget.delete(0, "end")
        widget.insert(0, selected)
        status.set("Selected driver car image. Click Save Driver to update drivers.csv.")

    def on_driver_selected(_event=None):
        selection = driver_list.curselection()
        if not selection:
            return
        index = int(selection[0])
        editor_state["selected_index"] = index
        set_profile_fields(editor_state["rows"][index])

    driver_list.bind("<<ListboxSelect>>", on_driver_selected)

    editor_buttons = frame(edit_panel, bg="#0b1520")
    editor_buttons.pack(fill="x", pady=(10, 0))
    button(editor_buttons, text="Load Drivers", command=load_driver_profiles, color="#334b64").pack(
        side="left",
        padx=(0, 6),
    )
    button(editor_buttons, text="Browse CSV", command=browse_driver_csv, color="#334b64").pack(
        side="left",
        padx=6,
    )
    button(
        editor_buttons,
        text="Create CSV for Profile",
        command=create_profile_league_csv,
        color="#334b64",
    ).pack(
        side="left",
        padx=6,
    )
    button(editor_buttons, text="New Driver", command=clear_profile_fields, color="#334b64").pack(
        side="left",
        padx=6,
    )
    button(editor_buttons, text="Choose Car Image", command=choose_driver_image, color="#334b64").pack(
        side="left",
        padx=6,
    )
    button(editor_buttons, text="Save Driver", command=save_current_driver, color=GREEN).pack(
        side="left",
        padx=6,
    )
    button(editor_buttons, text="Delete Driver", command=delete_current_driver, color=STOP_RED).pack(
        side="left",
        padx=6,
    )

    driver_stats_panel = frame(parent, bg="#0b1520")
    driver_stats_panel.pack(fill="x", expand=False, padx=14, pady=(0, 14))
    driver_stats_header = frame(driver_stats_panel, bg="#0b1520")
    driver_stats_header.pack(fill="x", padx=12, pady=(10, 6))
    label(driver_stats_header, text="League Driver Statistics", bg="#0b1520", fg=TEXT_FG, font=("Segoe UI", 12, "bold"), anchor="w").pack(side="left")
    driver_stats_summary = tk.StringVar(value="Results imported through League Manager will appear here.")
    label(driver_stats_header, textvariable=driver_stats_summary, bg="#0b1520", fg=MUTED_FG, anchor="w").pack(side="left", padx=14)
    driver_stats_tree = ttk.Treeview(driver_stats_panel, columns=("pos", "number", "driver", "starts", "wins", "top5", "top10", "poles", "led", "avg", "last", "points"), show="headings", height=10)
    for key, title, width in (("pos", "Pos", 38), ("number", "#", 42), ("driver", "Driver", 180), ("starts", "Starts", 48), ("wins", "Wins", 42), ("top5", "Top 5", 45), ("top10", "Top 10", 50), ("poles", "Poles", 42), ("led", "Laps Led", 55), ("avg", "Avg Finish", 65), ("last", "Last", 42), ("points", "Points", 55)):
        driver_stats_tree.heading(key, text=title)
        driver_stats_tree.column(key, width=width, anchor="w" if key == "driver" else "center")
    driver_stats_tree.pack(fill="x", expand=False, padx=12, pady=(0, 8))

    def refresh_driver_statistics():
        driver_stats_tree.delete(*driver_stats_tree.get_children())
        profile_name = (get_profile_name() if get_profile_name else "") or "default"
        saved_results = load_race_results(ROOT / "league" / league_folder_slug(profile_name) / "results.json")
        standings = calculate_standings(saved_results)
        for position, item in enumerate(standings, start=1):
            points = float(item["points"])
            points_text = str(int(points)) if points.is_integer() else str(round(points, 3)).rstrip("0").rstrip(".")
            driver_stats_tree.insert("", "end", values=(position, item["car_number"], item["name"], item["starts"], item["wins"], item["top_fives"], item["top_tens"], item["poles"], item["laps_led"], item["average_finish"], item.get("last_finish", ""), points_text))
        driver_stats_tree.configure(height=max(4, min(40, len(standings) or 4)))
        driver_stats_summary.set(f"{len(standings)} driver(s) built from {len(saved_results)} saved race(s)." if standings else "Results imported through League Manager will appear here.")

    button(driver_stats_header, text="Refresh Stats", command=refresh_driver_statistics, color="#334b64").pack(side="right")
    league_tab_state["refresh_driver_statistics"] = refresh_driver_statistics

    load_driver_profiles()
    refresh_driver_statistics()


def build_help_tab(
    parent,
    label,
    frame,
    button,
    get_values=None,
    broadcast_running=None,
    status=None,
):
    content = frame(parent, bg=PANEL_BG)
    content.pack(fill="both", expand=True, padx=18, pady=16)

    def section(title, body):
        label(
            content,
            text=title,
            bg=PANEL_BG,
            fg=TEXT_FG,
            font=("Segoe UI", 13, "bold"),
            anchor="w",
        ).pack(fill="x", pady=(14, 4))
        label(
            content,
            text=body.strip(),
            bg=PANEL_BG,
            fg=MUTED_FG,
            font=("Segoe UI", 10),
            justify="left",
            anchor="w",
            wraplength=900,
        ).pack(fill="x", pady=(0, 4))

    label(
        content,
        text="RGC AI Broadcast Studio Setup Guide",
        bg=PANEL_BG,
        fg=TEXT_FG,
        font=("Segoe UI", 17, "bold"),
        anchor="w",
    ).pack(fill="x", pady=(0, 6))
    label(
        content,
        text=(
            "Use this page as the quick in-app guide. Set up keys, voices, overlays, "
            "league data, and profiles before race night."
        ),
        bg=PANEL_BG,
        fg=MUTED_FG,
        font=("Segoe UI", 10),
        justify="left",
        anchor="w",
        wraplength=900,
    ).pack(fill="x", pady=(0, 8))

    link_row = frame(content, bg=PANEL_BG)
    link_row.pack(fill="x", pady=(0, 12))
    button(
        link_row,
        text="Open OpenAI API Keys",
        command=lambda: open_external_link("https://platform.openai.com/api-keys"),
        color="#334b64",
    ).pack(side="left", padx=(0, 8))
    button(
        link_row,
        text="Open ElevenLabs API Keys",
        command=lambda: open_external_link("https://elevenlabs.io/app/developers/api-keys"),
        color="#334b64",
    ).pack(side="left", padx=(0, 8))
    button(
        link_row,
        text="Open SIMRacingApps",
        command=lambda: open_external_link(SIM_RACING_APPS_HOME_URL),
        color="#334b64",
    ).pack(side="left", padx=(0, 8))
    button(
        link_row,
        text="Open SIMRacingApps Patch",
        command=lambda: open_external_link(SIM_RACING_APPS_PATCH_URL),
        color="#334b64",
    ).pack(side="left", padx=(0, 8))
    button(
        link_row,
        text="Open GitHub Releases",
        command=lambda: open_external_link(GITHUB_RELEASES_URL),
        color="#334b64",
    ).pack(side="left", padx=(0, 8))

    checklist_panel = frame(content, bg="#0b1520")
    checklist_panel.pack(fill="x", pady=(4, 14))
    checklist_header = frame(checklist_panel, bg="#0b1520")
    checklist_header.pack(fill="x", padx=12, pady=(10, 4))
    label(
        checklist_header,
        text="First-Time Setup Checklist",
        bg="#0b1520",
        fg=TEXT_FG,
        font=("Segoe UI", 13, "bold"),
        anchor="w",
    ).pack(side="left")
    checklist_summary = label(
        checklist_header,
        text="",
        bg="#0b1520",
        fg=MUTED_FG,
        anchor="w",
    )
    checklist_summary.pack(side="left", padx=(12, 0))
    checklist_rows = frame(checklist_panel, bg="#0b1520")
    checklist_rows.pack(fill="x", padx=12, pady=(0, 10))

    def render_checklist():
        for widget in checklist_rows.winfo_children():
            widget.destroy()
        values = get_values() if get_values else launcher_defaults(load_env_file())
        rows = build_first_time_setup_checklist(
            values,
            root=ROOT,
            broadcast_running=broadcast_running() if broadcast_running else False,
        )
        level_colors = {
            "ok": GREEN,
            "warn": "#d19a2a",
            "off": MUTED_FG,
        }
        icons = {
            "ok": "✓",
            "warn": "!",
            "off": "○",
        }
        ready_count = sum(1 for _name, _state, _detail, level in rows if level == "ok")
        warn_count = sum(1 for _name, _state, _detail, level in rows if level == "warn")
        checklist_summary.configure(
            text=f"{ready_count} ready | {warn_count} need attention"
        )
        for index, (name, state_text, detail, level) in enumerate(rows):
            row = frame(checklist_rows, bg="#0b1520")
            row.grid(
                row=index,
                column=0,
                sticky="ew",
                pady=2,
            )
            label(
                row,
                text=icons.get(level, "○"),
                width=3,
                anchor="w",
                bg="#0b1520",
                fg=level_colors.get(level, MUTED_FG),
                font=("Segoe UI", 10, "bold"),
            ).pack(side="left")
            label(
                row,
                text=name,
                width=20,
                anchor="w",
                bg="#0b1520",
                fg=TEXT_FG,
                font=("Segoe UI", 9, "bold"),
            ).pack(side="left")
            label(
                row,
                text=state_text,
                width=14,
                anchor="w",
                bg="#0b1520",
                fg=level_colors.get(level, MUTED_FG),
                font=("Segoe UI", 9, "bold"),
            ).pack(side="left")
            label(
                row,
                text=detail,
                anchor="w",
                bg="#0b1520",
                fg=MUTED_FG,
                justify="left",
                wraplength=620,
            ).pack(side="left", fill="x", expand=True)
        checklist_rows.columnconfigure(0, weight=1)
        if status:
            status.set("First-time setup checklist refreshed.")

    checklist_button_row = frame(checklist_panel, bg="#0b1520")
    checklist_button_row.pack(fill="x", padx=12, pady=(0, 10))
    button(
        checklist_button_row,
        text="Refresh Checklist",
        command=render_checklist,
        color="#334b64",
    ).pack(side="left")
    label(
        checklist_button_row,
        text="Use this before sending a build to an admin or before league night.",
        bg="#0b1520",
        fg=MUTED_FG,
        anchor="w",
    ).pack(side="left", padx=(12, 0))
    render_checklist()

    section(
        "1. Install and open the studio",
        """
        Run the Windows installer, then open RGC AI Broadcast Studio from the desktop icon.
        The installer sets up the app files, creates shortcuts, and runs the Python setup needed by this early version.
        If setup says Python is missing, install Python 3.11 or newer and make sure "Add python.exe to PATH" is checked.
        """,
    )
    section(
        "2. OpenAI setup",
        """
        OpenAI writes the broadcast commentary. Put your OpenAI API key into OPENAI_API_KEY.
        USE_OPENAI controls the default startup setting. During a live broadcast, Producer Assist can turn OpenAI on or off.
        OPENAI_MODEL controls which OpenAI model writes the broadcast. Never stream or share your API key.
        """,
    )
    section(
        "3. ElevenLabs setup",
        """
        ElevenLabs creates the spoken broadcaster voices. Put your ElevenLabs API key into ELEVENLABS_API_KEY.
        LEAD_VOICE_ID is the play-by-play voice. COLOR_VOICE_ID is the analyst voice. PIT_VOICE_ID is pit road and strategy.
        USE_ELEVENLABS controls the default startup setting. During a live broadcast, Producer Assist can mute or enable voice playback.
        """,
    )
    section(
        "4. Overlay setup",
        """
        Copy the Streamlabs / OBS browser-source link from Broadcast Settings and add it as a Browser Source.
        Use 1920 x 1080 for the browser source size. Put the overlay source above your iRacing capture.
        Add event title, race sponsor, series name, and sponsor logos before saving settings.
        The Producer Assist link is a private control-room page for the broadcaster, not a source for the stream.
        """,
    )
    section(
        "5. Optional car graphics setup",
        f"""
        RGC AI Broadcast Studio can run without SIMRacingApps or Trading Paints, but live 3D car renders, styled car numbers, and accurate custom paints work best when both are running in the background.

        Recommended SIMRacingApps setup:
        1. Download the original SIMRacingAppsServer from {SIM_RACING_APPS_HOME_URL}
        2. Download the patched build from {SIM_RACING_APPS_PATCH_URL}
        3. Run SIMRacingAppsServer before starting the broadcast.
        4. Leave the SIMRacingAppsServer window open or minimized while iRacing is running.
        5. Refresh Broadcast Health. SIMRacingApps should show as Running.

        Recommended Trading Paints setup:
        1. Start Trading Paints before joining the iRacing session.
        2. Let it download/update driver paints while the session loads.
        3. Refresh Broadcast Health. Trading Paints should show as Running.

        If SIMRacingApps is not running, the broadcast still works. The overlay will fall back to numbers/manual graphics where possible, but car renders may be missing or less accurate.
        If Trading Paints is not running, the broadcast still works, but custom paints may be stale, missing, or less accurate.
        """,
    )
    section(
        "6. Practice, qualifying, and caution music",
        """
        Practice music loops during practice. Qualifying music loops during qualifying when files are selected.
        MP3 or WAV files are recommended. OGA/OGG files are not supported by the hidden Windows audio player.
        Sponsor graphics for practice, qualifying, cautions, and the title overlay come from the Sponsor 1-5 logos and cause logo.
        Caution audio is used during caution replay/presentation segments.
        The Studio Volume slider controls program audio, including music beds and ElevenLabs voice playback.
        """,
    )
    section(
        "7. League and Sim Racer Hub data",
        """
        For official race testing, league files are optional. For league races, use the League / Sim Racer Hub tab.
        A clean Sim Racer Hub URL can be https://simracerhub.com, then fill in League ID, Series ID, and Season ID.
        Preview imports first. Driver imports preserve manual About stories like hometown, sponsor, team, and driving style.
        If schedule import finds no rows, add the first race schedule_id in First Race Schedule ID and import again.
        Race Schedule CSV maps track_name to schedule_id for every race in the season. The post-race Discord report uses the
        current iRacing track, Season ID, and imported schedule to add Sim Racer Hub race results and standings automatically.

        For a Velocity League profile, paste the public league home URL into Velocity League URL. One import automatically reads
        the active directory, selected-series standings, combined league career statistics, and full schedule. If the league has
        multiple series, enter the series URL key such as tuesday-night-trucks or paste that series/standings URL. Velocity season
        data goes to season.csv, combined career data goes to career.csv, and manually entered hometown, state, sponsor, About story,
        and car image are preserved when a matching driver is imported again.
        """,
    )
    section(
        "8. Profiles",
        """
        Profiles let you keep separate setups for league races, official testing, AI broadcast defaults, or human-broadcaster defaults.
        To make one, type a name in New Profile Name and click Create Profile. Later, choose it from the Profile list and click Load Profile.
        If a profile is selected, Save Settings updates both the active settings file and that selected profile.
        Use Delete beside the profile list to remove old test profiles you no longer need.
        Before race night, load the correct profile and refresh Broadcast Health.
        """,
    )
    section(
        "9. Start Broadcast and Producer Assist",
        """
        Start Broadcast runs the broadcast engine, overlay, Producer Assist control room, cameras, and caution replay controls.
        Producer Assist opens automatically after Start Broadcast. If you close it, use the Producer Assist link to open it again.
        Use Producer Assist to turn OpenAI, ElevenLabs, and auto cameras on or off during the same running broadcast.
        Manual driver or camera selection takes camera control and holds the selected driver card while the human broadcaster makes the call.
        Click Return Live when you want automatic commentary and cameras to resume.
        Stop Broadcast stops a broadcast launched by the studio.

        For an ordinary AI or human-assisted broadcast, start the Studio while the iRacing session is live during practice,
        qualifying, grid, or race. Do not use Start Broadcast by itself to call a saved replay. Use Driver Mode and
        Play Recorded Broadcast for the supported recorded-race workflow described below.

        """,
    )
    section(
        "10. Driver Mode and recorded broadcasts",
        """
        Driver Mode records the live race while you drive without playing broadcaster audio or allowing automatic camera changes.

        1. Turn on Driver Mode — Record Race Silently and click Start Broadcast before or during the live event.
        2. Race normally. Keep the Studio running so it can save telemetry, approved calls, overlays, and camera targets.
        3. After the race, save/open the matching iRacing replay and turn Driver Mode off.
        4. Choose the recording with Recorded Broadcast File. Keep its .jsonl, .events.jsonl, and .capture.json files together.
        5. Click Play Recorded Broadcast. You can press this before starting replay playback; the Studio waits silently until replay frames move.

        The replay frame counter controls timing, so pausing or changing replay speed also pauses or changes the recorded broadcast timing.
        You may begin at practice, qualifying, grid, or race; the Studio finds the current session location and skips earlier saved calls.
        During cautions, Producer Assist may take camera control, rewind, change drivers or angles, and then Return Live to the current recorded-broadcast time.
        Run a short test before relying on Driver Mode for a full league production because the matching saved iRacing replay is required.
        """,
    )
    section(
        "11. Producer Assist broadcast tools",
        """
        Producer Assist is both the AI control room and a tool for human broadcasters. It shows director suggestions, current broadcast focus,
        driver and league statistics, pit strategy, points information, broadcast notes, and camera/replay controls.

        Use the leaderboard selector for Top Down, Scroll, Flo, or Brazen without stepping through every style on air.
        Manual sponsor buttons play a chosen Sponsor 1-5 item. Crank It Up, caution music, and presentation graphics can also be triggered manually.
        During a caution, the full-screen Caution Review Slate or selected review video can hide camera searching and rewinding from viewers.
        The top-ten reset graphic, pit-road report, race recap, points, and final-results graphics are handled through the same running overlay.

        The pre-race show introduces Mike, Jeff, and Sarah before the starting-lineup sponsor and full grid. If the race goes green early,
        the Studio protects the remaining lineup calls, finishes announcing the field, and then makes the opening green-flag call.
        """,
    )
    section(
        "12. Updates",
        """
        Use Check for Updates to compare this installed version against the latest GitHub Release.
        Early versions open the release/download page instead of auto-installing. This is safer while the app is still moving quickly.
        """,
    )
    section(
        "13. Race-night checklist",
        """
        Open iRacing, open Streamlabs/OBS, confirm the browser overlay is visible, load your profile,
        refresh Broadcast Health, then start during practice. Run a short smoke test before league night:
        open the launcher, start, check overlay, stop. Full race tests are only needed when broadcast logic changes.
        """,
    )


def main():
    run_gui()


if __name__ == "__main__":
    main()
