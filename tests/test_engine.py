from broadcast.engine import BroadcastEngine
from broadcaster.race_director import RacePhase
from replay.telemetry_snapshot import TelemetrySnapshot
import time


class SilentOpenAI:
    def is_enabled(self):
        return False

    def generate_commentary(self, fallback_text="", **_):
        return fallback_text


class StubSponsorReads:
    def __init__(self):
        self.opening_sent = False
        self.caution_sent = False

    def opening_read(self):
        if self.opening_sent:
            return None
        self.opening_sent = True
        return "Opening sponsor read."

    def caution_read(self, current_lap=0):
        if self.caution_sent:
            return None
        self.caution_sent = True
        return f"Caution sponsor read on lap {current_lap}."


class SnapshotSource:
    def __init__(self, snapshot):
        self.snapshot = snapshot

    def get_results(self):
        return self.snapshot.results

    def get_starting_grid(self):
        return self.snapshot.starting_grid or self.snapshot.results

    def get_driver_lookup(self):
        return self.snapshot.driver_lookup

    def get_lap(self):
        return self.snapshot.race_lap()

    def get_total_laps(self):
        return self.snapshot.total_laps

    def get_session_flags(self):
        return self.snapshot.session_flags

    def get_session_state(self):
        return self.snapshot.session_state

    def get_current_session_num(self):
        return self.snapshot.session_num

    def get_session_time(self):
        return self.snapshot.session_time

    def get_session_type(self):
        return self.snapshot.session_type

    def get_track_info(self):
        return self.snapshot.track_info

    def get_car_idx_on_pit_road(self):
        return self.snapshot.pit_road_status

    def get_car_idx_track_surface(self):
        return self.snapshot.track_surface

    def get_car_idx_track_surface_material(self):
        return self.snapshot.track_surface_material

    def get_car_idx_lap_dist_pct(self):
        return self.snapshot.lap_dist_pct

    def get_car_idx_est_time(self):
        return self.snapshot.est_time


def test_engine_queues_exactly_one_initial_green_flag():
    snapshot = TelemetrySnapshot(
        lap=1,
        total_laps=20,
        session_flags=RaceFlags.GREEN | RaceFlags.START_GO,
        track_info={"track_name": "Daytona"},
        results=[{"CarIdx": 0, "Position": 1, "LapsComplete": 1}],
        driver_lookup={0: {"name": "Alex Driver", "number": "7"}},
        pit_road_status=[False],
        track_surface=[3],
        track_surface_material=[0],
        lap_dist_pct=[0.1],
        est_time=[10.0],
    )
    engine = BroadcastEngine(openai_director=SilentOpenAI())

    source = SnapshotSource(snapshot)
    emitted = engine.tick(source)
    engine.tick(source)
    engine.tick(source)
    engine.tick(source)
    pending_green = [
        item for item in engine.broadcast_queue.items if "green" in item.dedupe_key
    ]

    assert emitted.category == "race_control"
    assert emitted.dedupe_key.startswith("race_control:green")
    assert pending_green == []


def test_engine_uses_field_lap_when_spectator_lap_lags():
    engine = BroadcastEngine(openai_director=SilentOpenAI())

    lap = engine.best_race_lap(
        5,
        [
            {"CarIdx": 1, "LapsComplete": 40},
            {"CarIdx": 2, "Lap": 39},
        ],
    )

    assert lap == 40


def test_engine_reset_clears_session_state():
    engine = BroadcastEngine(openai_director=SilentOpenAI())
    engine.race_director.race_started = True
    engine.broadcast_queue.add("Old race")

    engine.reset()

    assert engine.race_director.race_started is False
    assert engine.broadcast_queue.items == []


def test_initial_one_to_green_keeps_the_opening_package_available():
    results = [
        {"CarIdx": index, "Position": index, "LapsComplete": 0}
        for index in range(5)
    ]
    drivers = {
        index: {"name": f"Driver {index + 1}", "number": str(index + 1)}
        for index in range(5)
    }
    snapshot = TelemetrySnapshot(
        lap=0,
        total_laps=20,
        session_flags=RaceFlags.ONE_TO_GREEN | RaceFlags.CAUTION,
        track_info={"track_name": "Nashville"},
        results=results,
        driver_lookup=drivers,
        pit_road_status=[False] * 5,
    )
    engine = BroadcastEngine(openai_director=SilentOpenAI())

    source = SnapshotSource(snapshot)
    emitted = engine.tick(source)
    engine.tick(source)
    engine.tick(source)

    assert emitted.category == "opening_welcome"
    assert any(
        item.dedupe_key == "race_control:one_to_green:initial"
        for item in engine.broadcast_queue.items
    )
    assert any(
        item.category == "opening_track_info" for item in engine.broadcast_queue.items
    )
    assert any(
        item.category.startswith("opening_field_rundown")
        for item in engine.broadcast_queue.items
    )


