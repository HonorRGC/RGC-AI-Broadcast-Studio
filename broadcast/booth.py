from config import USE_ELEVENLABS, ELEVENLABS_API_KEY, LEAD_VOICE_ID
from voice.elevenlabs_client import ElevenLabsClient


class BroadcastBooth:
    def __init__(self):
        self.last_comment = ""

        if USE_ELEVENLABS and ELEVENLABS_API_KEY and LEAD_VOICE_ID:
            self.voice_client = ElevenLabsClient(ELEVENLABS_API_KEY)
        else:
            self.voice_client = None

    def broadcast(self, commentary):
        if commentary == self.last_comment:
            return

        self.last_comment = commentary

        print()
        print("🎙 RGC BROADCAST")
        print("=" * 60)
        print(commentary)
        print("=" * 60)

        if self.voice_client:
            self.voice_client.speak(commentary, LEAD_VOICE_ID)
            import time
            time.sleep(8)