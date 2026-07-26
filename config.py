import os
from dotenv import load_dotenv


load_dotenv()


def env_int(name, default):
    try:
        return int(os.getenv(name, str(default)) or default)
    except (TypeError, ValueError):
        return int(default)


def env_int_list(name, default=""):
    values = []
    for raw_value in os.getenv(name, default).replace(";", ",").split(","):
        try:
            value = int(str(raw_value).strip())
        except (TypeError, ValueError):
            continue
        if value > 0 and value not in values:
            values.append(value)
    return values


def env_list(name, default="", separators=(";", "|", ",")):
    text = os.getenv(name, default)
    for separator in separators:
        text = text.replace(separator, "||")
    return [item.strip() for item in text.split("||") if item.strip()]


def env_list_or_default(name, default_items, separators=(";", "|", ",")):
    values = env_list(name, "", separators=separators)
    if values:
        return values
    return list(default_items or [])


def unique_list(values):
    seen = set()
    cleaned = []
    for value in values or []:
        text = str(value or "").strip()
        if not text:
            continue
        key = text.lower()
        if key in seen:
            continue
        cleaned.append(text)
        seen.add(key)
    return cleaned


# OpenAI
OPENAI_API_KEY = os.getenv("OPENAI_API_KEY")
USE_OPENAI = os.getenv("USE_OPENAI", "true").lower() == "true"
OPENAI_MODEL = os.getenv("OPENAI_MODEL", "gpt-5.5")


# ElevenLabs
ELEVENLABS_API_KEY = os.getenv("ELEVENLABS_API_KEY")
USE_ELEVENLABS = os.getenv("USE_ELEVENLABS", "true").lower() == "true"


# Voice IDs
LEAD_VOICE_ID = os.getenv("LEAD_VOICE_ID")
COLOR_VOICE_ID = os.getenv("COLOR_VOICE_ID")
PIT_VOICE_ID = os.getenv("PIT_VOICE_ID")


# League context
USE_LEAGUE_DRIVER_NOTES = os.getenv("USE_LEAGUE_DRIVER_NOTES", "false").lower() == "true"
LEAGUE_DRIVERS_CSV = os.getenv("LEAGUE_DRIVERS_CSV", "league/drivers.csv")
LEAGUE_SEASON_STATS_CSV = os.getenv("LEAGUE_SEASON_STATS_CSV", "league/season.csv")
LEAGUE_CAREER_STATS_CSV = os.getenv("LEAGUE_CAREER_STATS_CSV", "league/career.csv")
STAGE_END_LAPS = env_int_list("STAGE_END_LAPS", "")
RACE_ADMIN_MODE = os.getenv("RACE_ADMIN_MODE", "false").lower() == "true"
RACE_ADMIN_SEND_MODE = os.getenv("RACE_ADMIN_SEND_MODE", "clipboard").strip().lower()


# Future Discord interview/control-room integration.
DISCORD_BOT_ENABLED = os.getenv("DISCORD_BOT_ENABLED", "false").lower() == "true"
DISCORD_BOT_TOKEN = os.getenv("DISCORD_BOT_TOKEN", "").strip()
DISCORD_GUILD_ID = os.getenv("DISCORD_GUILD_ID", "").strip()
DISCORD_BOOTH_CHANNEL_ID = os.getenv("DISCORD_BOOTH_CHANNEL_ID", "").strip()
DISCORD_WAITING_CHANNEL_ID = os.getenv("DISCORD_WAITING_CHANNEL_ID", "").strip()
DISCORD_INTERVIEW_CHANNEL_ID = os.getenv("DISCORD_INTERVIEW_CHANNEL_ID", "").strip()
DISCORD_RACE_REPORT_ENABLED = os.getenv("DISCORD_RACE_REPORT_ENABLED", "false").lower() == "true"
DISCORD_RACE_REPORT_WEBHOOK_URL = os.getenv("DISCORD_RACE_REPORT_WEBHOOK_URL", "").strip()
DISCORD_RACE_REPORT_USE_OPENAI = os.getenv("DISCORD_RACE_REPORT_USE_OPENAI", "true").lower() == "true"
DISCORD_RACE_REPORT_RESULTS_URL = os.getenv("DISCORD_RACE_REPORT_RESULTS_URL", "").strip()
DISCORD_RACE_REPORT_CHAMPIONSHIP_URL = os.getenv("DISCORD_RACE_REPORT_CHAMPIONSHIP_URL", "").strip()
SIMRACERHUB_SOURCE = os.getenv("SIMRACERHUB_SOURCE", "https://simracerhub.com").strip()
SIMRACERHUB_RACE_SCHEDULE_CSV = os.getenv(
    "SIMRACERHUB_RACE_SCHEDULE_CSV",
    "league/race_schedule.csv",
).strip()