def test_engine_queues_sponsor_read_after_opening_lineup():
    results = [
        {"CarIdx": index, "Position": index, "LapsComplete": 0}
        for index in range(5)
    ]
    drivers = {
        index: {"name": f"Driver {index + 1}", "number": str(index + 1)}
        for index in range(5)
    }
    snapshot = TelemetrySnapshot(
        lap=0,
        total_laps=20,
        session_flags=RaceFlags.START_READY,
        track_info={"track_name": "Nashville"},
        results=results,
        driver_lookup=drivers,
        pit_road_status=[False] * 5,
    )
    engine = BroadcastEngine(openai_director=SilentOpenAI())
    engine.session_tracker.update("Race")
    engine.sponsor_read_director = StubSponsorReads()

    source = SnapshotSource(snapshot)
    engine.tick(source)
    engine.tick(source)
    engine.tick(source)

    sponsor_items = [
        item for item in engine.broadcast_queue.items
        if item.category == "sponsor_read"
    ]
    assert len(sponsor_items) == 1
    assert sponsor_items[0].message == "Opening sponsor read."


def test_engine_is_silent_until_the_race_session_begins():
    results = [
        {"CarIdx": index, "Position": index, "LapsComplete": 0}
        for index in range(5)
    ]
    drivers = {
        index: {"name": f"Driver {index + 1}", "number": str(index + 1)}
        for index in range(5)
    }
    source = SnapshotSource(
        TelemetrySnapshot(
            session_type="Practice",
            results=results,
            driver_lookup=drivers,
        )
    )
    engine = BroadcastEngine(openai_director=SilentOpenAI())

    assert engine.tick(source) is None
    assert engine.broadcast_queue.items == []

    source.snapshot = TelemetrySnapshot(
        session_type="Lone Qualify",
        results=results,
        driver_lookup=drivers,
    )
    assert engine.tick(source) is None
    assert engine.broadcast_queue.items == []

    source.snapshot = TelemetrySnapshot(
        session_type="Race",
        total_laps=20,
        session_flags=RaceFlags.START_READY,
        track_info={"track_name": "Nashville"},
        results=results,
        driver_lookup=drivers,
        pit_road_status=[False] * 5,
    )
    emitted = engine.tick(source)

    assert emitted.category == "opening_welcome"
    assert engine.race_director.race_started is False


def test_engine_uses_qualifying_grid_when_race_results_are_not_ready():
    grid = [{"CarIdx": index, "Position": index} for index in range(12)]
    drivers = {
        index: {"name": f"Driver {index + 1}", "number": str(index + 1)}
        for index in range(12)
    }
    snapshot = TelemetrySnapshot(
        session_type="Race",
        total_laps=20,
        session_flags=RaceFlags.START_READY,
        track_info={"track_name": "Nashville"},
        results=[],
        starting_grid=grid,
        driver_lookup=drivers,
        pit_road_status=[False] * 12,
    )
    engine = BroadcastEngine(openai_director=SilentOpenAI())

    source = SnapshotSource(snapshot)
    engine.tick(source)
    engine.tick(source)
    engine.tick(source)

    rundown = [
        item for item in engine.broadcast_queue.items
        if item.category.startswith("opening_field_rundown")
    ]
    assert len(rundown) == 12
    assert "Driver 12" in rundown[-1].message
    assert all(len(item.camera_sequence) == 1 for item in rundown)


