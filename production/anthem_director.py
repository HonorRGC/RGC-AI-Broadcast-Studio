from dataclasses import dataclass
from pathlib import Path

from config import (
    NATIONAL_ANTHEM_GRAPHICS,
    NATIONAL_ANTHEM_AUDIO,
    STUDIO_VOLUME,
    USE_NATIONAL_ANTHEM,
)
from production.audio_bed import (
    PlaylistAudioPlayer,
    existing_hidden_audio_paths,
    is_supported_hidden_audio_file,
    percent_to_mci_volume,
)
from production.session_tracker import SessionTracker, WeekendSession


@dataclass(frozen=True)
class AnthemDecision:
    status: str
    reason: str


class NationalAnthemDirector:
    def __init__(
        self,
        enabled=USE_NATIONAL_ANTHEM,
        audio_path=NATIONAL_ANTHEM_AUDIO,
        player=None,
        studio_volume=STUDIO_VOLUME,
        graphics=None,
    ):
        self.enabled = bool(enabled)
        self.audio_path = str(audio_path or "").strip()
        self.player = player or PlaylistAudioPlayer(
            normal_volume=percent_to_mci_volume(studio_volume),
            alias="rgc_anthem_audio",
        )
        self.graphics = list(graphics if graphics is not None else NATIONAL_ANTHEM_GRAPHICS)
        self.session_tracker = SessionTracker()
        self.played = False
        self.active = False

    def update(self, session_type, overlay_server=None):
        session = self.session_tracker.normalize(session_type)
        if not self.enabled:
            return AnthemDecision("ignored", "National anthem is disabled.")

        if session == WeekendSession.QUALIFYING and not self.played:
            self.played = True
            self.active = True
            if overlay_server:
                overlay_server.show_special_presentation(
                    kind="rgc_anthem",
                    title="RGC Anthem",
                    subtitle="Presented by RGC Motorsports",
                    duration=24 * 60 * 60,
                    graphics=self.graphics,
                )
            return self.play_audio()

        if self.active and session == WeekendSession.RACE:
            self.active = False
            self.stop_audio()
            if overlay_server:
                overlay_server.clear_special_presentation()
            return AnthemDecision("ended", "RGC Anthem presentation ended.")

        return AnthemDecision("ignored", "No anthem action is due.")

    def play_audio(self):
        playlist = self.audio_playlist()
        if not playlist:
            return AnthemDecision(
                "shown",
                "RGC Anthem overlay shown; no audio file is configured.",
            )

        existing_paths = existing_hidden_audio_paths(playlist)
        if not existing_paths:
            unsupported_paths = [
                path
                for path in playlist
                if path.exists() and not is_supported_hidden_audio_file(path)
            ]
            if unsupported_paths:
                return AnthemDecision(
                    "unsupported_audio",
                    "RGC Anthem audio uses an unsupported file type. Convert it to MP3 or WAV: "
                    f"{unsupported_paths[0]}",
                )
            return AnthemDecision(
                "missing_audio",
                f"RGC Anthem audio file was not found: {playlist[0]}",
            )

        try:
            if self.play_with_player([str(path) for path in existing_paths]) is False:
                return AnthemDecision(
                    "audio_failed",
                    "RGC Anthem audio could not be played by the hidden audio player.",
                )
        except Exception as error:
            return AnthemDecision(
                "audio_failed",
                f"RGC Anthem audio could not be played: {error}",
            )

        return AnthemDecision("played", "RGC Anthem presentation started.")

    def audio_playlist(self):
        return [
            Path(item.strip()).expanduser()
            for item in self.audio_path.split(";")
            if item.strip()
        ]

    def play_with_player(self, paths):
        if hasattr(self.player, "play_playlist_once"):
            return self.player.play_playlist_once(paths)
        if hasattr(self.player, "play_playlist"):
            return self.player.play_playlist(paths)
        if hasattr(self.player, "play"):
            return self.player.play(paths[0])
        return self.player(paths[0])

    def stop_audio(self):
        stopper = getattr(self.player, "stop", None)
        if stopper:
            stopper()

    def set_music_volume(self, volume_percent):
        setter = getattr(self.player, "set_volume", None)
        if setter:
            setter(percent_to_mci_volume(volume_percent))
