from pathlib import Path
import time
import uuid

from elevenlabs.client import ElevenLabs
from production.audio_bed import OneShotAudioPlayer, percent_to_mci_volume


class ElevenLabsClient:
    def __init__(self, api_key, studio_volume=65, player=None):
        self.client = ElevenLabs(api_key=api_key)
        self.player = player or OneShotAudioPlayer(
            normal_volume=percent_to_mci_volume(studio_volume),
            alias="rgc_voice_audio",
        )
        self.output_dir = Path(".runtime") / "voice"
        self.generated_files = []

    def list_voices(self):
        voices = self.client.voices.get_all()

        for voice in voices.voices:
            print(f"{voice.name} | {voice.voice_id}")

    def speak(self, text, voice_id):
        try:
            audio = self.client.text_to_speech.convert(
                voice_id=voice_id,
                model_id="eleven_multilingual_v2",
                output_format="mp3_44100_128",
                text=text,
            )

            output_path = self.next_output_path()
            output_path.parent.mkdir(parents=True, exist_ok=True)

            with open(output_path, "wb") as file:
                for chunk in audio:
                    file.write(chunk)

            self.remember_generated_file(output_path)
            if not self.player.play(str(output_path.resolve())):
                print("ElevenLabs voice error:")
                print("Hidden voice audio player could not play the generated file.")
                return 0.0
            return float(getattr(self.player, "last_duration_seconds", 0.0) or 0.0)

        except Exception as error:
            print("ElevenLabs voice error:")
            print(error)
            return 0.0

    def next_output_path(self):
        timestamp = int(time.time() * 1000)
        return self.output_dir / f"voice_{timestamp}_{uuid.uuid4().hex[:8]}.mp3"

    def remember_generated_file(self, output_path):
        self.generated_files.append(Path(output_path))
        self.cleanup_old_generated_files()

    def cleanup_old_generated_files(self, keep_last=25):
        if len(self.generated_files) <= keep_last:
            return

        stale_files = self.generated_files[:-keep_last]
        self.generated_files = self.generated_files[-keep_last:]
        for stale_file in stale_files:
            try:
                stale_file.unlink(missing_ok=True)
            except OSError:
                pass
