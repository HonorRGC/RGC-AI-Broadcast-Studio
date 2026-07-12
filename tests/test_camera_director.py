from types import SimpleNamespace

from production.camera_director import CameraDirector


class CameraTelemetry:
    def __init__(self):
        self.switches = []
        self.at_live_edge = True
        self.return_to_live_calls = 0

    def get_driver_lookup(self):
        return {
            0: {"name": "Leader", "number": "77"},
            3: {"name": "Eric Hudec", "number": "14"},
            4: {"name": "Another Driver", "number": "24"},
        }

    def get_results(self):
        return [
            {"CarIdx": 0, "Position": 0},
            {"CarIdx": 3, "Position": 1},
            {"CarIdx": 4, "Position": 2},
        ]

    def get_session_type(self):
        return "Race"

    def get_camera_groups(self):
        return [
            {"GroupNum": 1, "GroupName": "Scenic"},
            {"GroupNum": 2, "GroupName": "Fixed"},
            {"GroupNum": 3, "GroupName": "Static"},
            {"GroupNum": 7, "GroupName": "TV Fixed"},
            {"GroupNum": 4, "GroupName": "TV1"},
            {"GroupNum": 5, "GroupName": "TV Mixed"},
            {"GroupNum": 6, "GroupName": "Cockpit"},
        ]

    def switch_camera_to_car(self, car_number, group_number, camera_number=0):
        self.switches.append((car_number, group_number, camera_number))
        return True

    def switch_camera_to_incident(self, group_number, camera_number=0):
        self.switches.append(("incident", group_number, camera_number))
        return True

    def is_replay_at_live_edge(self):
        return self.at_live_edge

    def return_to_live(self):
        self.return_to_live_calls += 1
        self.at_live_edge = True
        return True


def target_item(car_idx=3):
    return SimpleNamespace(
        camera_target_car_idx=car_idx,
        camera_sequence=(),
        dedupe_key="race_story",
        category="race_story",
        message="A developing race story.",
    )


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


def test_camera_can_focus_iracing_incident_camera():
    telemetry = CameraTelemetry()
    director = CameraDirector(mode="auto", preferred_group="TV1")

    decision = director.focus_incident_replay("TV1", telemetry)

    assert decision.status == "switched"
    assert decision.group_number == 4
    assert telemetry.switches == [("incident", 4, 0)]


def test_caution_item_immediately_focuses_incident_camera():
    telemetry = CameraTelemetry()
    director = CameraDirector(mode="auto", preferred_group="TV1")
    item = SimpleNamespace(
        camera_focus_incident=True,
        camera_incident_group="Far Chase",
        category="race_control",
        dedupe_key="race_control:caution",
    )

    decision = director.follow(item, telemetry)

    assert decision.status == "switched"
    assert decision.group_number == 4
    assert telemetry.switches == [("incident", 4, 0)]


def test_caution_incident_camera_returns_to_leader_after_hold():
    telemetry = CameraTelemetry()
    times = iter([100.0, 100.0, 111.0, 136.0])
    director = CameraDirector(
        mode="auto",
        preferred_group="TV1",
        return_after_seconds=10,
        incident_return_after_seconds=35,
        clock=lambda: next(times),
    )
    item = SimpleNamespace(
        camera_focus_incident=True,
        camera_incident_group="Far Chase",
        category="race_control",
        dedupe_key="race_control:caution",
    )

    incident = director.follow(item, telemetry)
    held = director.update(telemetry)
    home = director.update(telemetry)

    assert incident.status == "switched"
    assert held.status == "held"
    assert home.status == "switched"
    assert telemetry.switches == [("incident", 4, 0), ("77", 5, 0)]


def test_unknown_camera_group_fails_without_sending_command():
    telemetry = CameraTelemetry()
    director = CameraDirector(mode="auto", preferred_group="Not A Group")

    decision = director.follow(target_item(), telemetry)

    assert decision.status == "failed"
    assert telemetry.switches == []


def test_tv_mixed_home_shot_falls_back_to_tv3_when_missing():
    telemetry = CameraTelemetry()
    telemetry.get_camera_groups = lambda: [
        {"GroupNum": 4, "GroupName": "TV1"},
        {"GroupNum": 7, "GroupName": "TV3"},
    ]
    director = CameraDirector(mode="auto")

    decision = director.update(telemetry)

    assert decision.status == "switched"
    assert decision.group_name == "TV3"
    assert telemetry.switches == [("77", 7, 0)]


def test_rear_chase_lineup_falls_back_to_far_chase_when_missing():
    telemetry = CameraTelemetry()
    telemetry.get_camera_groups = lambda: [
        {"GroupNum": 4, "GroupName": "TV1"},
        {"GroupNum": 8, "GroupName": "Far Chase"},
    ]
    director = CameraDirector(mode="auto")
    lineup = SimpleNamespace(
        camera_target_car_idx=None,
        camera_sequence=(),
        camera_sequence_steps=((3, "Rear Chase", 0),),
        dedupe_key="opening_field_rundown_1",
        message="On the pole is one driver.",
    )

    decision = director.follow(lineup, telemetry)

    assert decision.status == "switched"
    assert decision.group_name == "Far Chase"
    assert telemetry.switches == [("14", 8, 0)]


