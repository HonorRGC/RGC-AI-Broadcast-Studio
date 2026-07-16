from broadcaster.race_director import RacePhase
from config import CAUTION_PRESENTATION_GRAPHICS, SPONSOR_READ_CAUSE, SPONSOR_READ_NAME


class CautionPresentationDirector:
    """Controls caution-period sponsor presentation and music-bed cleanup."""

    def __init__(
        self,
        sponsor_name=SPONSOR_READ_NAME,
        sponsor_cause=SPONSOR_READ_CAUSE,
        overlay_duration=600.0,
        graphics=None,
        one_to_green_fade_seconds=1.0,
    ):
        self.sponsor_name = sponsor_name
        self.sponsor_cause = sponsor_cause
        self.overlay_duration = float(overlay_duration)
        self.graphics = list(graphics if graphics is not None else CAUTION_PRESENTATION_GRAPHICS)
        self.one_to_green_fade_seconds = float(one_to_green_fade_seconds)
        self.presentation_shown = False
        self.music_stopped_for_one_to_green = False

    def update(self, phase, overlay_server=None, audio_bed=None):
        phase = self.normalize_phase(phase)

        if phase == RacePhase.CAUTION:
            self.music_stopped_for_one_to_green = False
            if overlay_server and not self.presentation_shown:
                overlay_server.show_special_presentation(
                    kind="race_sponsors",
                    title="Today's Race Sponsors",
                    subtitle=self.subtitle(),
                    duration=self.overlay_duration,
                    graphics=self.graphics,
                )
                self.presentation_shown = True
                return "Caution sponsor overlay shown."
            return None

        if phase == RacePhase.ONE_TO_GREEN:
            self.stop_audio_once(audio_bed)
            return None

        if phase in (RacePhase.GREEN, RacePhase.CHECKERED, RacePhase.FORMATION):
            self.clear_overlay(overlay_server)
            self.music_stopped_for_one_to_green = False
            return None

        return None

    def stop_audio_once(self, audio_bed):
        if self.music_stopped_for_one_to_green:
            return
        fader = getattr(audio_bed, "fade_out", None)
        if fader:
            fader(duration_seconds=self.one_to_green_fade_seconds, steps=8)
        else:
            stopper = getattr(audio_bed, "stop", None)
            if stopper:
                stopper()
        self.music_stopped_for_one_to_green = True

    def clear_overlay(self, overlay_server):
        if overlay_server and self.presentation_shown:
            overlay_server.clear_special_presentation()
        self.presentation_shown = False

    def subtitle(self):
        parts = [part for part in [self.sponsor_name, self.sponsor_cause] if part]
        return " • ".join(parts) if parts else "RGC AI Broadcast Studio"

    @staticmethod
    def normalize_phase(phase):
        if isinstance(phase, RacePhase):
            return phase
        try:
            return RacePhase[str(phase)]
        except Exception:
            return RacePhase.UNKNOWN
