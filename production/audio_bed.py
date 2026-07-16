from pathlib import Path
import ctypes
import threading
import time

from config import CAUTION_REPLAY_AUDIO


SUPPORTED_MCI_AUDIO_EXTENSIONS = {
    ".aac",
    ".flac",
    ".m4a",
    ".mp3",
    ".wav",
    ".wma",
}


def is_supported_hidden_audio_file(path):
    return Path(str(path or "")).suffix.lower() in SUPPORTED_MCI_AUDIO_EXTENSIONS


def existing_hidden_audio_paths(playlist):
    paths = [Path(str(path or "")).expanduser() for path in playlist]
    return [
        path.resolve()
        for path in paths
        if path.exists() and is_supported_hidden_audio_file(path)
    ]


def percent_to_mci_volume(volume_percent):
    try:
        percent = int(volume_percent)
    except (TypeError, ValueError):
        percent = 65
    return max(0, min(1000, percent * 10))


class AudioBedPlayer:
    """Small Windows music-bed player with ducking support.

    It uses the built-in WinMM/MCI API so the project does not need another
    dependency just to keep a caution music bed rolling under commentary.
    """

    def __init__(
        self,
        audio_path=CAUTION_REPLAY_AUDIO,
        normal_volume=650,
        ducked_volume=140,
        alias="rgc_caution_bed",
    ):
        self.audio_path = str(audio_path or "").strip()
        self.normal_volume = int(normal_volume)
        self.ducked_volume = int(ducked_volume)
        self.alias = alias
        self.active_path = ""
        self.is_playing = False
        self.restore_timer = None
        self.fade_stop_event = None
        self.current_volume = self.normal_volume
        self.lock = threading.Lock()

    def play(self, audio_path=None):
        path = Path(str(audio_path or self.audio_path or "")).expanduser()
        if not path.exists():
            return False

        with self.lock:
            resolved = str(path.resolve())
            if self.fade_stop_event:
                self.fade_stop_event.set()
                self.fade_stop_event = None
            if self.is_playing and self.active_path == resolved:
                self.set_volume(self.normal_volume)
                return True

            self.close_locked()
            opened = self.send(f'open "{resolved}" type mpegvideo alias {self.alias}')
            if not opened:
                opened = self.send(f'open "{resolved}" alias {self.alias}')
            if not opened:
                return False

            self.active_path = resolved
            self.set_volume(self.normal_volume)
            if not self.send(f"play {self.alias} repeat"):
                self.close_locked()
                return False
            self.is_playing = True
            return True

    def duck(self):
        with self.lock:
            if self.is_playing:
                self.set_volume(self.ducked_volume)

    def restore(self):
        with self.lock:
            if self.is_playing:
                self.set_volume(self.normal_volume)

    def restore_after(self, seconds):
        with self.lock:
            if not self.is_playing:
                return
            if self.restore_timer:
                self.restore_timer.cancel()
            self.restore_timer = threading.Timer(max(0.1, float(seconds)), self.restore)
            self.restore_timer.daemon = True
            self.restore_timer.start()

    def stop(self):
        with self.lock:
            self.close_locked()

    def fade_out(self, duration_seconds=2.5, steps=10):
        with self.lock:
            if not self.is_playing:
                return False
            if self.restore_timer:
                self.restore_timer.cancel()
                self.restore_timer = None
            if self.fade_stop_event:
                self.fade_stop_event.set()
            stop_event = threading.Event()
            self.fade_stop_event = stop_event
            start_volume = self.current_volume

        thread = threading.Thread(
            target=self.fade_out_worker,
            args=(stop_event, start_volume, duration_seconds, steps),
            daemon=True,
        )
        thread.start()
        return True

    def fade_out_and_wait(self, duration_seconds=0.7, steps=6):
        with self.lock:
            if not self.is_playing:
                return False
            if self.restore_timer:
                self.restore_timer.cancel()
                self.restore_timer = None
            if self.fade_stop_event:
                self.fade_stop_event.set()
            stop_event = threading.Event()
            self.fade_stop_event = stop_event
            start_volume = self.current_volume

        self.fade_out_worker(stop_event, start_volume, duration_seconds, steps)
        return True

    def fade_out_worker(self, stop_event, start_volume, duration_seconds, steps):
        steps = max(1, int(steps or 1))
        duration_seconds = max(0.1, float(duration_seconds or 0.1))
        delay = duration_seconds / steps
        for step in range(steps, -1, -1):
            if stop_event.is_set():
                return
            volume = int(start_volume * step / steps)
            self.set_volume(volume)
            time.sleep(delay)
        if stop_event.is_set():
            return
        with self.lock:
            if self.fade_stop_event is stop_event:
                self.close_locked()

    def close_locked(self):
        if self.restore_timer:
            self.restore_timer.cancel()
            self.restore_timer = None
        if self.fade_stop_event:
            self.fade_stop_event.set()
            self.fade_stop_event = None
        self.send(f"stop {self.alias}")
        self.send(f"close {self.alias}")
        self.active_path = ""
        self.is_playing = False

    def set_volume(self, volume):
        volume = max(0, min(1000, int(volume)))
        self.current_volume = volume
        return self.send(f"setaudio {self.alias} volume to {volume}")

    def send(self, command):
        try:
            winmm = ctypes.windll.winmm
        except Exception:
            return False
        result = winmm.mciSendStringW(str(command), None, 0, None)
        return int(result or 0) == 0