def test_single_driver_lineup_holds_shot_instead_of_returning_home():
    telemetry = CameraTelemetry()
    telemetry.get_camera_groups = lambda: [
        {"GroupNum": 4, "GroupName": "TV1"},
        {"GroupNum": 8, "GroupName": "Rear Chase"},
        {"GroupNum": 9, "GroupName": "TV Mixed"},
    ]
    times = iter([100.0, 106.0])
    director = CameraDirector(mode="auto", clock=lambda: next(times))
    lineup = SimpleNamespace(
        camera_target_car_idx=None,
        camera_sequence=(),
        camera_sequence_steps=((3, "Rear Chase", 0),),
        dedupe_key="opening_field_rundown_1",
        message="On the pole is one driver.",
    )

    first = director.follow(lineup, telemetry)
    held = director.update(telemetry)

    assert first.status == "switched"
    assert held.status == "held"
    assert telemetry.switches == [("14", 8, 0)]


def test_final_lineup_driver_returns_to_tv_mixed_home():
    telemetry = CameraTelemetry()
    telemetry.get_camera_groups = lambda: [
        {"GroupNum": 8, "GroupName": "Rear Chase"},
        {"GroupNum": 9, "GroupName": "TV Mixed"},
    ]
    times = iter([100.0, 106.0])
    director = CameraDirector(mode="auto", clock=lambda: next(times))
    lineup = SimpleNamespace(
        camera_target_car_idx=None,
        camera_sequence=(),
        camera_sequence_steps=((3, "Rear Chase", 0),),
        camera_return_home_after_sequence=True,
        dedupe_key="opening_field_rundown_25",
        message="Starting 25th, the 25 of Final Driver. That is your field.",
    )

    first = director.follow(lineup, telemetry)
    home = director.update(telemetry)

    assert first.status == "switched"
    assert home.status == "switched"
    assert telemetry.switches == [("14", 8, 0), ("77", 9, 0)]


def test_story_shot_returns_to_leader_on_tv_mixed_after_ten_seconds():
    telemetry = CameraTelemetry()
    times = iter([100.0, 111.0])
    director = CameraDirector(mode="auto", clock=lambda: next(times))

    story = director.follow(target_item(3), telemetry)
    home = director.update(telemetry)

    assert story.status == "switched"
    assert home.status == "switched"
    assert telemetry.switches == [("14", 4, 0), ("77", 5, 0)]


def test_green_flag_forces_camera_back_to_leader():
    telemetry = CameraTelemetry()
    times = iter([100.0, 101.0])
    director = CameraDirector(mode="auto", clock=lambda: next(times))
    director.follow(target_item(3), telemetry)
    green = SimpleNamespace(
        camera_target_car_idx=None,
        camera_sequence=(),
        dedupe_key="race_control:green:FORMATION",
        message="Green flag!",
    )

    decision = director.follow(green, telemetry)

    assert decision.status == "switched"
    assert telemetry.switches[-1] == ("77", 5, 0)


def test_lineup_sequence_advances_to_each_named_driver():
    telemetry = CameraTelemetry()
    times = iter([100.0, 105.0])
    director = CameraDirector(mode="auto", clock=lambda: next(times))
    lineup = SimpleNamespace(
        camera_target_car_idx=None,
        camera_sequence=(3, 4),
        dedupe_key="opening_field_rundown_1",
        message="On the pole is one driver. Alongside is another driver.",
    )

    first = director.follow(lineup, telemetry)
    second = director.update(telemetry)

    assert first.status == "switched"
    assert second.status == "switched"
    assert telemetry.switches == [("14", 4, 1), ("24", 4, 1)]


def test_custom_sequence_can_switch_tv1_then_cockpit_for_same_driver():
    telemetry = CameraTelemetry()
    times = iter([100.0, 103.0])
    director = CameraDirector(mode="auto", clock=lambda: next(times))
    rundown = SimpleNamespace(
        camera_target_car_idx=None,
        camera_sequence=(),
        camera_sequence_steps=((3, "TV1", 0), (3, "Cockpit", 0)),
        dedupe_key="quarter_field_rundown_1",
        message="Quarter-race field rundown for one driver.",
    )

    first = director.follow(rundown, telemetry)
    second = director.update(telemetry)

    assert first.status == "switched"
    assert second.status == "switched"
    assert telemetry.switches == [("14", 4, 0), ("14", 6, 0)]


