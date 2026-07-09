from pathlib import Path
import os

from config import PRACTICE_MUSIC_PLAYLIST, SPONSOR_READ_CAUSE, SPONSOR_READ_NAME
from production.session_tracker import SessionTracker, WeekendSession


class PracticePresentationDirector:
    def __init__(
        self,
        playlist=None,
        player=None,
        sponsor_name=SPONSOR_READ_NAME,
        sponsor_cause=SPONSOR_READ_CAUSE,
    ):
        self.playlist = list(playlist if playlist is not None else PRACTICE_MUSIC_PLAYLIST)
        self.player = player or getattr(os, "startfile", None)
        self.sponsor_name = sponsor_name
        self.sponsor_cause = sponsor_cause
        self.session_tracker = SessionTracker()
        self.presentation_shown = False
        self.music_started = False

    def update(self, session_type, overlay_server=None):
        session = self.session_tracker.normalize(session_type)
        if session != WeekendSession.PRACTICE:
            if overlay_server and self.presentation_shown:
                overlay_server.clear_special_presentation()
            self.presentation_shown = False
            return None

        if overlay_server and not self.presentation_shown:
            overlay_server.show_special_presentation(
                kind="race_sponsors",
                title="Today's Race Sponsors",
                subtitle=self.subtitle(),
                duration=3600,
            )
            self.presentation_shown = True

        if self.playlist and not self.music_started:
            self.music_started = True
            return self.play_first_available_song()

        return None

    def subtitle(self):
        parts = [part for part in [self.sponsor_name, self.sponsor_cause] if part]
        return " • ".join(parts) if parts else "RGC AI Broadcast Studio"

    def play_first_available_song(self):
        if not self.player:
            return "Practice music is configured, but no desktop audio player is available."
        for raw_path in self.playlist:
            path = Path(raw_path).expanduser()
            if not path.exists():
                continue
            try:
                self.player(str(path.resolve()))
            except Exception as error:
                return f"Practice music could not be played: {error}"
        return f"Practice music started: {path.name}"
        return "Practice music playlist is configured, but no listed file was found."


class QualifyingCameraDirector:
    def __init__(self, hold_seconds=8.0, clock=None):
        self.hold_seconds = float(hold_seconds)
        self.clock = clock
        self.last_focus_at = 0.0
        self.last_car_idx = None

    def update(self, telemetry, camera_director):
        session_type = str(telemetry.get_session_type() or "").lower()
        is_practice = "practice" in session_type
        is_qualifying = "qual" in session_type
        if not (is_practice or is_qualifying):
            self.last_car_idx = None
            return None

        if getattr(camera_director, "replay_active", False):
            return None

        car_idx = self.pick_active_car(telemetry)
        if car_idx is None:
            return None

        now = camera_director.clock()
        if (
            self.last_car_idx == car_idx
            and self.last_focus_at
            and now - self.last_focus_at < self.hold_seconds
        ):
            return None

        group_name = "Cockpit" if is_qualifying else "TV1"
        role = "qualifying" if is_qualifying else "practice"

        decision = camera_director.focus_car(
            car_idx,
            group_name,
            telemetry,
            now,
            role=role,
            force=self.last_car_idx is None,
        )
        if decision.status in ("suggested", "switched", "held"):
            self.last_car_idx = car_idx
            self.last_focus_at = now
        return decision

    def pick_active_car(self, telemetry):
        results = telemetry.get_results() or []
        if not results:
            results = [
                {"CarIdx": car_idx, "Position": 999}
                for car_idx in (telemetry.get_driver_lookup() or {}).keys()
            ]
        pit_road = telemetry.get_car_idx_on_pit_road()
        surfaces = telemetry.get_car_idx_track_surface()
        lap_pct = telemetry.get_car_idx_lap_dist_pct()

        best = None
        for car in results:
            car_idx = car.get("CarIdx")
            if car_idx is None:
                continue
            if self.array_value(pit_road, car_idx, False):
                continue
            surface = self.array_value(surfaces, car_idx, 3)
            if surface not in (2, 3):
                continue
            pct = float(self.array_value(lap_pct, car_idx, 0.0) or 0.0)
            if pct <= 0:
                continue
            position = self.safe_int(car.get("Position"), 999)
            candidate = (position, -pct, car_idx)
            if best is None or candidate < best:
                best = candidate
        return best[2] if best else None

    def array_value(self, values, index, default=None):
        try:
            return values[int(index)]
        except Exception:
            return default

    def safe_int(self, value, default=0):
        try:
            return int(value)
        except Exception:
            return default
