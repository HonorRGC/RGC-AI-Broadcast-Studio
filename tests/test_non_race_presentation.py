from types import SimpleNamespace

from production.non_race_presentation import (
    PracticePresentationDirector,
    QualifyingCameraDirector,
)


class OverlaySpy:
    def __init__(self):
        self.presentations = []
        self.cleared = 0

    def show_special_presentation(self, **kwargs):
        self.presentations.append(kwargs)

    def clear_special_presentation(self):
        self.cleared += 1


def test_practice_presentation_shows_race_sponsors_and_clears_after_practice():
    overlay = OverlaySpy()
    director = PracticePresentationDirector(
        sponsor_name="RGC Motorsports",
        sponsor_cause="Autism Awareness",
    )

    director.update("Practice", overlay)
    director.update("Qualifying", overlay)

    assert overlay.presentations[0]["kind"] == "race_sponsors"
    assert overlay.presentations[0]["title"] == "Today's Race Sponsors"
    assert "RGC Motorsports" in overlay.presentations[0]["subtitle"]
    assert overlay.cleared == 1


def test_practice_presentation_can_start_practice_music(tmp_path):
    song = tmp_path / "practice.mp3"
    song.write_bytes(b"audio")
    played = []
    director = PracticePresentationDirector(playlist=[str(song)], player=played.append)

    message = director.update("Practice", OverlaySpy())

    assert played == [str(song.resolve())]
    assert "Practice music started" in message


def test_practice_presentation_reports_missing_music_file(tmp_path):
    missing = tmp_path / "missing.mp3"
    played = []
    director = PracticePresentationDirector(playlist=[str(missing)], player=played.append)

    message = director.update("Practice", OverlaySpy())

    assert played == []
    assert message == "Practice music playlist is configured, but no listed file was found."


class QualifyingTelemetry:
    def get_session_type(self):
        return "Qualifying"

    def get_results(self):
        return [
            {"CarIdx": 3, "Position": 1},
            {"CarIdx": 7, "Position": 0},
        ]

    def get_car_idx_on_pit_road(self):
        return [False] * 8

    def get_car_idx_track_surface(self):
        return [0, 0, 0, 3, 0, 0, 0, 3]

    def get_car_idx_lap_dist_pct(self):
        return [0.0, 0.0, 0.0, 0.25, 0.0, 0.0, 0.0, 0.50]


class CameraSpy:
    def __init__(self):
        self.replay_active = False
        self.calls = []

    def clock(self):
        return 100.0

    def focus_car(self, car_idx, group_name, telemetry, now, role, force=False):
        self.calls.append((car_idx, group_name, role, force))
        return SimpleNamespace(
            status="switched",
            car_idx=car_idx,
            car_number=str(car_idx),
            group_name=group_name,
        )


def test_qualifying_camera_uses_cockpit_for_active_qualifier():
    director = QualifyingCameraDirector()
    camera = CameraSpy()

    decision = director.update(QualifyingTelemetry(), camera)

    assert decision.status == "switched"
    assert camera.calls == [(7, "Cockpit", "qualifying", True)]


def test_practice_camera_uses_tv1_for_active_driver():
    class PracticeTelemetry(QualifyingTelemetry):
        def get_session_type(self):
            return "Practice"

    director = QualifyingCameraDirector()
    camera = CameraSpy()

    decision = director.update(PracticeTelemetry(), camera)

    assert decision.status == "switched"
    assert camera.calls == [(7, "TV1", "practice", True)]
