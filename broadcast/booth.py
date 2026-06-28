import time

from config import (
    USE_ELEVENLABS,
    ELEVENLABS_API_KEY,
    LEAD_VOICE_ID,
    COLOR_VOICE_ID,
    PIT_VOICE_ID,
)

from voice.elevenlabs_client import ElevenLabsClient


class BroadcastBooth:
    def __init__(self):
        self.last_comment = ""

        if USE_ELEVENLABS and ELEVENLABS_API_KEY:
            self.voice_client = ElevenLabsClient(ELEVENLABS_API_KEY)
        else:
            self.voice_client = None

    def broadcast(self, commentary, speaker="lead"):
        if commentary == self.last_comment:
            return

        self.last_comment = commentary
        speaker_label = self.get_speaker_label(speaker)

        print()
        print(f"RGC BROADCAST - {speaker_label}")
        print("=" * 60)
        print(commentary)
        print("=" * 60)

        voice_id = self.get_voice_id(speaker)

        if self.voice_client and voice_id:
            self.voice_client.speak(commentary, voice_id)

        time.sleep(6)

    def get_speaker_label(self, speaker):
        if speaker == "jeff":
            return "JEFF"

        if speaker == "sarah":
            return "SARAH"

        return "LEAD"

    def get_voice_id(self, speaker):
        if speaker == "jeff":
            return COLOR_VOICE_ID or LEAD_VOICE_ID

        if speaker == "sarah":
            return PIT_VOICE_ID or LEAD_VOICE_ID

        return LEAD_VOICE_ID