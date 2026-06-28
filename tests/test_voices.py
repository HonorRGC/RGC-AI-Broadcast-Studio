from config import ELEVENLABS_API_KEY, LEAD_VOICE_ID
from voice.elevenlabs_client import ElevenLabsClient

print(f"Lead Voice ID loaded: {LEAD_VOICE_ID}")

client = ElevenLabsClient(ELEVENLABS_API_KEY)

client.speak(
    "Welcome to R G C A I Broadcast Studio. Systems online and ready for today's race.",
    LEAD_VOICE_ID,
)

print("Voice test complete!")