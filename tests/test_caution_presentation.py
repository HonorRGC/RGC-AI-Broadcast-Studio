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
        self.fades = 0
        self.fade_kwargs = None

    def stop(self):
        self.stops += 1

    def fade_out(self, **kwargs):
        self.fades += 1
        self.fade_kwargs = kwargs


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


def test_caution_presentation_uses_configured_graphics():
    overlay = OverlaySpy()
    director = CautionPresentationDirector(
        graphics=["/assets/caution_sponsor.png", "/assets/autism.png"],
    )

    director.update(RacePhase.CAUTION, overlay)

    assert overlay.presentations[0]["graphics"] == [
        "/assets/caution_sponsor.png",
        "/assets/autism.png",
    ]


def test_caution_presentation_fades_music_once_at_one_to_green():
    audio = AudioBedSpy()
    director = CautionPresentationDirector()

    director.update(RacePhase.CAUTION, audio_bed=audio)
    director.update(RacePhase.ONE_TO_GREEN, audio_bed=audio)
    director.update(RacePhase.ONE_TO_GREEN, audio_bed=audio)

    assert audio.fades == 1
    assert audio.stops == 0
    assert audio.fade_kwargs == {"duration_seconds": 1.0, "steps": 8}


def test_caution_presentation_can_fall_back_to_stop_at_one_to_green():
    class StopOnlyAudioBed:
        def __init__(self):
            self.stops = 0

        def stop(self):
            self.stops += 1

    audio = StopOnlyAudioBed()
    director = CautionPresentationDirector()

    director.update(RacePhase.CAUTION, audio_bed=audio)
    director.update(RacePhase.ONE_TO_GREEN, audio_bed=audio)

    assert audio.stops == 1