# Overlay graphics
USE_IRACING_RENDERED_CAR_IMAGES = (
    os.getenv("USE_IRACING_RENDERED_CAR_IMAGES", "true").lower() == "true"
)
OVERLAY_EVENT_TITLE = os.getenv("OVERLAY_EVENT_TITLE", "RGC AI Broadcast")
OVERLAY_RACE_SPONSOR = os.getenv("OVERLAY_RACE_SPONSOR", os.getenv("RACE_SPONSOR_1_NAME", ""))
OVERLAY_SERIES_NAME = os.getenv("OVERLAY_SERIES_NAME", "")
OVERLAY_SERIES_LOGO = os.getenv("OVERLAY_SERIES_LOGO", "").strip()
OVERLAY_HOST = os.getenv("OVERLAY_HOST", "127.0.0.1").strip() or "127.0.0.1"
REMOTE_PRODUCER_ENABLED = os.getenv("REMOTE_PRODUCER_ENABLED", "false").lower() == "true"
REMOTE_PRODUCER_RELAY_URL = os.getenv("REMOTE_PRODUCER_RELAY_URL", "").strip()
REMOTE_PRODUCER_SESSION_CODE = os.getenv("REMOTE_PRODUCER_SESSION_CODE", "").strip()
REMOTE_PRODUCER_PIN = os.getenv("REMOTE_PRODUCER_PIN", "").strip()
OVERLAY_LEADERBOARD_STYLE = os.getenv("OVERLAY_LEADERBOARD_STYLE", "side").strip().lower()
CRANK_IT_UP_SPONSOR_GRAPHIC = os.getenv(
    "CRANK_IT_UP_SPONSOR_GRAPHIC",
    "",
)
CRANK_IT_UP_ICON_GRAPHIC = os.getenv(
    "CRANK_IT_UP_ICON_GRAPHIC",
    "/assets/crank_it_up.png",
)