class PlaylistAudioPlayer:
    """Loop a playlist with the built-in Windows MCI audio player."""

    def __init__(self, normal_volume=650, alias="rgc_practice_music"):
        self.normal_volume = int(normal_volume)
        self.alias = alias
        self.thread = None
        self.stop_event = threading.Event()
        self.lock = threading.Lock()
        self.active_playlist = []
        self.is_playing = False

    def play_playlist(self, playlist):
        paths = existing_hidden_audio_paths(playlist)
        if not paths:
            return False

        playlist_key = [str(path) for path in paths]
        with self.lock:
            if self.is_playing and self.active_playlist == playlist_key:
                return True
            self.stop_locked()
            self.stop_event.clear()
            self.active_playlist = playlist_key
            self.thread = threading.Thread(
                target=self.loop_playlist,
                args=(playlist_key,),
                daemon=True,
            )
            self.thread.start()
            self.is_playing = True
            return True

    def play_playlist_once(self, playlist):
        paths = existing_hidden_audio_paths(playlist)
        if not paths:
            return False

        playlist_key = [str(path) for path in paths]
        with self.lock:
            if self.is_playing and self.active_playlist == playlist_key:
                return True
            self.stop_locked()
            self.stop_event.clear()
            self.active_playlist = playlist_key
            self.thread = threading.Thread(
                target=self.play_sequence_once,
                args=(playlist_key,),
                daemon=True,
            )
            self.thread.start()
            self.is_playing = True
            return True

    def loop_playlist(self, playlist):
        while not self.stop_event.is_set():
            for path in playlist:
                if self.stop_event.is_set():
                    break
                self.play_one(path)

    def play_sequence_once(self, playlist):
        for path in playlist:
            if self.stop_event.is_set():
                break
            self.play_one(path)
        with self.lock:
            if self.active_playlist == playlist:
                self.active_playlist = []
                self.is_playing = False
                self.thread = None

    def play_one(self, path):
        if self.stop_event.is_set():
            return False

        self.close_alias()
        opened = self.send(f'open "{path}" type mpegvideo alias {self.alias}')
        if not opened:
            opened = self.send(f'open "{path}" alias {self.alias}')
        if not opened:
            return False

        if self.stop_event.is_set():
            self.close_alias()
            return False

        self.set_volume(self.normal_volume)
        if self.stop_event.is_set():
            self.close_alias()
            return False

        played = self.send(f"play {self.alias}")
        if played:
            self.wait_until_finished_or_stopped()
        self.close_alias()
        return played

    def wait_until_finished_or_stopped(self):
        while not self.stop_event.is_set():
            mode = self.query(f"status {self.alias} mode")
            if mode and mode.lower() not in {"playing", "seeking"}:
                break
            time.sleep(0.2)

    def stop(self):
        thread = None
        with self.lock:
            thread = self.thread
            self.stop_locked()
        if thread and thread.is_alive() and thread is not threading.current_thread():
            thread.join(timeout=1.0)

    def stop_locked(self):
        self.stop_event.set()
        self.close_alias()
        self.active_playlist = []
        self.is_playing = False
        self.thread = None

    def close_alias(self):
        self.send(f"stop {self.alias}")
        self.send(f"close {self.alias}")

    def set_volume(self, volume):
        volume = max(0, min(1000, int(volume)))
        return self.send(f"setaudio {self.alias} volume to {volume}")

    def send(self, command):
        try:
            winmm = ctypes.windll.winmm
        except Exception:
            return False
        result = winmm.mciSendStringW(str(command), None, 0, None)
        return int(result or 0) == 0

    def query(self, command):
        try:
            winmm = ctypes.windll.winmm
        except Exception:
            return ""
        buffer = ctypes.create_unicode_buffer(128)
        result = winmm.mciSendStringW(str(command), buffer, len(buffer), None)
        if int(result or 0) != 0:
            return ""
        return buffer.value.strip()


class OneShotAudioPlayer:
    """Play one local audio file through Windows MCI without opening a player UI."""

    def __init__(self, normal_volume=800, alias="rgc_one_shot_audio"):
        self.normal_volume = int(normal_volume)
        self.alias = alias
        self.active_path = ""
        self.is_playing = False
        self.close_timer = None
        self.lock = threading.Lock()

    def play(self, audio_path, duration_seconds=None):
        path = Path(str(audio_path or "")).expanduser()
        if not path.exists():
            return False

        with self.lock:
            resolved = str(path.resolve())
            self.close_locked()
            opened = self.send(f'open "{resolved}" type mpegvideo alias {self.alias}')
            if not opened:
                opened = self.send(f'open "{resolved}" alias {self.alias}')
            if not opened:
                return False

            self.active_path = resolved
            self.set_volume(self.normal_volume)
            if not self.send(f"play {self.alias}"):
                self.close_locked()
                return False
            self.is_playing = True
            self.schedule_close(duration_seconds)
            return True

    def stop(self):
        with self.lock:
            self.close_locked()

    def schedule_close(self, duration_seconds):
        if not duration_seconds:
            return
        self.close_timer = threading.Timer(
            max(0.1, float(duration_seconds)),
            self.stop,
        )
        self.close_timer.daemon = True
        self.close_timer.start()

    def close_locked(self):
        if self.close_timer:
            self.close_timer.cancel()
            self.close_timer = None
        self.send(f"stop {self.alias}")
        self.send(f"close {self.alias}")
        self.active_path = ""
        self.is_playing = False

    def set_volume(self, volume):
        volume = max(0, min(1000, int(volume)))
        return self.send(f"setaudio {self.alias} volume to {volume}")

    def send(self, command):
        try:
            winmm = ctypes.windll.winmm
        except Exception:
            return False
        result = winmm.mciSendStringW(str(command), None, 0, None)
        return int(result or 0) == 0