def test_engine_preserves_camera_target_for_close_action():
    results = [
        {"CarIdx": index, "Position": index, "LapsComplete": 4}
        for index in range(3)
    ]
    drivers = {
        index: {"name": f"Driver {index + 1}", "number": str(index + 1)}
        for index in range(3)
    }
    snapshot = TelemetrySnapshot(
        lap=4,
        total_laps=20,
        session_flags=RaceFlags.GREEN,
        results=results,
        driver_lookup=drivers,
        pit_road_status=[False] * 3,
        lap_dist_pct=[0.5000, 0.5007, 0.5014],
    )
    engine = BroadcastEngine(openai_director=SilentOpenAI())

    engine.tick(SnapshotSource(snapshot))

    action_items = [
        item for item in engine.broadcast_queue.items
        if item.camera_target_car_idx is not None
    ]
    assert len(action_items) == 1
    assert action_items[0].participant_car_indices == (0, 1, 2)


def test_engine_queues_quarter_field_rundown_under_green():
    results = [
        {"CarIdx": index, "Position": index, "LapsComplete": 10}
        for index in range(12)
    ]
    drivers = {
        index: {"name": f"Driver {index + 1}", "number": str(index + 1)}
        for index in range(12)
    }
    snapshot = TelemetrySnapshot(
        lap=10,
        total_laps=40,
        session_flags=RaceFlags.GREEN,
        results=results,
        driver_lookup=drivers,
        pit_road_status=[False] * 12,
        track_surface=[3] * 12,
        track_surface_material=[0] * 12,
        lap_dist_pct=[0.1] * 12,
        est_time=[10.0] * 12,
    )
    engine = BroadcastEngine(openai_director=SilentOpenAI())
    engine.race_director.race_started = True

    green = engine.tick(SnapshotSource(snapshot))
    engine.broadcast_queue.busy_until = 0
    rundown = engine.tick(SnapshotSource(snapshot))

    assert green.category == "race_control"
    assert rundown.category == "quarter_field_rundown_1"
    assert rundown.camera_sequence == (0,)
    assert rundown.protected is True
    assert "one quarter into this race" in rundown.message


def test_due_field_rundown_blocks_normal_stories_until_booth_is_clear():
    results = [
        {"CarIdx": index, "Position": index, "LapsComplete": 10}
        for index in range(12)
    ]
    drivers = {
        index: {"name": f"Driver {index + 1}", "number": str(index + 1)}
        for index in range(12)
    }
    snapshot = TelemetrySnapshot(
        lap=10,
        total_laps=40,
        session_flags=RaceFlags.GREEN,
        results=results,
        driver_lookup=drivers,
        pit_road_status=[False] * 12,
        track_surface=[3] * 12,
        track_surface_material=[0] * 12,
        lap_dist_pct=[0.1] * 12,
        est_time=[10.0] * 12,
    )
    engine = BroadcastEngine(openai_director=SilentOpenAI())
    engine.session_tracker.update("Race")
    engine.race_director.race_started = True
    engine.race_director.phase = RacePhase.GREEN
    engine.broadcast_queue.busy_until = time.time() + 60

    first = engine.tick(SnapshotSource(snapshot))

    assert first is None
    assert engine.editorial_producer.items == []
    assert engine.field_rundown_director.is_due_or_active(10, 40) is True

    engine.broadcast_queue.busy_until = 0
    second = engine.tick(SnapshotSource(snapshot))

    assert second.category == "quarter_field_rundown_1"
    assert "one quarter into this race" in second.message


def test_due_field_rundown_waits_for_green_flag_call_then_airs():
    results = [
        {"CarIdx": index, "Position": index, "LapsComplete": 10}
        for index in range(12)
    ]
    drivers = {
        index: {"name": f"Driver {index + 1}", "number": str(index + 1)}
        for index in range(12)
    }
    snapshot = TelemetrySnapshot(
        lap=10,
        total_laps=40,
        session_flags=RaceFlags.GREEN,
        results=results,
        driver_lookup=drivers,
        pit_road_status=[False] * 12,
        track_surface=[3] * 12,
        track_surface_material=[0] * 12,
        lap_dist_pct=[0.1] * 12,
        est_time=[10.0] * 12,
        track_info={"track_name": "Chicagoland Speedway"},
    )
    engine = BroadcastEngine(openai_director=SilentOpenAI())
    engine.race_director.race_started = True
    engine.race_director.phase = RacePhase.CAUTION
    engine.race_director.previous_phase = RacePhase.CAUTION

    green = engine.tick(SnapshotSource(snapshot))

    assert green.category == "race_control"
    assert "Green flag" in green.message

    engine.broadcast_queue.busy_until = 0
    rundown = engine.tick(SnapshotSource(snapshot))

    assert rundown.category == "quarter_field_rundown_1"