# Sponsor reads
USE_SPONSOR_READS = os.getenv("USE_SPONSOR_READS", "true").lower() == "true"
SPONSOR_READ_CAUSE = os.getenv("SPONSOR_READ_CAUSE", "")
SPONSOR_READ_CAUSE_LOGO = os.getenv("SPONSOR_READ_CAUSE_LOGO", "").strip()
SPONSOR_READ_MESSAGE = os.getenv("SPONSOR_READ_MESSAGE", "")
RACE_SPONSOR_1_NAME = os.getenv(
    "RACE_SPONSOR_1_NAME",
    os.getenv("SPONSOR_READ_NAME", OVERLAY_RACE_SPONSOR),
).strip()
RACE_SPONSOR_2_NAME = os.getenv("RACE_SPONSOR_2_NAME", os.getenv("SPONSOR_READ_NAME_2", "")).strip()
RACE_SPONSOR_3_NAME = os.getenv("RACE_SPONSOR_3_NAME", os.getenv("SPONSOR_READ_NAME_3", "")).strip()
RACE_SPONSOR_4_NAME = os.getenv("RACE_SPONSOR_4_NAME", "").strip()
RACE_SPONSOR_5_NAME = os.getenv("RACE_SPONSOR_5_NAME", "").strip()
RACE_SPONSOR_1_LOGO = os.getenv("RACE_SPONSOR_1_LOGO", "").strip()
RACE_SPONSOR_2_LOGO = os.getenv("RACE_SPONSOR_2_LOGO", "").strip()
RACE_SPONSOR_3_LOGO = os.getenv("RACE_SPONSOR_3_LOGO", "").strip()
RACE_SPONSOR_4_LOGO = os.getenv("RACE_SPONSOR_4_LOGO", "").strip()
RACE_SPONSOR_5_LOGO = os.getenv("RACE_SPONSOR_5_LOGO", "").strip()
RACE_SPONSOR_1_READ = os.getenv("RACE_SPONSOR_1_READ", SPONSOR_READ_MESSAGE).strip()
RACE_SPONSOR_2_READ = os.getenv("RACE_SPONSOR_2_READ", "").strip()
RACE_SPONSOR_3_READ = os.getenv("RACE_SPONSOR_3_READ", "").strip()
RACE_SPONSOR_4_READ = os.getenv("RACE_SPONSOR_4_READ", "").strip()
RACE_SPONSOR_5_READ = os.getenv("RACE_SPONSOR_5_READ", "").strip()
RACE_SPONSOR_1_VIDEO = os.getenv("RACE_SPONSOR_1_VIDEO", "").strip()
RACE_SPONSOR_2_VIDEO = os.getenv("RACE_SPONSOR_2_VIDEO", "").strip()
RACE_SPONSOR_3_VIDEO = os.getenv("RACE_SPONSOR_3_VIDEO", "").strip()
RACE_SPONSOR_4_VIDEO = os.getenv("RACE_SPONSOR_4_VIDEO", "").strip()
RACE_SPONSOR_5_VIDEO = os.getenv("RACE_SPONSOR_5_VIDEO", "").strip()
SPONSOR_READ_NAME = os.getenv("SPONSOR_READ_NAME", RACE_SPONSOR_1_NAME or OVERLAY_RACE_SPONSOR)
SPONSOR_READ_NAME_2 = os.getenv("SPONSOR_READ_NAME_2", RACE_SPONSOR_2_NAME)
SPONSOR_READ_NAME_3 = os.getenv("SPONSOR_READ_NAME_3", RACE_SPONSOR_3_NAME)
RACE_SPONSOR_NAMES = unique_list(
    [
        RACE_SPONSOR_1_NAME,
        RACE_SPONSOR_2_NAME,
        RACE_SPONSOR_3_NAME,
        RACE_SPONSOR_4_NAME,
        RACE_SPONSOR_5_NAME,
    ]
)
CRANK_IT_UP_SPONSOR_NAME = os.getenv(
    "CRANK_IT_UP_SPONSOR_NAME",
    RACE_SPONSOR_1_NAME or SPONSOR_READ_NAME or OVERLAY_RACE_SPONSOR or "RGC Motorsports",
).strip()
RACE_SPONSOR_LOGOS = unique_list(
    [
        RACE_SPONSOR_1_LOGO,
        RACE_SPONSOR_2_LOGO,
        RACE_SPONSOR_3_LOGO,
        RACE_SPONSOR_4_LOGO,
        RACE_SPONSOR_5_LOGO,
    ]
)
RACE_SPONSOR_READS = {
    name: read
    for name, read in zip(
        [
            RACE_SPONSOR_1_NAME,
            RACE_SPONSOR_2_NAME,
            RACE_SPONSOR_3_NAME,
            RACE_SPONSOR_4_NAME,
            RACE_SPONSOR_5_NAME,
        ],
        [
            RACE_SPONSOR_1_READ,
            RACE_SPONSOR_2_READ,
            RACE_SPONSOR_3_READ,
            RACE_SPONSOR_4_READ,
            RACE_SPONSOR_5_READ,
        ],
    )
    if name and read
}
RACE_SPONSOR_GRAPHICS = {
    name: logo
    for name, logo in zip(
        [
            RACE_SPONSOR_1_NAME,
            RACE_SPONSOR_2_NAME,
            RACE_SPONSOR_3_NAME,
            RACE_SPONSOR_4_NAME,
            RACE_SPONSOR_5_NAME,
        ],
        [
            RACE_SPONSOR_1_LOGO,
            RACE_SPONSOR_2_LOGO,
            RACE_SPONSOR_3_LOGO,
            RACE_SPONSOR_4_LOGO,
            RACE_SPONSOR_5_LOGO,
        ],
    )
    if name and logo
}
RACE_SPONSOR_VIDEOS = {
    name: video
    for name, video in zip(
        [
            RACE_SPONSOR_1_NAME,
            RACE_SPONSOR_2_NAME,
            RACE_SPONSOR_3_NAME,
            RACE_SPONSOR_4_NAME,
            RACE_SPONSOR_5_NAME,
        ],
        [
            RACE_SPONSOR_1_VIDEO,
            RACE_SPONSOR_2_VIDEO,
            RACE_SPONSOR_3_VIDEO,
            RACE_SPONSOR_4_VIDEO,
            RACE_SPONSOR_5_VIDEO,
        ],
    )
    if name and video
}
_DEFAULT_BRAND_GRAPHICS = env_list(
    "OVERLAY_BRAND_GRAPHICS",
    "/assets/rgc_motorsports.png,/assets/autism_awareness.png,/assets/keep_it_real.webp",
)
_SPONSOR_BRAND_GRAPHICS = unique_list(
    RACE_SPONSOR_LOGOS
    + [OVERLAY_SERIES_LOGO]
    + [SPONSOR_READ_CAUSE_LOGO]
)
OVERLAY_BRAND_GRAPHICS = _SPONSOR_BRAND_GRAPHICS or _DEFAULT_BRAND_GRAPHICS
NATIONAL_ANTHEM_GRAPHICS = env_list_or_default(
    "NATIONAL_ANTHEM_GRAPHICS",
    OVERLAY_BRAND_GRAPHICS,
)
CAUTION_PRESENTATION_GRAPHICS = env_list_or_default(
    "CAUTION_PRESENTATION_GRAPHICS",
    OVERLAY_BRAND_GRAPHICS,
)
PRACTICE_PRESENTATION_GRAPHICS = env_list_or_default(
    "PRACTICE_PRESENTATION_GRAPHICS",
    OVERLAY_BRAND_GRAPHICS,
)


