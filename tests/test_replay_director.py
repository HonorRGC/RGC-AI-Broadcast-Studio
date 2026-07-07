from types import SimpleNamespace

from production.replay_director import ReplayDirector


class ReplayTelemetry:
    def __init__(self):
        self.seeks = []
        self.live_returns = 0
        self.session_flags = 0
        self.session_state = 0

    def seek_replay_session_time(self, session_num, session_time_seconds):
        self.seeks.append((session_num, session_time_seconds))
        return True

    def seek_previous_incident(self, pre_roll_frames=360):
        self.seeks.append(("previous_incident", pre_roll_frames))
        return True

    def return_to_live(self):
        self.live_returns += 1
        return True

    def get_session_flags(self):
        return self.session_flags

    def get_session_state(self):
        return self.session_state


class ReplayCamera:
    def __init__(self):
        self.replay_active = False
        self.focuses = []
        self.ends = 0

    def begin_replay(self):
        self.replay_active = True

    def focus_replay(self, car_idx, group_name, telemetry):
        self.focuses.append((car_idx, group_name))
        return SimpleNamespace(status="switched", reason="Camera switched.")

    def focus_incident_replay(self, group_name, telemetry):
        self.focuses.append(("incident", group_name))
        return SimpleNamespace(status="switched", reason="Incident camera switched.")

    def end_replay(self, telemetry):
        self.replay_active = False
        self.ends += 1
        return SimpleNamespace(status="switched")


def incident_item(multi_angle=False):
    return SimpleNamespace(
        category="incident",
        dedupe_key="incident:3:incident points",
        camera_target_car_idx=3,
        replay_session_num=2,
        replay_session_time=100.0,
        replay_incident_delta=2,
        replay_multi_angle=multi_angle,
    )


def incident_marker_item():
    return SimpleNamespace(
        category="incident",
        dedupe_key="incident:marker:caution:1:2",
        camera_target_car_idx=None,
        replay_session_num=2,
        replay_session_time=None,
        replay_incident_delta=0,
        replay_multi_angle=True,
        replay_use_incident_marker=True,
    )


def restart_incident_marker_item():
    item = incident_marker_item()
    item.replay_marker_pre_roll_frames = 2400
    return item


def green_item():
    return SimpleNamespace(
        category="race_control",
        dedupe_key="race_control:green:CAUTION",
    )


class AudioBedSpy:
    def __init__(self):
        self.played = []

    def play(self, path):
        self.played.append(path)


def test_ordinary_incident_plays_one_angle_then_returns_live():
    telemetry = ReplayTelemetry()
    camera = ReplayCamera()
    times = iter([10.0, 23.0])
    director = ReplayDirector(mode="auto", angle_groups=("TV1", "TV2"), clock=lambda: next(times))

    started = director.handle_item(incident_item(), telemetry, camera)
    finished = director.update(telemetry, camera)

    assert started.total_angles == 1
    assert telemetry.seeks == [(2, 85.0)]
    assert camera.focuses == [(3, "TV1")]
    assert finished.status == "live"
    assert telemetry.live_returns == 1
    assert camera.replay_active is False


def test_green_flag_incident_replay_does_not_use_caution_audio_bed(tmp_path):
    audio = tmp_path / "caution.mp3"
    audio.write_bytes(b"audio")
    audio_bed = AudioBedSpy()
    telemetry = ReplayTelemetry()
    camera = ReplayCamera()
    director = ReplayDirector(
        mode="auto",
        replay_audio_path=str(audio),
        audio_player=audio_bed,
        clock=lambda: 10.0,
    )

    director.handle_item(incident_item(), telemetry, camera)

    assert audio_bed.played == []


def test_caution_incident_replay_uses_audio_bed_player(tmp_path):
    audio = tmp_path / "caution.mp3"
    audio.write_bytes(b"audio")
    audio_bed = AudioBedSpy()
    telemetry = ReplayTelemetry()
    camera = ReplayCamera()
    director = ReplayDirector(
        mode="auto",
        replay_audio_path=str(audio),
        audio_player=audio_bed,
        clock=lambda: 10.0,
    )

    director.handle_item(incident_item(multi_angle=True), telemetry, camera)

    assert audio_bed.played == [str(audio.resolve())]


def test_new_caution_incident_replays_tv1_then_tv2_before_live():
    telemetry = ReplayTelemetry()
    camera = ReplayCamera()
    times = iter([10.0, 23.0, 36.0])
    director = ReplayDirector(mode="auto", angle_groups=("TV1", "TV2"), clock=lambda: next(times))

    started = director.handle_item(incident_item(multi_angle=True), telemetry, camera)
    second_angle = director.update(telemetry, camera)
    finished = director.update(telemetry, camera)

    assert started.total_angles == 2
    assert second_angle.status == "angle"
    assert second_angle.angle_group == "TV2"
    assert telemetry.seeks == [(2, 85.0), (2, 85.0)]
    assert camera.focuses == [(3, "TV1"), (3, "TV2")]
    assert finished.status == "live"
    assert telemetry.live_returns == 1


