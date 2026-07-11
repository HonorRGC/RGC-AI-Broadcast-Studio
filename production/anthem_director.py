from dataclasses import dataclass
from pathlib import Path

from config import (
    NATIONAL_ANTHEM_AUDIO,
    NATIONAL_ANTHEM_DURATION_SECONDS,
    USE_NATIONAL_ANTHEM,
)
from production.audio_bed import OneShotAudioPlayer
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
        duration_seconds=NATIONAL_ANTHEM_DURATION_SECONDS,
        player=None,
    ):
        self.enabled = bool(enabled)
        self.audio_path = str(audio_path or "").strip()
        self.duration_seconds = float(duration_seconds or 90)
        self.player = player or OneShotAudioPlayer(alias="rgc_anthem_audio")
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
                    duration=self.duration_seconds,
                )
            return self.play_audio()

        if self.active and session == WeekendSession.RACE:
            self.active = False
            if overlay_server:
                overlay_server.clear_special_presentation()
            return AnthemDecision("ended", "RGC Anthem presentation ended.")

        return AnthemDecision("ignored", "No anthem action is due.")

    def play_audio(self):
        if not self.audio_path:
            return AnthemDecision(
                "shown",
                "RGC Anthem overlay shown; no audio file is configured.",
            )

        path = Path(self.audio_path).expanduser()
        if not path.exists():
            return AnthemDecision(
                "missing_audio",
                f"RGC Anthem audio file was not found: {path}",
            )

        try:
            if self.play_with_player(str(path.resolve())) is False:
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

    def play_with_player(self, path):
        if hasattr(self.player, "play"):
            return self.player.play(path, duration_seconds=self.duration_seconds)
        return self.player(path)
