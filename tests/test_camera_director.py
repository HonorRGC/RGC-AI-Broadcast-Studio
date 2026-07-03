from types import SimpleNamespace

from production.camera_director import CameraDirector


class CameraTelemetry:
    def __init__(self):
        self.switches = []

    def get_driver_lookup(self):
        return {3: {"name": "Eric Hudec", "number": "14"}}

    def get_camera_groups(self):
        return [
            {"GroupNum": 1, "GroupName": "Scenic"},
            {"GroupNum": 4, "GroupName": "TV1"},
        ]

    def switch_camera_to_car(self, car_number, group_number, camera_number=0):
        self.switches.append((car_number, group_number, camera_number))
        return True


def target_item(car_idx=3):
    return SimpleNamespace(camera_target_car_idx=car_idx)


def test_observe_mode_reports_target_without_switching_camera():
    telemetry = CameraTelemetry()
    director = CameraDirector(mode="observe", preferred_group="TV1")

    decision = director.follow(target_item(), telemetry)

    assert decision.status == "suggested"
    assert decision.car_number == "14"
    assert decision.group_number == 4
    assert telemetry.switches == []


def test_auto_mode_switches_to_target_car_and_holds_the_shot():
    telemetry = CameraTelemetry()
    times = iter([100.0, 102.0])
    director = CameraDirector(
        mode="auto",
        preferred_group="TV1",
        minimum_hold_seconds=8,
        clock=lambda: next(times),
    )

    switched = director.follow(target_item(3), telemetry)
    held = director.follow(target_item(4), telemetry)

    assert switched.status == "switched"
    assert telemetry.switches == [("14", 4, 0)]
    assert held.status == "held"


def test_camera_story_without_target_is_ignored():
    telemetry = CameraTelemetry()
    director = CameraDirector(mode="auto")

    decision = director.follow(target_item(None), telemetry)

    assert decision.status == "ignored"
    assert telemetry.switches == []


def test_unknown_camera_group_fails_without_sending_command():
    telemetry = CameraTelemetry()
    director = CameraDirector(mode="auto", preferred_group="Not A Group")

    decision = director.follow(target_item(), telemetry)

    assert decision.status == "failed"
    assert telemetry.switches == []