# Optional post-race interviews.
POST_RACE_INTERVIEWS_ENABLED = (
    os.getenv("POST_RACE_INTERVIEWS_ENABLED", "false").lower() == "true"
)


# Optional qualifying music. NATIONAL_ANTHEM_AUDIO is kept as a legacy alias for older profiles.
QUALIFYING_MUSIC_PLAYLIST = os.getenv(
    "QUALIFYING_MUSIC_PLAYLIST",
    os.getenv("NATIONAL_ANTHEM_AUDIO", ""),
)
USE_QUALIFYING_MUSIC = (
    os.getenv("USE_QUALIFYING_MUSIC", "true").lower() == "true"
)
USE_NATIONAL_ANTHEM = USE_QUALIFYING_MUSIC
NATIONAL_ANTHEM_AUDIO = QUALIFYING_MUSIC_PLAYLIST


# Optional practice/replay music beds.
STUDIO_VOLUME = max(
    0,
    min(
        100,
        env_int(
            "STUDIO_VOLUME",
            env_int("PRACTICE_MUSIC_VOLUME", 65),
        ),
    ),
)
PRACTICE_MUSIC_PLAYLIST = [
    item.strip()
    for item in os.getenv("PRACTICE_MUSIC_PLAYLIST", "").split(";")
    if item.strip()
]
CAUTION_REPLAY_AUDIO = os.getenv("CAUTION_REPLAY_AUDIO", NATIONAL_ANTHEM_AUDIO)
