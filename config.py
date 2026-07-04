import os
from dotenv import load_dotenv


load_dotenv()


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
