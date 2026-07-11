import threading

from production.audio_bed import OneShotAudioPlayer, PlaylistAudioPlayer


class PlaylistAudioPlayerSpy(PlaylistAudioPlayer):
    def __init__(self):
        super().__init__(alias="test_practice_music")
        self.commands = []

    def send(self, command):
        self.commands.append(command)
        return True


def test_playlist_player_does_not_start_song_after_stop_signal():
    player = PlaylistAudioPlayerSpy()
    player.stop_event.set()

    played = player.play_one("D:/Music/practice.mp3")

    assert played is False
    assert not any(command.startswith("open ") for command in player.commands)
    assert not any(command.startswith("play ") for command in player.commands)


def test_playlist_player_stop_joins_background_thread():
    player = PlaylistAudioPlayerSpy()
    finished = threading.Event()

    def worker():
        finished.wait(0.1)

    player.thread = threading.Thread(target=worker)
    player.thread.start()
    player.is_playing = True

    player.stop()

    assert player.stop_event.is_set()
    assert player.thread is None


class OneShotAudioPlayerSpy(OneShotAudioPlayer):
    def __init__(self):
        super().__init__(alias="test_one_shot_audio")
        self.commands = []

    def send(self, command):
        self.commands.append(command)
        return True


def test_one_shot_audio_player_plays_without_repeat_or_wait(tmp_path):
    audio = tmp_path / "anthem.mp3"
    audio.write_bytes(b"audio")
    player = OneShotAudioPlayerSpy()

    played = player.play(str(audio), duration_seconds=10)

    assert played is True
    assert any(command.startswith("open ") for command in player.commands)
    assert f"play {player.alias}" in player.commands
    assert f"play {player.alias} repeat" not in player.commands
    assert f"play {player.alias} wait" not in player.commands
    player.stop()


def test_one_shot_audio_player_stops_and_closes_alias(tmp_path):
    audio = tmp_path / "anthem.mp3"
    audio.write_bytes(b"audio")
    player = OneShotAudioPlayerSpy()
    player.play(str(audio))
    player.commands.clear()

    player.stop()

    assert f"stop {player.alias}" in player.commands
    assert f"close {player.alias}" in player.commands
    assert player.is_playing is False