def test_pass_story_carries_overtaking_car_as_camera_target():
    engine = BroadcastEngine(openai_director=SilentOpenAI())
    drivers = {
        0: {"name": "Leader", "number": "77"},
        1: {"name": "Eric Hudec", "number": "14"},
    }
    initial = [
        {"CarIdx": 0, "Position": 0, "LapsComplete": 1},
        {"CarIdx": 1, "Position": 3, "LapsComplete": 1},
    ]
    changed = [
        {"CarIdx": 0, "Position": 0, "LapsComplete": 2},
        {"CarIdx": 1, "Position": 2, "LapsComplete": 2},
    ]
    engine.race_brain.analyze(initial, drivers)

    engine._collect_pass_stories(changed, drivers)

    assert engine.editorial_producer.items[0].camera_target_car_idx == 1
    assert engine.editorial_producer.items[0].participant_car_indices == (1,)


def test_inactive_cars_are_filtered_from_pass_stories():
    engine = BroadcastEngine(openai_director=SilentOpenAI())
    drivers = {
        0: {"name": "Leader", "number": "77"},
        1: {"name": "Inactive Driver", "number": "14"},
    }
    initial = [
        {"CarIdx": 0, "Position": 0, "LapsComplete": 4},
        {"CarIdx": 1, "Position": 9, "LapsComplete": 4},
    ]
    snapshot = TelemetrySnapshot(
        lap=5,
        total_laps=90,
        session_flags=RaceFlags.GREEN,
        results=[
            {"CarIdx": 0, "Position": 0, "LapsComplete": 5},
            {"CarIdx": 1, "Position": 2, "LapsComplete": 5},
        ],
        driver_lookup=drivers,
        pit_road_status=[False, False],
        track_surface=[3, 1],
        track_surface_material=[0, 0],
        lap_dist_pct=[0.1, 0.2],
        est_time=[10.0, 10.0],
    )
    engine.race_brain.analyze(initial, drivers)

    engine.tick(SnapshotSource(snapshot))

    assert all(
        item.driver_name != "Inactive Driver"
        for item in engine.editorial_producer.items
    )


def test_incident_is_collected_after_race_enters_caution():
    drivers = {0: {"name": "Driver One", "number": "1"}}
    source = SnapshotSource(
        TelemetrySnapshot(
            lap=3,
            total_laps=20,
            session_flags=RaceFlags.GREEN,
            results=[
                {"CarIdx": 0, "Position": 0, "LapsComplete": 3, "Incidents": 0}
            ],
            driver_lookup=drivers,
            pit_road_status=[False],
            track_surface=[3],
            track_surface_material=[0],
            lap_dist_pct=[0.4],
            est_time=[20.0],
        )
    )
    engine = BroadcastEngine(openai_director=SilentOpenAI())
    emitted = engine.tick(source)
    source.snapshot = TelemetrySnapshot(
        lap=3,
        total_laps=20,
        session_flags=RaceFlags.CAUTION,
        session_num=2,
        session_time=125.0,
        results=[
            {"CarIdx": 0, "Position": 0, "LapsComplete": 3, "Incidents": 2}
        ],
        driver_lookup=drivers,
        pit_road_status=[False],
        track_surface=[3],
        track_surface_material=[0],
        lap_dist_pct=[0.4],
        est_time=[20.0],
    )

    emitted = engine.tick(source)

    incident_items = [
        item for item in engine.broadcast_queue.items if item.category == "incident"
    ]
    assert len(incident_items) == 1
    assert incident_items[0].camera_target_car_idx == 0
    assert incident_items[0].replay_session_num == 2
    assert incident_items[0].replay_session_time == 125.0
    assert incident_items[0].replay_multi_angle is True
    assert emitted.dedupe_key == "race_control:caution"