def test_silent_feature_sequence_uses_feature_duration_for_timing():
    telemetry = CameraTelemetry()
    times = iter([100.0, 104.0, 105.0])
    director = CameraDirector(mode="auto", clock=lambda: next(times))
    feature = SimpleNamespace(
        camera_target_car_idx=None,
        camera_sequence=(),
        camera_sequence_steps=((3, "Crank Fixed", 0),),
        dedupe_key="crank_it_up:10",
        category="crank_it_up",
        message="Crank It Up",
        silent=True,
        feature_duration_seconds=10.0,
        camera_return_home_after_sequence=True,
    )

    first = director.follow(feature, telemetry)
    held = director.update(telemetry)

    assert first.status == "switched"
    assert held.status == "held"
    assert telemetry.switches == [("14", 7, 0)]


def test_spoken_feature_sequence_uses_feature_duration_for_timing():
    telemetry = CameraTelemetry()
    times = iter([100.0, 109.0, 110.0])
    director = CameraDirector(mode="auto", clock=lambda: next(times))
    rundown = SimpleNamespace(
        camera_target_car_idx=None,
        camera_sequence=(),
        camera_sequence_steps=((3, "TV1", 0), (3, "Cockpit", 0)),
        dedupe_key="long_green_field_rundown_1",
        category="long_green_field_rundown_1",
        message="Long green top ten rundown.",
        silent=False,
        feature_duration_seconds=20.0,
        camera_return_home_after_sequence=False,
    )

    first = director.follow(rundown, telemetry)
    held = director.update(telemetry)
    second = director.update(telemetry)

    assert first.status == "switched"
    assert held.status == "held"
    assert second.status == "switched"
    assert telemetry.switches == [("14", 4, 0), ("14", 6, 0)]


def test_crank_fixed_does_not_fall_back_to_moving_tv_cameras():
    telemetry = CameraTelemetry()
    telemetry.get_camera_groups = lambda: [
        {"GroupNum": 4, "GroupName": "TV1"},
        {"GroupNum": 5, "GroupName": "TV Mixed"},
    ]
    director = CameraDirector(mode="auto")
    feature = SimpleNamespace(
        camera_target_car_idx=None,
        camera_sequence=(),
        camera_sequence_steps=((3, "Crank Fixed", 0),),
        dedupe_key="crank_it_up:10",
        category="crank_it_up",
        message="Crank It Up",
        silent=True,
        feature_duration_seconds=10.0,
        camera_return_home_after_sequence=True,
    )

    decision = director.follow(feature, telemetry)

    assert decision.status == "failed"
    assert telemetry.switches == []


def test_tv_fixed_request_prefers_exact_tv_fixed_camera_group():
    telemetry = CameraTelemetry()
    director = CameraDirector(mode="auto", preferred_group="TV Fixed")

    decision = director.follow(target_item(3), telemetry)

    assert decision.status == "switched"
    assert decision.group_name == "TV Fixed"
    assert telemetry.switches == [("14", 7, 0)]


def test_fixed_camera_request_falls_back_to_scenic_or_tv_when_missing():
    telemetry = CameraTelemetry()
    telemetry.get_camera_groups = lambda: [
        {"GroupNum": 1, "GroupName": "Scenic"},
        {"GroupNum": 4, "GroupName": "TV1"},
    ]
    director = CameraDirector(mode="auto", preferred_group="Fixed")

    decision = director.follow(target_item(3), telemetry)

    assert decision.status == "switched"
    assert decision.group_name == "Scenic"
    assert telemetry.switches == [("14", 1, 0)]


def test_incident_camera_can_interrupt_the_minimum_hold():
    telemetry = CameraTelemetry()
    times = iter([100.0, 101.0])
    director = CameraDirector(mode="auto", clock=lambda: next(times))
    director.follow(target_item(3), telemetry)
    incident = target_item(4)
    incident.category = "incident"

    decision = director.follow(incident, telemetry)

    assert decision.status == "switched"
    assert telemetry.switches[-1] == ("24", 4, 0)


def test_auto_mode_returns_a_behind_replay_view_to_live():
    telemetry = CameraTelemetry()
    telemetry.at_live_edge = False
    director = CameraDirector(mode="auto", clock=lambda: 100.0)

    decision = director.update(telemetry)

    assert decision.status == "live"
    assert telemetry.return_to_live_calls == 1


def test_live_edge_enforcement_is_suspended_during_incident_replay():
    telemetry = CameraTelemetry()
    telemetry.at_live_edge = False
    director = CameraDirector(mode="auto", clock=lambda: 100.0)
    director.begin_replay()

    decision = director.update(telemetry)

    assert decision.status == "held"
    assert telemetry.return_to_live_calls == 0


def test_end_replay_requires_next_update_to_verify_live_edge():
    telemetry = CameraTelemetry()
    telemetry.at_live_edge = False
    director = CameraDirector(mode="auto", clock=lambda: 100.0)
    director.begin_replay()

    home = director.end_replay(telemetry)
    live = director.update(telemetry)

    assert home.status == "switched"
    assert home.car_number == "77"
    assert live.status == "live"
    assert telemetry.return_to_live_calls == 1
