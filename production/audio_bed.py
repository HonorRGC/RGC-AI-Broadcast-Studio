from pathlib import Path
import ctypes
import threading

from config import CAUTION_REPLAY_AUDIO


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
        self.lock = threading.Lock()

    def play(self, audio_path=None):
        path = Path(str(audio_path or self.audio_path or "")).expanduser()
        if not path.exists():
            return False

        with self.lock:
            resolved = str(path.resolve())
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

    def close_locked(self):
        if self.restore_timer:
            self.restore_timer.cancel()
            self.restore_timer = None
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
