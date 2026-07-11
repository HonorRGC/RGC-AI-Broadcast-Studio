from pathlib import Path

from production.anthem_director import NationalAnthemDirector


class OverlaySpy:
    def __init__(self):
        self.presentations = []
        self.cleared = 0

    def show_special_presentation(self, **kwargs):
        self.presentations.append(kwargs)

    def clear_special_presentation(self):
        self.cleared += 1


class HiddenPlayerSpy:
    def __init__(self):
        self.plays = []

    def play(self, path, duration_seconds=None):
        self.plays.append((path, duration_seconds))
        return True


def test_rgc_anthem_starts_once_during_qualifying(tmp_path):
    audio = tmp_path / "anthem.mp3"
    audio.write_bytes(b"audio")
    played = []
    overlay = OverlaySpy()
    director = NationalAnthemDirector(
        enabled=True,
        audio_path=str(audio),
        duration_seconds=88,
        player=played.append,
    )

    first = director.update("Lone Qualify", overlay)
    repeated = director.update("Qualifying", overlay)

    assert first.status == "played"
    assert repeated.status == "ignored"
    assert played == [str(audio.resolve())]
    assert overlay.presentations[0]["kind"] == "rgc_anthem"
    assert overlay.presentations[0]["title"] == "RGC Anthem"
    assert overlay.presentations[0]["duration"] == 88


def test_rgc_anthem_uses_hidden_player_interface_with_duration(tmp_path):
    audio = tmp_path / "anthem.mp3"
    audio.write_bytes(b"audio")
    player = HiddenPlayerSpy()
    director = NationalAnthemDirector(
        enabled=True,
        audio_path=str(audio),
        duration_seconds=75,
        player=player,
    )

    decision = director.update("Qualifying", OverlaySpy())

    assert decision.status == "played"
    assert player.plays == [(str(audio.resolve()), 75)]


def test_rgc_anthem_can_show_without_audio_file():
    overlay = OverlaySpy()
    director = NationalAnthemDirector(enabled=True, audio_path="")

    decision = director.update("Qualifying", overlay)

    assert decision.status == "shown"
    assert overlay.presentations


def test_rgc_anthem_clears_when_race_starts(tmp_path):
    audio = tmp_path / "anthem.mp3"
    audio.write_bytes(b"audio")
    overlay = OverlaySpy()
    director = NationalAnthemDirector(
        enabled=True,
        audio_path=str(audio),
        player=lambda _: None,
    )

    director.update("Qualifying", overlay)
    ended = director.update("Race", overlay)

    assert ended.status == "ended"
    assert overlay.cleared == 1


def test_rgc_anthem_reports_missing_audio(tmp_path):
    missing = Path(tmp_path) / "missing.mp3"
    director = NationalAnthemDirector(enabled=True, audio_path=str(missing))

    decision = director.update("Qualifying")

    assert decision.status == "missing_audio"
