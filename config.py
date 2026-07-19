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


# Overlay graphics
OVERLAY_EVENT_TITLE = os.getenv("OVERLAY_EVENT_TITLE", "RGC AI Broadcast")
OVERLAY_RACE_SPONSOR = os.getenv("OVERLAY_RACE_SPONSOR", "")
OVERLAY_SERIES_NAME = os.getenv("OVERLAY_SERIES_NAME", "")
OVERLAY_HOST = os.getenv("OVERLAY_HOST", "127.0.0.1").strip() or "127.0.0.1"
REMOTE_PRODUCER_ENABLED = os.getenv("REMOTE_PRODUCER_ENABLED", "false").lower() == "true"
REMOTE_PRODUCER_RELAY_URL = os.getenv("REMOTE_PRODUCER_RELAY_URL", "").strip()
REMOTE_PRODUCER_SESSION_CODE = os.getenv("REMOTE_PRODUCER_SESSION_CODE", "").strip()
REMOTE_PRODUCER_PIN = os.getenv("REMOTE_PRODUCER_PIN", "").strip()
OVERLAY_LEADERBOARD_STYLE = os.getenv("OVERLAY_LEADERBOARD_STYLE", "side").strip().lower()
OVERLAY_BRAND_GRAPHICS = [
    item.strip()
    for item in os.getenv(
        "OVERLAY_BRAND_GRAPHICS",
        "/assets/rgc_motorsports.png,/assets/autism_awareness.png,/assets/keep_it_real.webp",
    ).split(",")
    if item.strip()
]
NATIONAL_ANTHEM_GRAPHICS = [
    item.strip()
    for item in os.getenv("NATIONAL_ANTHEM_GRAPHICS", ",".join(OVERLAY_BRAND_GRAPHICS)).split(",")
    if item.strip()
]
CAUTION_PRESENTATION_GRAPHICS = [
    item.strip()
    for item in os.getenv("CAUTION_PRESENTATION_GRAPHICS", ",".join(OVERLAY_BRAND_GRAPHICS)).split(",")
    if item.strip()
]
CRANK_IT_UP_SPONSOR_GRAPHIC = os.getenv(
    "CRANK_IT_UP_SPONSOR_GRAPHIC",
    "/assets/rgc_motorsports.png",
)
CRANK_IT_UP_ICON_GRAPHIC = os.getenv(
    "CRANK_IT_UP_ICON_GRAPHIC",
    "/assets/crank_it_up.png",
)


# Sponsor reads
USE_SPONSOR_READS = os.getenv("USE_SPONSOR_READS", "true").lower() == "true"
SPONSOR_READ_NAME = os.getenv("SPONSOR_READ_NAME", OVERLAY_RACE_SPONSOR)
SPONSOR_READ_NAME_2 = os.getenv("SPONSOR_READ_NAME_2", "")
SPONSOR_READ_NAME_3 = os.getenv("SPONSOR_READ_NAME_3", "")
SPONSOR_READ_CAUSE = os.getenv("SPONSOR_READ_CAUSE", "")
SPONSOR_READ_MESSAGE = os.getenv("SPONSOR_READ_MESSAGE", "")


# Optional post-race interviews.
POST_RACE_INTERVIEWS_ENABLED = (
    os.getenv("POST_RACE_INTERVIEWS_ENABLED", "false").lower() == "true"
)


# Optional pre-race ceremony
USE_NATIONAL_ANTHEM = os.getenv("USE_NATIONAL_ANTHEM", "false").lower() == "true"
NATIONAL_ANTHEM_AUDIO = os.getenv("NATIONAL_ANTHEM_AUDIO", "")


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
