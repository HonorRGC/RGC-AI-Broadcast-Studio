import threading

from production.audio_bed import PlaylistAudioPlayer


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
