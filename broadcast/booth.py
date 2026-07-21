from config import (
    USE_ELEVENLABS,
    ELEVENLABS_API_KEY,
    LEAD_VOICE_ID,
    COLOR_VOICE_ID,
    PIT_VOICE_ID,
    STUDIO_VOLUME,
)

from voice.elevenlabs_client import ElevenLabsClient


class BroadcastBooth:
    def __init__(
        self,
        enable_voice=True,
        audio_bed=None,
        studio_volume=STUDIO_VOLUME,
        producer_sink=None,
    ):
        self.last_comment = ""
        self.enable_voice = enable_voice
        self.audio_bed = audio_bed
        self.studio_volume = int(studio_volume)
        self.producer_sink = producer_sink
        self.voice_runtime_enabled = True

        if enable_voice and USE_ELEVENLABS and ELEVENLABS_API_KEY:
            self.voice_client = ElevenLabsClient(
                ELEVENLABS_API_KEY,
                studio_volume=self.studio_volume,
            )
        else:
            self.voice_client = None

    def voice_status(self):
        if not self.voice_runtime_enabled:
            return False, "disabled from Producer Assist"
        if not self.enable_voice:
            return False, "disabled by --no-voice"
        if not USE_ELEVENLABS:
            return False, "USE_ELEVENLABS is false"
        if not ELEVENLABS_API_KEY:
            return False, "ELEVENLABS_API_KEY is missing"
        if not LEAD_VOICE_ID:
            return False, "LEAD_VOICE_ID is missing"
        if not self.voice_client:
            return False, "voice client did not initialize"
        return True, "ready"

    def set_voice_enabled(self, enabled):
        self.voice_runtime_enabled = bool(enabled)

    def set_studio_volume(self, volume_percent):
        try:
            self.studio_volume = max(0, min(100, int(volume_percent)))
        except (TypeError, ValueError):
            return
        if self.voice_client and hasattr(self.voice_client, "set_volume_percent"):
            self.voice_client.set_volume_percent(self.studio_volume)

    def voice_id_status(self):
        return {
            "lead": bool(LEAD_VOICE_ID),
            "jeff": bool(COLOR_VOICE_ID or LEAD_VOICE_ID),
            "sarah": bool(PIT_VOICE_ID or LEAD_VOICE_ID),
        }

    def broadcast(self, commentary, speaker="lead"):
        if commentary == self.last_comment:
            return 0.0

        self.last_comment = commentary
        speaker_label = self.get_speaker_label(speaker)

        print()
        print(f"RGC BROADCAST - {speaker_label}")
        print("=" * 60)
        print(commentary)
        print("=" * 60)

        if self.producer_sink:
            self.producer_sink(
                kind="broadcast",
                title=f"RGC BROADCAST - {speaker_label}",
                message=commentary,
                speaker=speaker_label,
            )

        voice_id = self.get_voice_id(speaker)

        if self.voice_runtime_enabled and self.voice_client and voice_id:
            if self.audio_bed:
                self.audio_bed.duck()
            playback_seconds = 0.0
            try:
                playback_seconds = float(
                    self.voice_client.speak(commentary, voice_id) or 0.0
                )
            finally:
                if self.audio_bed:
                    self.audio_bed.restore_after(
                        playback_seconds or self.estimate_speech_seconds(commentary)
                    )
            return playback_seconds
        elif self.voice_runtime_enabled and self.voice_client and not voice_id:
            print(f"Voice output skipped: no voice ID is configured for {speaker_label}.")
        return 0.0

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

    def estimate_speech_seconds(self, commentary):
        words = len(str(commentary or "").split())
        return max(3.0, min(35.0, words / 2.65 + 1.25))
