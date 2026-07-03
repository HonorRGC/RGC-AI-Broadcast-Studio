from broadcast.engine import BroadcastEngine
from broadcaster.race_director import RacePhase
from replay.telemetry_snapshot import TelemetrySnapshot


class SilentOpenAI:
    def is_enabled(self):
        return False

    def generate_commentary(self, fallback_text="", **_):
        return fallback_text


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

    emitted = engine.tick(SnapshotSource(snapshot))
    pending_green = [
        item for item in engine.broadcast_queue.items if "green" in item.dedupe_key
    ]

    assert emitted.category == "race_control"
    assert emitted.dedupe_key.startswith("race_control:green")
    assert pending_green == []


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

    emitted = engine.tick(SnapshotSource(snapshot))

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

    engine.tick(SnapshotSource(snapshot))

    rundown = [
        item for item in engine.broadcast_queue.items
        if item.category.startswith("opening_field_rundown")
    ]
    assert len(rundown) == 2
    assert "Driver 12" in rundown[1].message


def test_engine_preserves_camera_target_for_close_action():
    results = [
        {"CarIdx": index, "Position": index, "LapsComplete": 5}
        for index in range(3)
    ]
    drivers = {
        index: {"name": f"Driver {index + 1}", "number": str(index + 1)}
        for index in range(3)
    }
    snapshot = TelemetrySnapshot(
        lap=5,
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
    engine.tick(source)
    source.snapshot = TelemetrySnapshot(
        lap=3,
        total_laps=20,
        session_flags=RaceFlags.CAUTION,
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

    engine.tick(source)

    incident_items = [
        item for item in engine.broadcast_queue.items if item.category == "incident"
    ]
    assert len(incident_items) == 1
    assert incident_items[0].camera_target_car_idx == 0


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
    assert "post_race" in categories
    assert "incident" not in categories


class RaceFlags:
    GREEN = 0x00000004
    CAUTION = 0x00004000
    ONE_TO_GREEN = 0x00000200
    START_READY = 0x20000000
    START_GO = 0x80000000
