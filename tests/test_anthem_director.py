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
        self.playlists = []
        self.stops = 0

    def play(self, path, duration_seconds=None):
        self.plays.append((path, duration_seconds))
        return True

    def play_playlist_once(self, paths):
        self.playlists.append(paths)
        return True

    def stop(self):
        self.stops += 1


def test_rgc_anthem_starts_once_during_qualifying(tmp_path):
    audio = tmp_path / "anthem.mp3"
    audio.write_bytes(b"audio")
    played = []
    overlay = OverlaySpy()
    director = NationalAnthemDirector(
        enabled=True,
        audio_path=str(audio),
        player=played.append,
    )

    first = director.update("Lone Qualify", overlay)
    repeated = director.update("Qualifying", overlay)

    assert first.status == "played"
    assert repeated.status == "ignored"
    assert played == [str(audio.resolve())]
    assert overlay.presentations[0]["kind"] == "rgc_anthem"
    assert overlay.presentations[0]["title"] == "RGC Anthem"
    assert overlay.presentations[0]["duration"] == 24 * 60 * 60


def test_rgc_anthem_uses_configured_graphics(tmp_path):
    audio = tmp_path / "anthem.mp3"
    audio.write_bytes(b"audio")
    overlay = OverlaySpy()
    director = NationalAnthemDirector(
        enabled=True,
        audio_path=str(audio),
        player=lambda _: None,
        graphics=["/assets/anthem.png", "/assets/awareness.png"],
    )

    director.update("Qualifying", overlay)

    assert overlay.presentations[0]["graphics"] == [
        "/assets/anthem.png",
        "/assets/awareness.png",
    ]


def test_rgc_anthem_uses_hidden_player_without_overlay_duration(tmp_path):
    audio = tmp_path / "anthem.mp3"
    audio.write_bytes(b"audio")
    player = HiddenPlayerSpy()
    director = NationalAnthemDirector(
        enabled=True,
        audio_path=str(audio),
        player=player,
    )

    decision = director.update("Qualifying", OverlaySpy())

    assert decision.status == "played"
    assert player.playlists == [[str(audio.resolve())]]


def test_rgc_anthem_can_play_multiple_audio_files_once(tmp_path):
    first_audio = tmp_path / "anthem_one.mp3"
    second_audio = tmp_path / "anthem_two.mp3"
    first_audio.write_bytes(b"audio")
    second_audio.write_bytes(b"audio")
    player = HiddenPlayerSpy()
    director = NationalAnthemDirector(
        enabled=True,
        audio_path=f"{first_audio};{second_audio}",
        player=player,
    )

    decision = director.update("Qualifying", OverlaySpy())

    assert decision.status == "played"
    assert player.playlists == [
        [str(first_audio.resolve()), str(second_audio.resolve())]
    ]


def test_rgc_anthem_reports_unsupported_audio_type(tmp_path):
    unsupported = tmp_path / "anthem.oga"
    unsupported.write_bytes(b"audio")
    player = HiddenPlayerSpy()
    director = NationalAnthemDirector(
        enabled=True,
        audio_path=str(unsupported),
        player=player,
    )

    decision = director.update("Qualifying", OverlaySpy())

    assert decision.status == "unsupported_audio"
    assert "Convert it to MP3 or WAV" in decision.reason
    assert player.playlists == []


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
    player = HiddenPlayerSpy()
    director = NationalAnthemDirector(
        enabled=True,
        audio_path=str(audio),
        player=player,
    )

    director.update("Qualifying", overlay)
    ended = director.update("Race", overlay)

    assert ended.status == "ended"
    assert overlay.cleared == 1
    assert player.stops == 1


def test_rgc_anthem_reports_missing_audio(tmp_path):
    missing = Path(tmp_path) / "missing.mp3"
    director = NationalAnthemDirector(enabled=True, audio_path=str(missing))

    decision = director.update("Qualifying")

    assert decision.status == "missing_audio"
