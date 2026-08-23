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

try:
    import tomllib
except ModuleNotFoundError:  # pragma: no cover - Python < 3.11 fallback
    import tomli as tomllib


ROOT = Path(__file__).resolve().parent
ENV_PATH = ROOT / ".env"
STATIC_ASSET_DIR = ROOT / "production" / "static"
RUNTIME_DIR = ROOT / ".runtime"
BROADCAST_PID_PATH = RUNTIME_DIR / "broadcast.pid"
PROFILE_DIR = ROOT / "profiles"
BROADCAST_PROCESS = None
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
    ("OPENAI_MODEL", "gpt-5.5"),
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
    ("OVERLAY_HOST", "127.0.0.1"),
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
    ("PRACTICE_MUSIC_PLAYLIST", ""),
    ("QUALIFYING_MUSIC_PLAYLIST", ""),
    ("STUDIO_VOLUME", "65"),
    ("CAUTION_REPLAY_AUDIO", ""),
    ("POST_RACE_INTERVIEWS_ENABLED", "false"),
    ("RACE_ADMIN_MODE", "false"),
    ("RACE_ADMIN_SEND_MODE", "clipboard"),
    ("DISCORD_RACE_REPORT_ENABLED", "false"),
    ("DISCORD_RACE_REPORT_WEBHOOK_URL", ""),
    ("DISCORD_RACE_REPORT_USE_OPENAI", "true"),
    ("USE_LEAGUE_DRIVER_NOTES", "false"),
    ("LEAGUE_DRIVERS_CSV", "league/drivers.csv"),
    ("LEAGUE_SEASON_STATS_CSV", "league/season.csv"),
    ("LEAGUE_CAREER_STATS_CSV", "league/career.csv"),
    ("STAGE_END_LAPS", ""),
    ("LEAGUE_FUEL_PERCENT", ""),
    ("LEAGUE_ENGINE_POWER_PERCENT", ""),
    ("LEAGUE_TIRE_SETS", ""),
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
    ("DISCORD_BOT_ENABLED", "false"),
    ("DISCORD_BOT_TOKEN", ""),
    ("DISCORD_GUILD_ID", ""),
    ("DISCORD_BOOTH_CHANNEL_ID", ""),
    ("DISCORD_WAITING_CHANNEL_ID", ""),
    ("DISCORD_INTERVIEW_CHANNEL_ID", ""),
    ("REMOTE_PRODUCER_ENABLED", "false"),
    ("REMOTE_PRODUCER_RELAY_URL", ""),
    ("REMOTE_PRODUCER_SESSION_CODE", ""),
    ("REMOTE_PRODUCER_PIN", ""),
]

SAVED_FIELDS = LAUNCHER_FIELDS + LEGACY_SPONSOR_FIELDS + SIM_RACER_HUB_FIELDS

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
    "OVERLAY_HOST": "Remote Producer Assist Access",
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
    "PRACTICE_MUSIC_PLAYLIST": "Practice Music Playlist",
    "QUALIFYING_MUSIC_PLAYLIST": "Qualifying Music Playlist",
    "CAUTION_REPLAY_AUDIO": "Caution Replay Music",
    "POST_RACE_INTERVIEWS_ENABLED": "Post-Race Interviews",
    "RACE_ADMIN_MODE": "Race Admin Mode",
    "RACE_ADMIN_SEND_MODE": "Race Admin Send Mode",
    "DISCORD_RACE_REPORT_ENABLED": "Discord Race Report",
    "DISCORD_RACE_REPORT_WEBHOOK_URL": "Race Report Webhook URL",
    "DISCORD_RACE_REPORT_USE_OPENAI": "Use OpenAI Race Recap",
    "USE_LEAGUE_DRIVER_NOTES": "Use League Driver Profiles",
    "LEAGUE_DRIVERS_CSV": "Driver Profiles CSV",
    "LEAGUE_SEASON_STATS_CSV": "Season Stats CSV",
    "LEAGUE_CAREER_STATS_CSV": "Career Stats CSV",
    "STAGE_END_LAPS": "Stage End Laps",
    "LEAGUE_FUEL_PERCENT": "Fuel Percent",
    "LEAGUE_ENGINE_POWER_PERCENT": "Engine Power Percent",
    "LEAGUE_TIRE_SETS": "Tire Sets",
}