def test_early_caution_without_candidate_queues_iracing_incident_marker_replay():
    drivers = {0: {"name": "Driver One", "number": "1"}}
    snapshot = TelemetrySnapshot(
        lap=1,
        total_laps=20,
        session_flags=RaceFlags.CAUTION,
        session_num=2,
        session_time=35.0,
        results=[
            {"CarIdx": 0, "Position": 0, "LapsComplete": 1, "Incidents": 0}
        ],
        driver_lookup=drivers,
        pit_road_status=[False],
        track_surface=[3],
        track_surface_material=[0],
        lap_dist_pct=[0.4],
        est_time=[20.0],
    )
    engine = BroadcastEngine(openai_director=SilentOpenAI())
    engine.race_director.phase = RacePhase.CAUTION
    engine.race_director.previous_phase = RacePhase.GREEN
    engine.race_director.phase_changed = True

    engine._collect_incidents(
        telemetry=SnapshotSource(snapshot),
        results=snapshot.results,
        driver_lookup=drivers,
        pit_road_status=snapshot.pit_road_status,
        current_lap=1,
    )

    incident = next(
        item for item in engine.broadcast_queue.items if item.category == "incident"
    )
    assert incident.replay_use_incident_marker is True
    assert incident.replay_multi_angle is True
    assert incident.camera_target_car_idx is None


def test_green_flag_incident_requests_only_one_replay_angle():
    drivers = {0: {"name": "Driver One", "number": "1"}}
    source = SnapshotSource(
        TelemetrySnapshot(
            lap=3,
            total_laps=20,
            session_flags=RaceFlags.GREEN,
            session_num=2,
            session_time=50.0,
            results=[
                {"CarIdx": 0, "Position": 0, "LapsComplete": 3, "Incidents": 0}
            ],
            driver_lookup=drivers,
            pit_road_status=[False],
            track_surface=[3],
            track_surface_material=[0],
            lap_dist_pct=[0.4],
            est_time=[20.0],
        )
    )
    engine = BroadcastEngine(openai_director=SilentOpenAI())
    engine.tick(source)
    source.snapshot = TelemetrySnapshot(
        lap=3,
        total_laps=20,
        session_flags=RaceFlags.GREEN,
        session_num=2,
        session_time=51.0,
        results=[
            {"CarIdx": 0, "Position": 0, "LapsComplete": 3, "Incidents": 2}
        ],
        driver_lookup=drivers,
        pit_road_status=[False],
        track_surface=[3],
        track_surface_material=[0],
        lap_dist_pct=[0.4],
        est_time=[20.0],
    )

    emitted = engine.tick(source)

    incident = emitted
    assert incident.replay_session_time == 51.0
    assert incident.replay_multi_angle is False


def test_incident_after_caution_transition_uses_only_one_replay_angle():
    drivers = {0: {"name": "Driver One", "number": "1"}}
    source = SnapshotSource(
        TelemetrySnapshot(
            lap=3,
            total_laps=20,
            session_flags=RaceFlags.GREEN,
            results=[
                {"CarIdx": 0, "Position": 0, "LapsComplete": 3, "Incidents": 0}
            ],
            driver_lookup=drivers,
            pit_road_status=[False],
            track_surface=[3],
            track_surface_material=[0],
            lap_dist_pct=[0.4],
            est_time=[20.0],
        )
    )
    engine = BroadcastEngine(openai_director=SilentOpenAI())
    engine.tick(source)
    source.snapshot = TelemetrySnapshot(
        lap=3,
        total_laps=20,
        session_flags=RaceFlags.CAUTION,
        results=[
            {"CarIdx": 0, "Position": 0, "LapsComplete": 3, "Incidents": 0}
        ],
        driver_lookup=drivers,
        pit_road_status=[False],
        track_surface=[3],
        track_surface_material=[0],
        lap_dist_pct=[0.4],
        est_time=[20.0],
    )
    engine.tick(source)
    source.snapshot.results[0]["Incidents"] = 2
    source.snapshot.session_time = 60.0

    engine.tick(source)

    incident = next(
        item for item in engine.broadcast_queue.items
        if item.category == "incident" and item.replay_incident_delta == 2
    )
    assert incident.replay_multi_angle is False