def test_default_caution_replay_package_uses_one_stable_angle():
    telemetry = ReplayTelemetry()
    camera = ReplayCamera()
    times = iter([10.0, 23.0])
    director = ReplayDirector(mode="auto", clock=lambda: next(times))

    started = director.handle_item(incident_item(multi_angle=True), telemetry, camera)
    finished = director.update(telemetry, camera)

    assert started.total_angles == 1
    assert finished.status == "live"
    assert camera.focuses == [(3, "Far Chase")]


def test_caution_replay_holds_until_configured_duration():
    telemetry = ReplayTelemetry()
    camera = ReplayCamera()
    times = iter([10.0, 29.0, 31.0])
    director = ReplayDirector(
        mode="auto",
        angle_seconds=20.0,
        clock=lambda: next(times),
    )

    director.handle_item(incident_item(multi_angle=True), telemetry, camera)
    held = director.update(telemetry, camera)
    finished = director.update(telemetry, camera)

    assert held.status == "held"
    assert finished.status == "live"
    assert telemetry.live_returns == 1


def test_green_flag_interrupts_replay_and_returns_live_immediately():
    telemetry = ReplayTelemetry()
    camera = ReplayCamera()
    director = ReplayDirector(mode="auto", angle_groups=("TV1", "TV2"), clock=lambda: 10.0)
    director.handle_item(incident_item(multi_angle=True), telemetry, camera)

    decision = director.handle_item(green_item(), telemetry, camera)

    assert decision.status == "live"
    assert telemetry.live_returns == 1
    assert camera.replay_active is False


def test_observe_mode_never_seeks_or_changes_live_replay_state():
    telemetry = ReplayTelemetry()
    camera = ReplayCamera()
    director = ReplayDirector(mode="observe", angle_groups=("TV1", "TV2"), clock=lambda: 10.0)

    decision = director.handle_item(incident_item(), telemetry, camera)

    assert decision.status == "started"
    assert telemetry.seeks == []
    assert telemetry.live_returns == 0
    assert camera.focuses == []
    assert camera.replay_active is False


def test_caution_replay_continues_during_caution_flag_state():
    telemetry = ReplayTelemetry()
    camera = ReplayCamera()
    times = iter([10.0, 23.0])
    director = ReplayDirector(mode="auto", angle_groups=("TV1", "TV2"), clock=lambda: next(times))
    director.handle_item(incident_item(multi_angle=True), telemetry, camera)
    telemetry.session_flags = 0x00000004

    decision = director.update(telemetry, camera)

    assert decision.status == "angle"
    assert telemetry.live_returns == 0
    assert camera.replay_active is True


def test_incident_marker_replay_uses_iracing_previous_incident_camera():
    telemetry = ReplayTelemetry()
    camera = ReplayCamera()
    times = iter([10.0, 23.0, 36.0])
    director = ReplayDirector(mode="auto", angle_groups=("TV1", "TV2"), clock=lambda: next(times))

    started = director.handle_item(incident_marker_item(), telemetry, camera)
    second_angle = director.update(telemetry, camera)

    assert started.status == "started"
    assert started.total_angles == 2
    assert second_angle.status == "angle"
    assert telemetry.seeks == [
        ("previous_incident", 1500),
        ("previous_incident", 1500),
    ]
    assert telemetry.live_returns == 1
    assert camera.focuses == [("incident", "TV1"), ("incident", "TV2")]


def test_incident_marker_replay_pre_roll_frames_are_configurable():
    telemetry = ReplayTelemetry()
    camera = ReplayCamera()
    director = ReplayDirector(
        mode="auto",
        angle_groups=("TV1", "TV2"),
        incident_marker_pre_roll_frames=480,
        clock=lambda: 10.0,
    )

    director.handle_item(incident_marker_item(), telemetry, camera)

    assert telemetry.seeks == [("previous_incident", 480)]


def test_incident_marker_replay_can_use_per_item_restart_preroll():
    telemetry = ReplayTelemetry()
    camera = ReplayCamera()
    director = ReplayDirector(
        mode="auto",
        incident_marker_pre_roll_frames=1500,
        clock=lambda: 10.0,
    )

    director.handle_item(restart_incident_marker_item(), telemetry, camera)

    assert telemetry.seeks == [("previous_incident", 2400)]
