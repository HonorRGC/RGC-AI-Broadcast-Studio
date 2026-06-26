from pathlib import Path
import os

from elevenlabs.client import ElevenLabs


class ElevenLabsClient:
    def __init__(self, api_key):
        self.client = ElevenLabs(api_key=api_key)

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

            output_path = Path("temp_voice.mp3")

            with open(output_path, "wb") as file:
                for chunk in audio:
                    file.write(chunk)

            os.startfile(output_path)

        except Exception as error:
            print("ElevenLabs voice error:")
            print(error)