from pathlib import Path

from elevenlabs.client import ElevenLabs
from production.audio_bed import OneShotAudioPlayer, percent_to_mci_volume


class ElevenLabsClient:
    def __init__(self, api_key, studio_volume=65, player=None):
        self.client = ElevenLabs(api_key=api_key)
        self.player = player or OneShotAudioPlayer(
            normal_volume=percent_to_mci_volume(studio_volume),
            alias="rgc_voice_audio",
        )

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

            output_path = Path(".runtime") / "latest_voice.mp3"
            output_path.parent.mkdir(parents=True, exist_ok=True)

            with open(output_path, "wb") as file:
                for chunk in audio:
                    file.write(chunk)

            if not self.player.play(str(output_path.resolve())):
                print("ElevenLabs voice error:")
                print("Hidden voice audio player could not play the generated file.")

        except Exception as error:
            print("ElevenLabs voice error:")
            print(error)
