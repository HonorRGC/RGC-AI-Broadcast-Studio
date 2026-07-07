from broadcast.booth import BroadcastBooth


class AudioBedSpy:
    def __init__(self):
        self.ducks = 0
        self.restores = []

    def duck(self):
        self.ducks += 1

    def restore_after(self, seconds):
        self.restores.append(seconds)


class VoiceSpy:
    def __init__(self):
        self.spoken = []

    def speak(self, commentary, voice_id):
        self.spoken.append((commentary, voice_id))


def test_booth_ducks_audio_bed_while_voice_line_is_playing():
    audio_bed = AudioBedSpy()
    booth = BroadcastBooth(enable_voice=False, audio_bed=audio_bed)
    booth.voice_client = VoiceSpy()
    booth.get_voice_id = lambda speaker: "voice-1"

    booth.broadcast("Trouble on the speedway, caution is out.", speaker="lead")

    assert audio_bed.ducks == 1
    assert audio_bed.restores
    assert booth.voice_client.spoken == [
        ("Trouble on the speedway, caution is out.", "voice-1")
    ]