BROADCAST_FIELD_SECTIONS = {
    "USE_OPENAI": "AI Commentary",
    "USE_ELEVENLABS": "Broadcaster Voices",
    "OVERLAY_EVENT_TITLE": "Event Sponsors / Overlay Links",
    "PRACTICE_MUSIC_PLAYLIST": "Practice / Qualifying / Caution Music",
    "POST_RACE_INTERVIEWS_ENABLED": "Race Flow",
    "RACE_ADMIN_MODE": "Race Control",
    "DISCORD_RACE_REPORT_ENABLED": "Discord Race Report",
    "USE_LEAGUE_DRIVER_NOTES": "League Data",
    "LEAGUE_FUEL_PERCENT": "League Race Package",
}

BROADCAST_FIELD_HELP = {
    "USE_OPENAI": "Required for the full AI broadcast. Turn this off when a human broadcaster only wants prompts, cameras, and overlays.",
    "OPENAI_API_KEY": "Required when OpenAI commentary is on. Keep this private and never show it on stream.",
    "OPENAI_MODEL": "Model used to write broadcast lines and Discord recaps. Leave the default unless you are testing another model.",
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
    "OVERLAY_LEADERBOARD_STYLE": "side keeps the NASCAR-style left leaderboard. ticker scrolls across the top under the title. flo uses a compact two-row top leaderboard with sponsor and series logos.",
    "OVERLAY_HOST": "Use 127.0.0.1 for this PC only. Use 0.0.0.0 when trusted helpers connect through Tailscale. The Producer Assist / Remote Admin Link is the link to send to trusted admins on your Tailscale network.",
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
    "PRACTICE_MUSIC_PLAYLIST": "Practice music playlist. Multiple songs are separated with semicolons and loop during practice.",
    "QUALIFYING_MUSIC_PLAYLIST": "Qualifying music playlist. Multiple songs are separated with semicolons and loop during qualifying. Sponsor graphics come from Sponsor 1-5 logos.",
    "CAUTION_REPLAY_AUDIO": "Music bed used during caution replay/presentation segments.",
    "POST_RACE_INTERVIEWS_ENABLED": "If true, the AI finishes the race recap/top 10 and then hands off to human post-race interviews for the top three. If false, it does the normal signoff.",
    "RACE_ADMIN_MODE": "Enables hosted-race admin commands in Producer Assist. Keep off unless this PC has race admin rights.",
    "RACE_ADMIN_SEND_MODE": "clipboard is safest for stream. open_chat/ui_paste can bring iRacing chat or the iRacing window onto the broadcast PC capture. For clean race control, use a trusted remote admin on another PC through Producer Assist/Tailscale.",
    "DISCORD_RACE_REPORT_ENABLED": "Posts an automatic post-race recap to a Discord webhook after the finish order stabilizes.",
    "DISCORD_RACE_REPORT_WEBHOOK_URL": "Required when Discord Race Report is true. Create this webhook in the Discord results channel.",
    "DISCORD_RACE_REPORT_USE_OPENAI": "Uses OpenAI for a more natural race recap. If off, the Studio posts a simpler generated recap.",
    "USE_LEAGUE_DRIVER_NOTES": "Turns on league driver profiles, about stories, season stats, career stats, teams, sponsors, hometowns, and driving styles.",
    "LEAGUE_DRIVERS_CSV": "Driver profile CSV used for About stories and league-specific info.",
    "LEAGUE_SEASON_STATS_CSV": "Current-season stats CSV imported from Sim Racer Hub.",
    "LEAGUE_CAREER_STATS_CSV": "Career/all-season stats CSV imported from Sim Racer Hub.",
    "STAGE_END_LAPS": "Optional comma-separated stage end laps. Example: 30,60.",
    "LEAGUE_FUEL_PERCENT": "Optional league race setting. Example: 65 means Mike can mention fuel is set at 65 percent during the opening.",
    "LEAGUE_ENGINE_POWER_PERCENT": "Optional league race setting. Example: 90 means Mike can mention engine power is set at 90 percent.",
    "LEAGUE_TIRE_SETS": "Optional league race tire limit. Example: 3 means Mike can mention three tire sets are available.",
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
    "PRACTICE_MUSIC_PLAYLIST",
    "QUALIFYING_MUSIC_PLAYLIST",
    "POST_RACE_INTERVIEWS_ENABLED",
    "DISCORD_RACE_REPORT_ENABLED",
    "DISCORD_RACE_REPORT_WEBHOOK_URL",
    "USE_LEAGUE_DRIVER_NOTES",
    "STAGE_END_LAPS",
    "LEAGUE_FUEL_PERCENT",
    "LEAGUE_ENGINE_POWER_PERCENT",
    "LEAGUE_TIRE_SETS",
}

