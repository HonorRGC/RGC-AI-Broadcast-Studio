from broadcaster.race_director import RacePhase
from production.caution_presentation import CautionPresentationDirector


class OverlaySpy:
    def __init__(self):
        self.presentations = []
        self.cleared = 0

    def show_special_presentation(self, **kwargs):
        self.presentations.append(kwargs)

    def clear_special_presentation(self):
        self.cleared += 1


class AudioBedSpy:
    def __init__(self):
        self.stops = 0

    def stop(self):
        self.stops += 1


def test_caution_presentation_shows_sponsors_until_green():
    overlay = OverlaySpy()
    director = CautionPresentationDirector(
        sponsor_name="RGC Motorsports",
        sponsor_cause="Autism Awareness",
    )

    message = director.update(RacePhase.CAUTION, overlay)
    director.update(RacePhase.ONE_TO_GREEN, overlay)
    director.update(RacePhase.GREEN, overlay)

    assert message == "Caution sponsor overlay shown."
    assert overlay.presentations[0]["kind"] == "race_sponsors"
    assert overlay.presentations[0]["title"] == "Today's Race Sponsors"
    assert "RGC Motorsports" in overlay.presentations[0]["subtitle"]
    assert overlay.cleared == 1


def test_caution_presentation_stops_music_once_at_one_to_green():
    audio = AudioBedSpy()
    director = CautionPresentationDirector()

    director.update(RacePhase.CAUTION, audio_bed=audio)
    director.update(RacePhase.ONE_TO_GREEN, audio_bed=audio)
    director.update(RacePhase.ONE_TO_GREEN, audio_bed=audio)

    assert audio.stops == 1