def test_soft_off_pace_signal_does_not_interrupt_broadcast_under_green():
    drivers = {0: {"name": "Driver One", "number": "1"}}
    engine = BroadcastEngine(openai_director=SilentOpenAI())
    engine.session_tracker.update("Race")
    engine.race_director.race_started = True
    engine.race_director.phase = RacePhase.GREEN

    engine._collect_incidents(
        telemetry=SnapshotSource(
            TelemetrySnapshot(
                lap=8,
                total_laps=90,
                session_flags=RaceFlags.GREEN,
                results=[{"CarIdx": 0, "Position": 1, "LapsComplete": 8, "Incidents": 0}],
                driver_lookup=drivers,
                track_surface=[3],
                track_surface_material=[0],
                lap_dist_pct=[0.5],
                est_time=[10.0],
            )
        ),
        results=[{"CarIdx": 0, "Position": 1, "LapsComplete": 8, "Incidents": 0}],
        driver_lookup=drivers,
        pit_road_status=[False],
        current_lap=8,
    )
    engine._collect_incidents(
        telemetry=SnapshotSource(
            TelemetrySnapshot(
                lap=8,
                total_laps=90,
                session_flags=RaceFlags.GREEN,
                results=[{"CarIdx": 0, "Position": 1, "LapsComplete": 8, "Incidents": 0}],
                driver_lookup=drivers,
                track_surface=[3],
                track_surface_material=[0],
                lap_dist_pct=[0.5],
                est_time=[25.0],
            )
        ),
        results=[{"CarIdx": 0, "Position": 1, "LapsComplete": 8, "Incidents": 0}],
        driver_lookup=drivers,
        pit_road_status=[False],
        current_lap=8,
    )

    assert [
        item for item in engine.broadcast_queue.items
        if item.category == "incident"
    ] == []


def test_one_to_green_reports_small_caution_pit_group():
    engine = BroadcastEngine(openai_director=SilentOpenAI())
    engine.sponsor_read_director = StubSponsorReads()
    results = [
        {"CarIdx": index, "Position": index}
        for index in range(6)
    ]
    drivers = {
        index: {"name": f"Driver {index + 1}", "number": str(index + 1)}
        for index in range(6)
    }
    engine.race_director.phase = RacePhase.CAUTION
    engine._collect_pit_stories(
        results=results,
        driver_lookup=drivers,
        pit_road_status=[False, True, False, False, False, False],
        current_lap=5,
    )
    engine.race_director.phase = RacePhase.ONE_TO_GREEN
    engine._collect_pit_stories(
        results=results,
        driver_lookup=drivers,
        pit_road_status=[False, False, False, False, False, False],
        current_lap=6,
    )

    pit_item = next(
        item for item in engine.broadcast_queue.items
        if item.dedupe_key.startswith("caution_pit_small_group")
    )
    assert "Only a few takers" in pit_item.message
    assert pit_item.speaker == "sarah"
    assert pit_item.camera_target_car_idx is None
    assert any(
        item.category == "sponsor_read"
        and item.message == "Caution sponsor read on lap 6."
        for item in engine.broadcast_queue.items
    )


def test_cool_down_state_airs_checkered_and_suppresses_false_incident():
    drivers = {0: {"name": "Race Winner", "number": "77"}}
    source = SnapshotSource(
        TelemetrySnapshot(
            lap=9,
            total_laps=10,
            session_flags=RaceFlags.GREEN,
            session_state=4,
            results=[
                {"CarIdx": 0, "Position": 0, "LapsComplete": 9, "Incidents": 0}
            ],
            driver_lookup=drivers,
            pit_road_status=[False],
            track_surface=[3],
            track_surface_material=[0],
            lap_dist_pct=[0.9],
            est_time=[20.0],
        )
    )
    engine = BroadcastEngine(openai_director=SilentOpenAI())
    engine.tick(source)
    source.snapshot = TelemetrySnapshot(
        lap=9,
        total_laps=10,
        session_flags=0,
        session_state=6,
        results=[
            {"CarIdx": 0, "Position": 0, "LapsComplete": 9, "Incidents": 2}
        ],
        driver_lookup=drivers,
        pit_road_status=[False],
        track_surface=[1],
        track_surface_material=[0],
        lap_dist_pct=[0.4],
        est_time=[30.0],
    )

    engine.tick(source)

    categories = [item.category for item in engine.broadcast_queue.items]
    assert engine.race_director.phase == RacePhase.CHECKERED
    assert "incident" not in categories
    assert "post_race" not in categories

    for _ in range(3):
        engine.tick(source)

    categories = [item.category for item in engine.broadcast_queue.items]
    assert "post_race" in categories
    assert "incident" not in categories


class RaceFlags:
    GREEN = 0x00000004
    CAUTION = 0x00004000
    ONE_TO_GREEN = 0x00000200
    START_READY = 0x20000000
    START_GO = 0x80000000