BOOLEAN_SETTING_KEYS = {
    "USE_OPENAI",
    "USE_ELEVENLABS",
    "USE_SIM_RACING_APPS",
    "USE_SPONSOR_READS",
    "POST_RACE_INTERVIEWS_ENABLED",
    "RACE_ADMIN_MODE",
    "DISCORD_RACE_REPORT_ENABLED",
    "DISCORD_RACE_REPORT_USE_OPENAI",
    "USE_LEAGUE_DRIVER_NOTES",
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
    return launcher_defaults(load_env_file(path))


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


def driver_roster_import_target(active_driver_csv="", sim_racer_hub_output=""):
    """Return the one driver CSV the editor and Sim Racer Hub import should share."""
    active = str(active_driver_csv or "").strip()
    if active:
        return active
    configured = str(sim_racer_hub_output or "").strip()
    return configured or "league/drivers.csv"


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
            return 200 <= int(getattr(response, "status", 200)) < 500
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
                "Not running",
                "Start SIMRacingAppsServer before broadcasting, or set Use SIMRacingApps Car Graphics to false.",
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

    if str(values.get("OVERLAY_HOST", "127.0.0.1") or "").strip() == "0.0.0.0":
        rows.append(
            (
                "Remote Producer Assist",
                "Shared",
                f"Send trusted helpers the Producer Assist link: {producer_link_for_host('0.0.0.0')}",
                "ok",
            )
        )
    else:
        rows.append(
            (
                "Remote Producer Assist",
                "Local only",
                "Use Remote Producer Assist Access 0.0.0.0 when a trusted helper will connect through Tailscale.",
                "off",
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
            rows.append(
                (
                    "League Profiles",
                    "Ready",
                    "Driver, season stats, and career stats CSV files found.",
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
        "Remote Producer Assist",
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
    root = Path(root)
    league_dir = root / "league"
    league_dir.mkdir(exist_ok=True)

    copied = []
    for name in ("drivers.csv", "season.csv", "career.csv"):
        source = root / "league.example" / name
        target = league_dir / name
        if source.exists() and not target.exists():
            shutil.copyfile(source, target)
            copied.append(str(target))
    stats_header = (
        "name,car_number,stats_scope,starts,wins,top_fives,top_tens,poles,"
        "avg_finish,last_finish,points_position,points_to_next,"
        "track_starts,track_wins,best_track_finish,notes\n"
    )
    for name, scope in (("season.csv", "season"), ("career.csv", "career")):
        target = league_dir / name
        if not target.exists():
            target.write_text(stats_header, encoding="utf-8")
            copied.append(str(target))
    return copied


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


def broadcast_command():
    return [
        sys.executable,
        str(ROOT / "app.py"),
        "--overlay",
        "--camera-mode",
        "auto",
        "--incident-replay",
        "auto",
    ]


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
    )


def launch_broadcast():
    global BROADCAST_PROCESS
    if is_process_running(BROADCAST_PROCESS):
        return BROADCAST_PROCESS

    env = os.environ.copy()
    BROADCAST_PROCESS = subprocess.Popen(broadcast_command(), cwd=ROOT, env=env)
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
    league_tab = frame(notebook, bg=PANEL_BG)
    help_tab = frame(notebook, bg=PANEL_BG)
    notebook.add(settings_tab, text="Broadcast Settings")
    notebook.add(league_tab, text="League / Sim Racer Hub")
    notebook.add(help_tab, text="Help / Setup Guide")

    settings_content = settings_tab
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
    sim_racer_hub_state = {"entries": {}, "career_mode": None}
    league_tab_state = {}
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
        if key == "OVERLAY_LEADERBOARD_STYLE":
            entry_widget = ttk.Combobox(
                settings_frame,
                values=("side", "ticker", "flo"),
                width=69,
                state="readonly",
            )
            entry_widget.set(existing.get(key, "side") or "side")
        elif key == "OVERLAY_HOST":
            entry_widget = ttk.Combobox(
                settings_frame,
                values=("127.0.0.1", "0.0.0.0"),
                width=69,
                state="readonly",
            )
            entry_widget.set(existing.get(key, "127.0.0.1") or "127.0.0.1")
        elif key in BOOLEAN_SETTING_KEYS:
            entry_widget = ttk.Combobox(
                settings_frame,
                values=("false", "true"),
                width=69,
                state="readonly",
            )
            entry_widget.set(bool_setting_text(existing, key, _default))
        elif key == "RACE_ADMIN_SEND_MODE":
            entry_widget = ttk.Combobox(
                settings_frame,
                values=("clipboard", "open_chat", "ui_paste"),
                width=69,
                state="readonly",
            )
            entry_widget.set(existing.get(key, "clipboard") or "clipboard")
        else:
            entry_widget = entry(settings_frame, width=72)
            entry_widget.insert(0, existing.get(key, ""))
        if isinstance(entry_widget, ttk.Combobox):
            disable_combobox_mousewheel(entry_widget)
        entry_widget.grid(row=settings_grid_row, column=1, sticky="ew", pady=3)
        entries[key] = entry_widget
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

        if key == "OVERLAY_HOST":
            add_settings_hint(
                "Use 127.0.0.1 for this PC only. Use 0.0.0.0 when a trusted helper will open Producer Assist through Tailscale. "
                f"Tailscale download: {TAILSCALE_WINDOWS_DOWNLOAD_URL}"
            )

        if key == "REMOTE_PRODUCER_PIN":
            add_settings_hint(
                "Optional helper PIN label for trusted remote Producer Assist sessions. "
                "For v1.0, use Tailscale with Remote Producer Assist Access set to 0.0.0.0."
            )

        if key == "RACE_ADMIN_MODE":
            add_settings_hint(
                "Hosted-race admin controls for cautions, penalties, wave-bys, EOLs, DQs, and removals. "
                "Keep this off unless the broadcaster PC is an iRacing admin in the hosted session."
            )

        if key == "RACE_ADMIN_SEND_MODE":
            add_settings_hint(
                "clipboard is broadcast-safe and only copies the iRacing command for manual send. "
                "open_chat copies it and opens iRacing text chat for quick Ctrl+V/Enter. "
                "ui_paste is testing-only and may show iRacing chat/window on the stream. "
                "If the broadcast PC is also the streaming PC, any mode that opens chat can interrupt what viewers see. "
                "For the cleanest production, have a trusted race-control admin open Producer Assist from another PC through Tailscale."
            )

        if key == "OVERLAY_HOST":
            label(
                settings_frame,
                text="Streamlabs / OBS Link",
                anchor="w",
                width=24,
                bg=PANEL_BG,
                fg=MUTED_FG,
            ).grid(row=settings_grid_row, column=0, sticky="w", pady=3)
            overlay_url_var = tk.StringVar(value=DEFAULT_OVERLAY_URL)
            overlay_url_entry = entry(
                settings_frame,
                textvariable=overlay_url_var,
                width=72,
                state="readonly",
                readonlybackground=FIELD_BG,
            )
            overlay_url_entry.grid(row=settings_grid_row, column=1, sticky="ew", pady=3)
            button(
                settings_frame,
                text="Copy Overlay Link",
                command=lambda: (
                    copy_to_clipboard(root, DEFAULT_OVERLAY_URL),
                    status.set("Copied overlay browser-source link for Streamlabs / OBS."),
                ),
                color="#334b64",
            ).grid(row=settings_grid_row, column=2, padx=(8, 0), sticky="w")
            settings_grid_row += 1

            label(
                settings_frame,
                text="Producer Assist / Remote Admin Link",
                anchor="w",
                width=24,
                bg=PANEL_BG,
                fg=MUTED_FG,
            ).grid(row=settings_grid_row, column=0, sticky="w", pady=3)
            producer_url_var = tk.StringVar(value=DEFAULT_PRODUCER_URL)
            producer_url_entry = entry(
                settings_frame,
                textvariable=producer_url_var,
                width=72,
                state="readonly",
                readonlybackground=FIELD_BG,
            )
            producer_url_entry.grid(row=settings_grid_row, column=1, sticky="ew", pady=3)

            def refresh_producer_link(*_):
                host_widget = entries.get("OVERLAY_HOST")
                host_value = host_widget.get() if host_widget else "127.0.0.1"
                producer_url_var.set(producer_link_for_host(host_value))

            if "OVERLAY_HOST" in entries:
                entries["OVERLAY_HOST"].bind("<<ComboboxSelected>>", refresh_producer_link)
                entries["OVERLAY_HOST"].bind("<KeyRelease>", refresh_producer_link)
                refresh_producer_link()

            button(
                settings_frame,
                text="Copy Admin Link",
                command=lambda: (
                    copy_to_clipboard(root, producer_url_var.get()),
                    status.set("Copied Producer Assist / remote admin link. Send this to trusted admins on Tailscale."),
                ),
                color="#334b64",
            ).grid(row=settings_grid_row, column=2, padx=(8, 0), sticky="w")
            settings_grid_row += 1
            add_settings_hint(
                "This is the same Producer Assist control-room page. With access set to 0.0.0.0, this link uses the broadcast PC's Tailscale address so trusted admins on your Tailscale network can help. "
                "Keep the Streamlabs / OBS Link local on the broadcast PC."
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
        career_mode = sim_racer_hub_state.get("career_mode")
        if career_mode is not None:
            values["SIMRACERHUB_CAREER_MODE"] = "true" if career_mode.get() else "false"
        return values

    def apply_values_to_form(values):
        values = launcher_defaults(values)
        for key, widget in entries.items():
            if hasattr(widget, "set"):
                widget.set(values.get(key, ""))
            else:
                widget.delete(0, "end")
                widget.insert(0, values.get(key, ""))
        for key, widget in sim_racer_hub_state["entries"].items():
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
        path = save_profile(name, collect_values())
        profile_var.set(sanitize_profile_name(name))
        profile_name_var.set("")
        refresh_profile_list()
        status.set(f"Created profile: {path.name}")

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
        apply_values_to_form(values)
        save_env_file(collect_values())
        status.set(f"Loaded profile '{name}' and saved it as the active broadcast settings.")

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
        copied = ensure_league_files()
        if copied:
            messagebox.showinfo("League files created", "\n".join(copied))
        else:
            messagebox.showinfo(
                "League files ready",
                "league/drivers.csv, league/season.csv, and league/career.csv already exist.",
            )

    def start_broadcast():
        save_settings()
        current_values = collect_values()
        if setting_enabled(current_values, "USE_SIM_RACING_APPS", "true") and not sim_racing_apps_is_running():
            messagebox.showwarning(
                "SIMRacingApps is not running",
                "Use SIMRacingApps Car Graphics is set to true, but SIMRacingAppsServer is not running.\n\n"
                "Start SIMRacingAppsServer before starting the broadcast, or change Use SIMRacingApps Car Graphics to false and save settings.",
            )
            status.set(
                "SIMRacingApps is enabled but not running. Start SIMRacingAppsServer or set it to false."
            )
            refresh_health()
            return
        process = launch_broadcast()
        if process:
            status.set(
                "Started broadcast with overlay, Producer Assist, cameras, and incident replay. "
                "Use Producer Assist to toggle OpenAI, ElevenLabs, and auto cameras."
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
    refresh_health()
    root.protocol("WM_DELETE_WINDOW", on_close)

    root.mainloop()


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
    from tkinter import filedialog
    from tkinter import simpledialog

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
    tk.Checkbutton(
        form,
        text="Career Mode: import all seasons in this series instead of one season",
        variable=career_mode,
        bg=PANEL_BG,
        fg=TEXT_FG,
        activebackground=PANEL_BG,
        activeforeground=TEXT_FG,
        selectcolor=FIELD_BG,
    ).grid(row=len(rows), column=1, sticky="w", pady=(4, 8))

    buttons = frame(parent, bg=PANEL_BG)
    buttons.pack(fill="x", padx=14, pady=(8, 4))

    def values():
        return {key: entry.get().strip() for key, entry in entries.items()}

    output_box = tk.Text(
        parent,
        height=18,
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

    def run_import(dry_run, drivers_only=False, schedule_only=False):
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

        stats_output = (
            data["SIMRACERHUB_CAREER_STATS_OUTPUT"]
            if career_mode.get()
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
            career_mode=False if schedule_only else career_mode.get(),
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
            mode = "career" if career_mode.get() else "season"
            if schedule_only:
                target = data["SIMRACERHUB_RACE_SCHEDULE_CSV"] or "league/race_schedule.csv"
            elif drivers_only:
                target = data["SIMRACERHUB_DRIVERS_OUTPUT"] or driver_roster_import_target()
                if not dry_run:
                    load_driver_profiles()
            else:
                target = stats_output or (
                    "league/career.csv" if career_mode.get() else "league/season.csv"
                )
            data_type = "race schedule" if schedule_only else ("driver roster" if drivers_only else "stats")
            suffix = "" if dry_run else f" to {target}"
            status.set(f"{action} Sim Racer Hub {mode} {data_type}{suffix}.")
        else:
            status.set("Sim Racer Hub import failed. Check the output panel.")

    button(buttons, text="Preview Stats", command=lambda: run_import(True), color="#334b64").pack(
        side="left",
        padx=4,
    )
    button(buttons, text="Import Stats", command=lambda: run_import(False), color=GREEN).pack(
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
        text="Tip: import the schedule once per season; use Career Mode for all-season driver stats.",
        anchor="w",
        bg=PANEL_BG,
        fg=MUTED_FG,
    ).pack(side="left", padx=12)
    output_box.pack(fill="both", expand=True, padx=14, pady=(8, 0))

    editor_panel = frame(parent, bg="#0b1520")
    editor_panel.pack(fill="both", expand=True, padx=14, pady=(4, 14))
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
    editor_body.pack(fill="both", expand=True, padx=12, pady=(0, 12))

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
        height=14,
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
        if season_stats_csv:
            if "LEAGUE_SEASON_STATS_CSV" in settings_entries:
                set_entry_value(settings_entries["LEAGUE_SEASON_STATS_CSV"], season_stats_csv)
            if "SIMRACERHUB_SEASON_STATS_OUTPUT" in entries:
                set_entry_value(entries["SIMRACERHUB_SEASON_STATS_OUTPUT"], season_stats_csv)
        if career_stats_csv:
            if "LEAGUE_CAREER_STATS_CSV" in settings_entries:
                set_entry_value(settings_entries["LEAGUE_CAREER_STATS_CSV"], career_stats_csv)
            if "SIMRACERHUB_CAREER_STATS_OUTPUT" in entries:
                set_entry_value(entries["SIMRACERHUB_CAREER_STATS_OUTPUT"], career_stats_csv)
        if race_schedule_csv and "SIMRACERHUB_RACE_SCHEDULE_CSV" in entries:
            set_entry_value(entries["SIMRACERHUB_RACE_SCHEDULE_CSV"], race_schedule_csv)

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

    load_driver_profiles()


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
        text="Open Tailscale Download",
        command=lambda: open_external_link(TAILSCALE_WINDOWS_DOWNLOAD_URL),
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
        Start Broadcast runs the broadcast engine, overlay, Producer Assist control room, cameras, caution replay controls, and race control.
        Producer Assist opens automatically after Start Broadcast. If you close it, use the Producer Assist link to open it again.
        Use Producer Assist to turn OpenAI, ElevenLabs, and auto cameras on or off during the same running broadcast.
        Stop Broadcast stops a broadcast launched by the studio.

        Important: RGC AI Broadcast Studio is currently for live iRacing sessions only. Start it while the session is live
        during practice, qualifying, grid, or race. Saved iRacing replays are not officially supported for normal broadcasts yet.
        Replay SDK data can behave differently from live telemetry, so cameras, timing, cautions, scoring, and broadcast calls may not line up correctly.

        Race Admin Send Mode controls how admin commands are handled. clipboard is broadcast-safe and copies the command for manual send.
        open_chat copies the command and opens iRacing text chat for quick Ctrl+V/Enter. ui_paste is testing-only and may show iRacing chat/window on the broadcast.
        If the broadcast PC is also the streaming PC, sending commands through iRacing chat can interrupt the viewer-facing broadcast capture.
        For clean league race control, use a trusted admin on another PC through Producer Assist/Tailscale so any iRacing chat/admin workflow happens away from the broadcast screen.
        """,
    )
    section(
        "10. Remote helper setup with Tailscale",
        f"""
        Recommended for trusted league admins in different locations: use Tailscale.
        Download Tailscale for Windows here: {TAILSCALE_WINDOWS_DOWNLOAD_URL}

        1. Install Tailscale on the broadcast PC.
        2. Install Tailscale on the helper admin's PC.
        3. Sign both PCs into the same Tailscale network.
        4. In Broadcast Settings, set Remote Producer Assist Access to 0.0.0.0 and save settings.
        5. Start Broadcast.
        6. Copy the Producer Assist / Remote Admin Link and send it only to trusted helpers on your Tailscale network.

        The stream overlay link should still use http://127.0.0.1:8765/overlay inside OBS/Streamlabs on the broadcast PC.
        Tailscale is only for the private Producer Assist control-room page.
        """,
    )
    section(
        "11. Updates",
        """
        Use Check for Updates to compare this installed version against the latest GitHub Release.
        Early versions open the release/download page instead of auto-installing. This is safer while the app is still moving quickly.
        """,
    )
    section(
        "12. Race-night checklist",
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
