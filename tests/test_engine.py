from broadcast.engine import BroadcastEngine
from broadcaster.race_director import RacePhase
from production.penalty_detector import PenaltyDetector
from production.race_state_tracker import RaceState
from replay.telemetry_snapshot import TelemetrySnapshot
from types import SimpleNamespace
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


def test_live_battle_editorial_items_expire_quickly():
    assert BroadcastEngine.editorial_queue_expiry_seconds(
        SimpleNamespace(story_type="live_side_by_side")
    ) == 8
    assert BroadcastEngine.editorial_queue_expiry_seconds(
        SimpleNamespace(story_type="live_pass_clear")
    ) == 8
    assert BroadcastEngine.editorial_queue_expiry_seconds(
        SimpleNamespace(story_type="biggest_mover")
    ) == 45


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

    def get_car_idx_session_flags(self):
        return self.snapshot.car_idx_session_flags

    def get_car_idx_penalty_reasons(self):
        return self.snapshot.car_idx_penalty_reasons


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
    pending_green = [
        item for item in engine.broadcast_queue.items if "green" in item.dedupe_key
    ]

    assert emitted.category == "race_control"
    assert emitted.dedupe_key.startswith("race_control:green")
    assert pending_green == []


def test_engine_queues_stage_end_points_top_ten_under_green():
    engine = BroadcastEngine(openai_director=SilentOpenAI())
    engine.stage_end_laps = (30,)
    results = [
        {"CarIdx": index, "Position": index}
        for index in range(10)
    ]
    drivers = {
        index: {"name": f"Driver {index + 1}", "number": str(index + 1)}
        for index in range(10)
    }

    queued = engine._queue_stage_end_if_due(
        results,
        drivers,
        current_lap=30,
        caution=False,
    )

    assert queued is True
    item = engine.broadcast_queue.next_item()
    assert item.category == "stage_end"
    assert "Stage 1 is complete at lap 30" in item.message
    assert "wins the stage" in item.message
    assert "stage points top ten" in item.message


def test_engine_rewrites_caution_as_stage_break_when_stage_caution_flies():
    engine = BroadcastEngine(openai_director=SilentOpenAI())
    engine.stage_end_laps = (30,)
    engine.broadcast_queue.add(
        "Trouble on the speedway - caution is out here at Daytona.",
        priority=12,
        category="race_control",
        protected=True,
        dedupe_key="race_control:caution",
    )
    results = [{"CarIdx": 0, "Position": 0}]
    drivers = {0: {"name": "Stage Winner", "number": "24"}}

    queued = engine._queue_stage_end_if_due(
        results,
        drivers,
        current_lap=30,
        caution=True,
    )

    assert queued is True
    caution_item = [
        item for item in engine.broadcast_queue.items
        if item.dedupe_key == "race_control:caution"
    ][0]
    assert "scheduled stage break" in caution_item.message
    assert "Stage 1" in caution_item.message


def test_engine_stage_end_only_queues_once():
    engine = BroadcastEngine(openai_director=SilentOpenAI())
    engine.stage_end_laps = (30,)
    results = [{"CarIdx": 0, "Position": 0}]
    drivers = {0: {"name": "Stage Winner", "number": "24"}}

    first = engine._queue_stage_end_if_due(results, drivers, current_lap=30)
    second = engine._queue_stage_end_if_due(results, drivers, current_lap=31)

    assert first is True
    assert second is False


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
    engine.tick(source)
    engine.tick(source)

    assert emitted.category == "opening_welcome"
    assert any(
        item.dedupe_key == "race_control:one_to_green:initial"
        for item in engine.broadcast_queue.items
    )
    assert not any(item.category == "opening_race_outlook" for item in engine.broadcast_queue.items)
    assert any(item.category == "opening_pit_report" for item in engine.broadcast_queue.items)
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
    engine.tick(source)
    engine.tick(source)

    sponsor_items = [
        item for item in engine.broadcast_queue.items
        if item.category == "sponsor_read"
    ]
    assert len(sponsor_items) == 1
    assert sponsor_items[0].message == "Opening sponsor read."
    assert sponsor_items[0].priority == 8
    assert sponsor_items[0].delay_seconds == 1.0


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


def test_engine_submits_pack_formation_story():
    results = [
        {"CarIdx": index, "Position": index, "LapsComplete": 8}
        for index in range(6)
    ]
    drivers = {
        index: {"name": f"Driver {index + 1}", "number": str(index + 1)}
        for index in range(6)
    }
    snapshot = TelemetrySnapshot(
        lap=8,
        total_laps=30,
        session_flags=RaceFlags.GREEN,
        results=results,
        driver_lookup=drivers,
        pit_road_status=[False] * 6,
        track_surface=[3] * 6,
        lap_dist_pct=[0.5000, 0.5040, 0.5080, 0.5120, 0.5160, 0.5200],
    )
    engine = BroadcastEngine(openai_director=SilentOpenAI())
    engine.session_tracker.update("Race")
    engine.race_director.race_started = True
    engine.race_director.phase = RacePhase.GREEN

    engine.tick(SnapshotSource(snapshot))

    formation_items = [
        item for item in engine.editorial_producer.items
        if item.story_type == "formation_single_file"
    ]
    assert len(formation_items) == 1
    assert "single-file rhythm" in formation_items[0].summary
    assert "draft train" not in formation_items[0].summary.lower()
    assert formation_items[0].speaker == "jeff"


def test_engine_queues_long_green_field_rundown_under_green():
    results = [
        {"CarIdx": index, "Position": index, "LapsComplete": 20}
        for index in range(12)
    ]
    drivers = {
        index: {"name": f"Driver {index + 1}", "number": str(index + 1)}
        for index in range(12)
    }
    snapshot = TelemetrySnapshot(
        lap=20,
        total_laps=60,
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
    engine.race_intelligence.race_state_tracker.initialized = True

    green = engine.tick(SnapshotSource(snapshot))
    engine.broadcast_queue.busy_until = 0
    rundown = engine.tick(SnapshotSource(snapshot))

    assert green.category == "race_control"
    assert rundown.category == "long_green_field_rundown_1"
    assert rundown.camera_sequence == (0,)
    assert rundown.protected is True
    assert rundown.feature_duration_seconds == 22.0
    assert rundown.camera_return_home_after_sequence is False
    assert "20-lap green flag run" in rundown.message


def test_engine_blocks_long_green_field_rundown_with_less_than_thirteen_to_go():
    results = [
        {"CarIdx": index, "Position": index, "LapsComplete": 48}
        for index in range(12)
    ]
    drivers = {
        index: {"name": f"Driver {index + 1}", "number": str(index + 1)}
        for index in range(12)
    }
    snapshot = TelemetrySnapshot(
        lap=48,
        total_laps=60,
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
    engine.race_intelligence.race_state_tracker.initialized = True
    engine.race_intelligence.race_state_tracker.state.green_lap_count = 20
    engine.field_rundown_director.active_milestone = "long_green"

    item = engine.tick(SnapshotSource(snapshot))

    assert item is None or item.category != "long_green_field_rundown_1"
    assert engine.field_rundown_director.active_milestone is None


def test_engine_allows_long_green_field_rundown_at_thirteen_to_go():
    results = [
        {"CarIdx": index, "Position": index, "LapsComplete": 47}
        for index in range(12)
    ]
    drivers = {
        index: {"name": f"Driver {index + 1}", "number": str(index + 1)}
        for index in range(12)
    }
    snapshot = TelemetrySnapshot(
        lap=47,
        total_laps=60,
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
    engine.race_intelligence.race_state_tracker.initialized = True
    engine.race_intelligence.race_state_tracker.state.green_lap_count = 20

    item = engine.tick(SnapshotSource(snapshot))

    assert item.category == "long_green_field_rundown_1"
    assert item.protected is True


def test_engine_queues_silent_crank_it_up_after_ten_green_laps():
    results = [
        {"CarIdx": index, "Position": index + 1, "LapsComplete": 10}
        for index in range(8)
    ]
    engine = BroadcastEngine(openai_director=SilentOpenAI())

    queued = engine._queue_crank_it_up(results, green_lap_count=10)

    item = engine.broadcast_queue.next_item(now=time.time())
    assert queued is True
    assert item.category == "crank_it_up_intro"
    assert item.silent is False
    assert item.protected is True
    assert "Crank It Up is presented by RGC Motorsports" in item.message

    engine.broadcast_queue.busy_until = 0
    silent_item = engine.broadcast_queue.next_item(now=time.time())
    assert silent_item.category == "crank_it_up"
    assert silent_item.message == "Crank It Up"
    assert silent_item.silent is True
    assert silent_item.protected is True
    assert silent_item.feature_duration_seconds == 50.0
    assert silent_item.camera_sequence_steps == (
        (0, "Crank Fixed", 0),
        (1, "Crank Fixed", 0),
        (2, "Crank Fixed", 0),
        (3, "Crank Fixed", 0),
    )
    assert silent_item.camera_return_home_after_sequence is True


def test_crank_it_up_does_not_queue_with_fifteen_or_less_to_go():
    results = [
        {"CarIdx": index, "Position": index + 1, "LapsComplete": 51}
        for index in range(8)
    ]
    engine = BroadcastEngine(openai_director=SilentOpenAI())

    queued = engine._queue_crank_it_up(
        results,
        green_lap_count=20,
        laps_remaining=15,
    )

    assert queued is False
    assert engine.broadcast_queue.items == []


def test_crank_it_up_intro_airs_before_silent_feature():
    results = [
        {"CarIdx": index, "Position": index + 1, "LapsComplete": 10}
        for index in range(3)
    ]
    engine = BroadcastEngine(openai_director=SilentOpenAI())

    engine._queue_crank_it_up(results, green_lap_count=10)

    categories = [item.category for item in engine.broadcast_queue.items]
    assert categories == ["crank_it_up_intro", "crank_it_up"]
    assert engine.broadcast_queue.items[0].priority > engine.broadcast_queue.items[1].priority


def test_crank_it_up_silent_feature_uses_tv_fixed_camera():
    results = [
        {"CarIdx": index, "Position": index + 1, "LapsComplete": 10}
        for index in range(8)
    ]
    engine = BroadcastEngine(openai_director=SilentOpenAI())

    engine._queue_crank_it_up(results, green_lap_count=10)

    item = next(
        item for item in engine.broadcast_queue.items
        if item.category == "crank_it_up"
    )
    assert item.silent is True
    assert item.protected is True
    assert item.feature_duration_seconds == 50.0
    assert item.camera_sequence_steps == (
        (0, "Crank Fixed", 0),
        (1, "Crank Fixed", 0),
        (2, "Crank Fixed", 0),
        (3, "Crank Fixed", 0),
    )
    assert item.camera_return_home_after_sequence is True


def test_crank_it_up_runs_once_per_green_run_until_caution_reset():
    results = [
        {"CarIdx": index, "Position": index + 1, "LapsComplete": 10}
        for index in range(6)
    ]
    engine = BroadcastEngine(openai_director=SilentOpenAI())

    assert engine._queue_crank_it_up(results, green_lap_count=10) is True
    engine.broadcast_queue.items.clear()
    engine.broadcast_queue.busy_until = 0
    assert engine._queue_crank_it_up(results, green_lap_count=11) is False

    engine.crank_it_up_sent_this_green_run = False

    assert engine._queue_crank_it_up(results, green_lap_count=10) is True


def test_manual_crank_it_up_bypasses_green_run_trigger():
    results = [
        {"CarIdx": index, "Position": index + 1, "LapsComplete": 2}
        for index in range(4)
    ]
    engine = BroadcastEngine(openai_director=SilentOpenAI())

    queued = engine.queue_manual_crank_it_up(results, sponsor_name="Test Sponsor")

    assert queued is True
    categories = [item.category for item in engine.broadcast_queue.items]
    assert categories == ["crank_it_up_intro", "crank_it_up"]
    assert "Test Sponsor" in engine.broadcast_queue.items[0].message
    assert engine.broadcast_queue.items[1].feature_duration_seconds == 50.0


def test_green_flag_pit_cycle_update_starts_when_multiple_cars_pit():
    engine = BroadcastEngine(openai_director=SilentOpenAI())
    engine.race_director.phase = RacePhase.GREEN
    engine.race_intelligence.race_state.laps_remaining = 40
    events = [
        SimpleNamespace(event_type="PIT_STOP", under_caution=False),
        SimpleNamespace(event_type="PIT_STOP", under_caution=False),
    ]
    results = [
        {"CarIdx": 0, "Position": 1},
        {"CarIdx": 1, "Position": 2},
    ]

    queued = engine._queue_green_pit_cycle_update(
        events,
        results,
        {},
        [True, True],
        current_lap=30,
    )

    assert queued is True
    item = engine.broadcast_queue.next_item()
    assert item.category == "green_pit_cycle_update"
    assert item.speaker == "sarah"
    assert "Green flag pit stops are starting" in item.message


def test_green_flag_pit_cycle_update_reports_recent_stops_after_start():
    engine = BroadcastEngine(openai_director=SilentOpenAI())
    engine.race_director.phase = RacePhase.GREEN
    engine.race_intelligence.race_state.laps_remaining = 35
    engine.green_pit_cycle_announced = True
    engine.green_pit_cycle_last_update_lap = 20
    engine.pit_strategy_detector.driver_states = {
        0: SimpleNamespace(car_idx=0, last_pit_lap=30),
        1: SimpleNamespace(car_idx=1, last_pit_lap=31),
    }

    queued = engine._queue_green_pit_cycle_update(
        [],
        [{"CarIdx": 0, "Position": 1}, {"CarIdx": 1, "Position": 2}],
        {},
        [False, False],
        current_lap=33,
    )

    assert queued is True
    item = engine.broadcast_queue.next_item()
    assert "2 cars have made stops" in item.message


def test_green_flag_pit_cycle_uses_draft_track_strategy_language():
    engine = BroadcastEngine(openai_director=SilentOpenAI())
    engine.race_director.phase = RacePhase.GREEN
    engine.race_intelligence.race_state.laps_remaining = 40

    queued = engine._queue_green_pit_cycle_update(
        [
            SimpleNamespace(event_type="PIT_STOP", under_caution=False, car_idx=0),
            SimpleNamespace(event_type="PIT_STOP", under_caution=False, car_idx=1),
        ],
        [{"CarIdx": 0, "Position": 1}, {"CarIdx": 1, "Position": 2}],
        {},
        [True, True],
        current_lap=30,
        track_info={"track_name": "Daytona International Speedway"},
    )

    assert queued is True
    item = engine.broadcast_queue.next_item()
    assert "fuel" in item.message.lower()
    assert "draft" in item.message.lower()


def test_green_flag_pit_cycle_ignores_parked_race_control_car():
    engine = BroadcastEngine(openai_director=SilentOpenAI())
    engine.race_director.phase = RacePhase.GREEN
    engine.race_intelligence.race_state.laps_remaining = 40
    engine.pit_strategy_detector.driver_states = {
        0: SimpleNamespace(car_idx=0, started_from_pit_road=True, last_pit_exit_lap=0),
        1: SimpleNamespace(car_idx=1, started_from_pit_road=False, last_pit_exit_lap=0),
    }

    queued = engine._queue_green_pit_cycle_update(
        [
            SimpleNamespace(event_type="PIT_STOP", under_caution=False, car_idx=0),
            SimpleNamespace(event_type="PIT_STOP", under_caution=False, car_idx=1),
        ],
        [
            {"CarIdx": 0, "Position": 1, "LapsComplete": 0},
            {"CarIdx": 1, "Position": 2, "LapsComplete": 12},
        ],
        {},
        [True, True],
        current_lap=12,
        track_info={"track_name": "Charlotte Motor Speedway"},
    )

    assert queued is False


def test_due_field_rundown_blocks_normal_stories_until_booth_is_clear():
    results = [
        {"CarIdx": index, "Position": index, "LapsComplete": 20}
        for index in range(12)
    ]
    drivers = {
        index: {"name": f"Driver {index + 1}", "number": str(index + 1)}
        for index in range(12)
    }
    snapshot = TelemetrySnapshot(
        lap=20,
        total_laps=60,
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
    engine.race_intelligence.race_state_tracker.initialized = True
    engine.broadcast_queue.busy_until = time.time() + 60

    first = engine.tick(SnapshotSource(snapshot))

    assert first is None
    assert engine.editorial_producer.items == []
    assert engine.field_rundown_director.is_due_or_active(20, 60, 20) is True

    engine.broadcast_queue.busy_until = 0
    second = engine.tick(SnapshotSource(snapshot))

    assert second.category == "long_green_field_rundown_1"
    assert "20-lap green flag run" in second.message


def test_due_field_rundown_waits_for_green_flag_call_then_airs():
    results = [
        {"CarIdx": index, "Position": index, "LapsComplete": 20}
        for index in range(12)
    ]
    drivers = {
        index: {"name": f"Driver {index + 1}", "number": str(index + 1)}
        for index in range(12)
    }
    snapshot = TelemetrySnapshot(
        lap=20,
        total_laps=60,
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
    engine.session_tracker.update("Race")
    engine.race_director.race_started = True
    engine.race_director.phase = RacePhase.CAUTION
    engine.race_director.previous_phase = RacePhase.CAUTION
    engine.race_intelligence.race_state_tracker.initialized = True

    green = engine.tick(SnapshotSource(snapshot))

    assert green.category == "race_control"
    assert "Green flag" in green.message

    engine.broadcast_queue.busy_until = 0
    rundown = engine.tick(SnapshotSource(snapshot))

    assert rundown.category == "long_green_field_rundown_1"


def test_engine_joining_mid_race_queues_in_progress_opening_without_green_flag():
    results = [
        {"CarIdx": index, "Position": index, "LapsComplete": 12}
        for index in range(8)
    ]
    drivers = {
        index: {"name": f"Driver {index + 1}", "number": str(index + 1)}
        for index in range(8)
    }
    snapshot = TelemetrySnapshot(
        lap=12,
        total_laps=50,
        session_flags=RaceFlags.GREEN,
        results=results,
        driver_lookup=drivers,
        pit_road_status=[False] * 8,
        track_surface=[3] * 8,
        track_surface_material=[0] * 8,
        lap_dist_pct=[0.1] * 8,
        est_time=[10.0] * 8,
        track_info={"track_name": "Talladega Superspeedway"},
    )
    engine = BroadcastEngine(openai_director=SilentOpenAI())

    first = engine.tick(SnapshotSource(snapshot))

    assert first.category == "mid_race_join"
    assert "already in progress" in first.message
    assert "lap 12 of 50" in first.message
    assert not any("Green flag is in the air" in item.message for item in engine.broadcast_queue.items)
    assert engine.joined_mid_race is True


def test_mid_race_join_does_not_count_unobserved_laps_as_long_green_run():
    results = [
        {"CarIdx": index, "Position": index, "LapsComplete": 20}
        for index in range(12)
    ]
    drivers = {
        index: {"name": f"Driver {index + 1}", "number": str(index + 1)}
        for index in range(12)
    }
    snapshot = TelemetrySnapshot(
        lap=20,
        total_laps=60,
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

    engine.tick(SnapshotSource(snapshot))
    engine.broadcast_queue.busy_until = 0
    second = engine.tick(SnapshotSource(snapshot))

    assert second is None or second.category != "long_green_field_rundown_1"
    assert engine.race_intelligence.get_race_state().green_lap_count == 0


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


def test_engine_queues_quiet_green_race_stat_filler_with_camera_target():
    engine = BroadcastEngine(openai_director=SilentOpenAI())
    state = RaceState(
        current_lap=12,
        total_laps=80,
        laps_remaining=68,
        green_lap_count=8,
        is_green=True,
    )
    drivers = {
        1: {"name": "Austin Peterson", "number": "77"},
        2: {"name": "Dean Marsh", "number": "24"},
        3: {"name": "Eric Hudec", "number": "14"},
    }
    results = [
        {"CarIdx": 1, "Position": 0, "Time": 0.0},
        {"CarIdx": 2, "Position": 1, "Time": 0.3},
        {"CarIdx": 3, "Position": 2, "Time": 2.0},
    ]

    queued = engine._queue_race_stat_filler(
        results,
        drivers,
        state,
        current_lap=12,
    )

    assert queued is True
    assert engine.broadcast_queue.items[0].category.startswith("race_stat:")
    assert engine.broadcast_queue.items[0].camera_target_car_idx == 2


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
    assert incident_items[0].camera_target_car_idx is None
    assert incident_items[0].replay_use_incident_marker is True
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
    assert incident.replay_session_time == 35.0


def test_caution_candidate_prefers_iracing_incident_marker_over_guessed_car():
    drivers = {0: {"name": "Driver One", "number": "1"}}
    snapshot = TelemetrySnapshot(
        lap=3,
        total_laps=20,
        session_flags=RaceFlags.CAUTION,
        session_num=2,
        session_time=90.0,
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
    engine = BroadcastEngine(openai_director=SilentOpenAI())
    engine.race_director.phase = RacePhase.CAUTION
    engine.race_director.previous_phase = RacePhase.GREEN
    engine.race_director.phase_changed = True
    engine.incident_detector.analyze = lambda **_: []
    engine.incident_detector.build_caution_fallback = lambda current_lap: SimpleNamespace(
        car_idx=0,
        trouble_type="caution candidate",
        incident_delta=0,
        message="Wrong guessed car caused the caution.",
        importance=9,
        lap=current_lap,
        total_incidents=0,
    )

    engine._collect_incidents(
        telemetry=SnapshotSource(snapshot),
        results=snapshot.results,
        driver_lookup=drivers,
        pit_road_status=snapshot.pit_road_status,
        current_lap=3,
    )

    incident = next(
        item for item in engine.broadcast_queue.items if item.category == "incident"
    )
    assert incident.replay_use_incident_marker is True
    assert incident.camera_target_car_idx is None
    assert incident.replay_session_time == 90.0
    assert "Wrong guessed car" not in incident.message


def test_final_lap_pack_wreck_is_called_live_without_replay():
    drivers = {
        index: {"name": f"Driver {index + 1}", "number": str(index + 1)}
        for index in range(5)
    }
    first = TelemetrySnapshot(
        lap=49,
        total_laps=50,
        session_flags=RaceFlags.GREEN,
        session_num=2,
        session_time=490.0,
        results=[
            {"CarIdx": index, "Position": index + 1, "LapsComplete": 49, "Incidents": 0}
            for index in range(5)
        ],
        driver_lookup=drivers,
        pit_road_status=[False] * 5,
        track_surface=[3] * 5,
        track_surface_material=[0] * 5,
        lap_dist_pct=[0.50, 0.51, 0.52, 0.53, 0.54],
        est_time=[20.0, 20.2, 20.4, 20.6, 20.8],
    )
    wreck = TelemetrySnapshot(
        lap=49,
        total_laps=50,
        session_flags=RaceFlags.GREEN,
        session_num=2,
        session_time=492.0,
        results=[
            {"CarIdx": 0, "Position": 8, "LapsComplete": 49, "Incidents": 0},
            {"CarIdx": 1, "Position": 9, "LapsComplete": 49, "Incidents": 0},
            {"CarIdx": 2, "Position": 10, "LapsComplete": 49, "Incidents": 0},
            {"CarIdx": 3, "Position": 11, "LapsComplete": 49, "Incidents": 0},
            {"CarIdx": 4, "Position": 5, "LapsComplete": 49, "Incidents": 0},
        ],
        driver_lookup=drivers,
        pit_road_status=[False] * 5,
        track_surface=[3] * 5,
        track_surface_material=[0] * 5,
        lap_dist_pct=[0.49, 0.50, 0.51, 0.52, 0.54],
        est_time=[22.0, 22.2, 22.4, 22.6, 20.8],
    )
    engine = BroadcastEngine(openai_director=SilentOpenAI())
    engine.race_director.phase = RacePhase.GREEN
    engine.race_director.previous_phase = RacePhase.GREEN

    engine._collect_incidents(
        telemetry=SnapshotSource(first),
        results=first.results,
        driver_lookup=drivers,
        pit_road_status=first.pit_road_status,
        current_lap=49,
        total_laps=50,
    )
    engine._collect_incidents(
        telemetry=SnapshotSource(wreck),
        results=wreck.results,
        driver_lookup=drivers,
        pit_road_status=wreck.pit_road_status,
        current_lap=49,
        total_laps=50,
    )

    incident = next(
        item for item in engine.broadcast_queue.items if item.category == "incident"
    )
    assert "final lap" in incident.message
    assert "race back to the checkered flag" in incident.message
    assert incident.replay_session_num is None
    assert incident.replay_session_time is None
    assert incident.replay_use_incident_marker is False
    assert incident.camera_focus_incident is False
    assert incident.camera_target_car_idx is None


def test_green_flag_possible_trouble_moves_camera_to_car():
    drivers = {2: {"name": "Trouble Driver", "number": "27"}}
    first = TelemetrySnapshot(
        lap=18,
        total_laps=50,
        session_flags=RaceFlags.GREEN,
        session_num=2,
        session_time=180.0,
        results=[{"CarIdx": 2, "Position": 3, "LapsComplete": 18, "Incidents": 0}],
        driver_lookup=drivers,
        pit_road_status=[False, False, False],
        track_surface=[3, 3, 3],
        track_surface_material=[0, 0, 0],
        lap_dist_pct=[0.0, 0.0, 0.70],
        est_time=[0.0, 0.0, 20.0],
    )
    trouble = TelemetrySnapshot(
        lap=18,
        total_laps=50,
        session_flags=RaceFlags.GREEN,
        session_num=2,
        session_time=183.0,
        results=[{"CarIdx": 2, "Position": 8, "LapsComplete": 18, "Incidents": 0}],
        driver_lookup=drivers,
        pit_road_status=[False, False, False],
        track_surface=[3, 3, 0],
        track_surface_material=[0, 0, 0],
        lap_dist_pct=[0.0, 0.0, 0.67],
        est_time=[0.0, 0.0, 24.0],
    )
    engine = BroadcastEngine(openai_director=SilentOpenAI())
    engine.race_director.phase = RacePhase.GREEN
    engine.race_director.previous_phase = RacePhase.GREEN

    engine._collect_incidents(
        telemetry=SnapshotSource(first),
        results=first.results,
        driver_lookup=drivers,
        pit_road_status=first.pit_road_status,
        current_lap=18,
        total_laps=50,
    )
    engine._collect_incidents(
        telemetry=SnapshotSource(trouble),
        results=trouble.results,
        driver_lookup=drivers,
        pit_road_status=trouble.pit_road_status,
        current_lap=18,
        total_laps=50,
    )

    incident = next(
        item for item in engine.broadcast_queue.items if item.category == "incident"
    )
    assert "may have had a moment" in incident.message
    assert incident.camera_target_car_idx == 2
    assert incident.camera_focus_incident is False
    assert incident.protected is False
    assert incident.priority == 4
    assert incident.delay_seconds == 2.0


def test_green_flag_soft_incident_does_not_clear_current_broadcast():
    drivers = {2: {"name": "Trouble Driver", "number": "27"}}
    first = TelemetrySnapshot(
        lap=18,
        total_laps=50,
        session_flags=RaceFlags.GREEN,
        session_num=2,
        session_time=180.0,
        results=[{"CarIdx": 2, "Position": 3, "LapsComplete": 18, "Incidents": 0}],
        driver_lookup=drivers,
        pit_road_status=[False, False, False],
        track_surface=[3, 3, 3],
        track_surface_material=[0, 0, 0],
        lap_dist_pct=[0.0, 0.0, 0.70],
        est_time=[0.0, 0.0, 20.0],
    )
    trouble = TelemetrySnapshot(
        lap=18,
        total_laps=50,
        session_flags=RaceFlags.GREEN,
        session_num=2,
        session_time=183.0,
        results=[{"CarIdx": 2, "Position": 8, "LapsComplete": 18, "Incidents": 0}],
        driver_lookup=drivers,
        pit_road_status=[False, False, False],
        track_surface=[3, 3, 0],
        track_surface_material=[0, 0, 0],
        lap_dist_pct=[0.0, 0.0, 0.67],
        est_time=[0.0, 0.0, 24.0],
    )
    engine = BroadcastEngine(openai_director=SilentOpenAI())
    engine.race_director.phase = RacePhase.GREEN
    engine.race_director.previous_phase = RacePhase.GREEN
    engine.broadcast_queue.add(
        "The leader is working through traffic.",
        category="race_story",
        dedupe_key="story:leader",
    )

    engine._collect_incidents(
        telemetry=SnapshotSource(first),
        results=first.results,
        driver_lookup=drivers,
        pit_road_status=first.pit_road_status,
        current_lap=18,
        total_laps=50,
    )
    engine._collect_incidents(
        telemetry=SnapshotSource(trouble),
        results=trouble.results,
        driver_lookup=drivers,
        pit_road_status=trouble.pit_road_status,
        current_lap=18,
        total_laps=50,
    )

    categories = [item.category for item in engine.broadcast_queue.items]
    assert "race_story" in categories
    assert "incident" in categories


def test_pack_wreck_detector_stays_quiet_while_field_forms_under_caution():
    drivers = {
        index: {"name": f"Driver {index + 1}", "number": str(index + 1)}
        for index in range(5)
    }
    first = TelemetrySnapshot(
        lap=20,
        total_laps=50,
        session_flags=RaceFlags.CAUTION,
        session_num=2,
        session_time=200.0,
        results=[
            {"CarIdx": index, "Position": index + 1, "LapsComplete": 20, "Incidents": 0}
            for index in range(5)
        ],
        driver_lookup=drivers,
        pit_road_status=[False] * 5,
        track_surface=[3] * 5,
        track_surface_material=[0] * 5,
        lap_dist_pct=[0.50, 0.51, 0.52, 0.53, 0.54],
        est_time=[20.0, 20.2, 20.4, 20.6, 20.8],
    )
    shuffled = TelemetrySnapshot(
        lap=20,
        total_laps=50,
        session_flags=RaceFlags.CAUTION,
        session_num=2,
        session_time=202.0,
        results=[
            {"CarIdx": 0, "Position": 8, "LapsComplete": 20, "Incidents": 0},
            {"CarIdx": 1, "Position": 9, "LapsComplete": 20, "Incidents": 0},
            {"CarIdx": 2, "Position": 10, "LapsComplete": 20, "Incidents": 0},
            {"CarIdx": 3, "Position": 11, "LapsComplete": 20, "Incidents": 0},
            {"CarIdx": 4, "Position": 5, "LapsComplete": 20, "Incidents": 0},
        ],
        driver_lookup=drivers,
        pit_road_status=[False] * 5,
        track_surface=[0, 0, 0, 0, 3],
        track_surface_material=[0] * 5,
        lap_dist_pct=[0.49, 0.50, 0.51, 0.52, 0.54],
        est_time=[22.0, 22.2, 22.4, 22.6, 20.8],
    )
    engine = BroadcastEngine(openai_director=SilentOpenAI())
    engine.race_director.phase = RacePhase.CAUTION
    engine.race_director.previous_phase = RacePhase.CAUTION
    engine.race_director.phase_changed = False

    engine._collect_incidents(
        telemetry=SnapshotSource(first),
        results=first.results,
        driver_lookup=drivers,
        pit_road_status=first.pit_road_status,
        current_lap=20,
        total_laps=50,
    )
    engine._collect_incidents(
        telemetry=SnapshotSource(shuffled),
        results=shuffled.results,
        driver_lookup=drivers,
        pit_road_status=shuffled.pit_road_status,
        current_lap=20,
        total_laps=50,
    )

    assert not any(item.category == "incident" for item in engine.broadcast_queue.items)


def test_high_confidence_caution_candidate_anchors_replay_to_car_and_time():
    drivers = {0: {"name": "Driver One", "number": "1"}}
    source = SnapshotSource(
        TelemetrySnapshot(
            lap=5,
            total_laps=20,
            session_flags=RaceFlags.GREEN,
            session_num=2,
            session_time=120.0,
            results=[
                {"CarIdx": 0, "Position": 1, "LapsComplete": 5, "Incidents": 0}
            ],
            driver_lookup=drivers,
            pit_road_status=[False],
            track_surface=[3],
            track_surface_material=[0],
            lap_dist_pct=[0.50],
            est_time=[10.0],
        )
    )
    engine = BroadcastEngine(openai_director=SilentOpenAI())
    engine.tick(source)
    source.snapshot = TelemetrySnapshot(
        lap=5,
        total_laps=20,
        session_flags=RaceFlags.CAUTION,
        session_num=2,
        session_time=125.0,
        results=[
            {"CarIdx": 0, "Position": 5, "LapsComplete": 5, "Incidents": 0}
        ],
        driver_lookup=drivers,
        pit_road_status=[False],
        track_surface=[0],
        track_surface_material=[0],
        lap_dist_pct=[0.46],
        est_time=[15.0],
    )

    engine.tick(source)

    incident = next(
        item for item in engine.broadcast_queue.items if item.category == "incident"
    )
    assert incident.replay_use_incident_marker is True
    assert incident.camera_target_car_idx is None
    assert incident.replay_session_time == 125.0
    assert incident.replay_multi_angle is True


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

    assert emitted is None
    incident = next(
        item for item in engine.broadcast_queue.items if item.category == "incident"
    )
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
    engine._collect_pit_stories(
        results=results,
        driver_lookup=drivers,
        pit_road_status=[False, False, False, False, False, False],
        current_lap=6,
    )
    engine._collect_pit_stories(
        results=results,
        driver_lookup=drivers,
        pit_road_status=[False, False, False, False, False, False],
        current_lap=6,
    )
    engine._collect_pit_stories(
        results=results,
        driver_lookup=drivers,
        pit_road_status=[False, False, False, False, False, False],
        current_lap=6,
    )
    engine._collect_pit_stories(
        results=results,
        driver_lookup=drivers,
        pit_road_status=[False, False, False, False, False, False],
        current_lap=6,
    )
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
    top_ten = next(
        item for item in engine.broadcast_queue.items
        if item.category == "caution_top_ten_reset"
    )
    assert "Before this restart, here is the top ten" in top_ten.message
    assert "first, the 1 of Driver 1" in top_ten.message
    assert "second, the 2 of Driver 2" in top_ten.message
    assert top_ten.delay_seconds == 1.5


def test_one_to_green_top_ten_reset_only_queues_once_per_caution():
    engine = BroadcastEngine(openai_director=SilentOpenAI())
    results = [
        {"CarIdx": index, "Position": index}
        for index in range(10)
    ]
    drivers = {
        index: {"name": f"Driver {index + 1}", "number": str(index + 1)}
        for index in range(10)
    }
    engine.race_director.phase = RacePhase.ONE_TO_GREEN

    for lap in (20, 21, 22, 23, 24, 25, 26):
        engine._collect_pit_stories(results, drivers, [False] * 10, current_lap=lap)

    resets = [
        item for item in engine.broadcast_queue.items
        if item.category == "caution_top_ten_reset"
    ]
    assert len(resets) == 1


def test_one_to_green_skips_top_ten_reset_on_short_tracks():
    engine = BroadcastEngine(openai_director=SilentOpenAI())
    results = [
        {"CarIdx": index, "Position": index}
        for index in range(10)
    ]
    drivers = {
        index: {"name": f"Driver {index + 1}", "number": str(index + 1)}
        for index in range(10)
    }
    engine.race_director.phase = RacePhase.ONE_TO_GREEN

    for lap in (20, 21, 22, 23, 24, 25, 26):
        engine._collect_pit_stories(
            results,
            drivers,
            [False] * 10,
            current_lap=lap,
            track_info={
                "track_name": "Martinsville Speedway",
                "track_type": "oval",
                "track_length": "0.53 mi",
            },
        )

    assert not any(
        item.category == "caution_top_ten_reset"
        for item in engine.broadcast_queue.items
    )


def test_one_to_green_top_ten_waits_for_stable_running_order():
    engine = BroadcastEngine(openai_director=SilentOpenAI())
    drivers = {
        index: {"name": f"Driver {index + 1}", "number": str(index + 1)}
        for index in range(10)
    }
    first_order = [
        {"CarIdx": index, "Position": index}
        for index in range(10)
    ]
    settled_order = [
        {"CarIdx": car_idx, "Position": position}
        for position, car_idx in enumerate([0, 2, 1, 3, 4, 5, 6, 7, 8, 9])
    ]
    engine.race_director.phase = RacePhase.ONE_TO_GREEN

    engine._collect_pit_stories(first_order, drivers, [False] * 10, current_lap=20)
    engine._collect_pit_stories(settled_order, drivers, [False] * 10, current_lap=20)
    engine._collect_pit_stories(settled_order, drivers, [False] * 10, current_lap=20)

    assert not any(
        item.category == "caution_top_ten_reset"
        for item in engine.broadcast_queue.items
    )

    for _ in range(4):
        engine._collect_pit_stories(
            settled_order,
            drivers,
            [False] * 10,
            current_lap=20,
        )

    reset = next(
        item for item in engine.broadcast_queue.items
        if item.category == "caution_top_ten_reset"
    )
    assert "second, the 3 of Driver 3" in reset.message
    assert "third, the 2 of Driver 2" in reset.message


def test_one_to_green_majority_pit_report_waits_for_full_caution_cycle():
    engine = BroadcastEngine(openai_director=SilentOpenAI())
    results = [
        {"CarIdx": index, "Position": index}
        for index in range(20)
    ]
    drivers = {
        index: {"name": f"Driver {index + 1}", "number": str(index + 1)}
        for index in range(20)
    }
    engine.race_director.phase = RacePhase.CAUTION
    engine._collect_pit_stories(
        results=results,
        driver_lookup=drivers,
        pit_road_status=[index < 15 for index in range(20)],
        current_lap=5,
    )

    assert [
        item for item in engine.broadcast_queue.items
        if item.dedupe_key.startswith("caution_pit_wave")
    ] == []

    engine._collect_pit_stories(
        results=results,
        driver_lookup=drivers,
        pit_road_status=[index < 18 for index in range(20)],
        current_lap=6,
    )
    engine.race_director.phase = RacePhase.ONE_TO_GREEN
    engine._collect_pit_stories(
        results=results,
        driver_lookup=drivers,
        pit_road_status=[False] * 20,
        current_lap=7,
    )

    pit_item = next(
        item for item in engine.broadcast_queue.items
        if item.dedupe_key.startswith("caution_pit_wave")
    )
    assert "18 of 20 cars" in pit_item.message
    assert pit_item.speaker == "sarah"


def test_one_to_green_does_not_call_lucky_dog_candidate_for_now():
    engine = BroadcastEngine(openai_director=SilentOpenAI())
    results = [
        {"CarIdx": 0, "Position": 0, "LapsComplete": 20},
        {"CarIdx": 1, "Position": 1, "LapsComplete": 19},
        {"CarIdx": 2, "Position": 2, "LapsComplete": 19},
    ]
    drivers = {
        0: {"name": "Leader", "number": "1"},
        1: {"name": "Lucky Driver", "number": "7"},
        2: {"name": "Other Driver", "number": "8"},
    }
    engine.race_director.phase = RacePhase.ONE_TO_GREEN

    engine._collect_pit_stories(
        results=results,
        driver_lookup=drivers,
        pit_road_status=[False] * 3,
        current_lap=20,
    )

    assert not any(item.category == "lucky_dog" for item in engine.broadcast_queue.items)


def test_late_caution_note_mentions_green_white_checkered():
    engine = BroadcastEngine(openai_director=SilentOpenAI())

    engine._queue_late_caution_note(current_lap=49, total_laps=50)

    item = next(
        item for item in engine.broadcast_queue.items
        if item.category == "late_caution_note"
    )
    assert "green-white-checkered" in item.message


def test_restart_caution_marker_replay_uses_extra_preroll():
    engine = BroadcastEngine(openai_director=SilentOpenAI())

    assert engine.restart_caution_marker_pre_roll_frames(0) == 1500
    assert engine.restart_caution_marker_pre_roll_frames(2) == 1500
    assert engine.restart_caution_marker_pre_roll_frames(3) == 1500


def test_caution_marker_replay_uses_saved_caution_start_time():
    engine = BroadcastEngine(openai_director=SilentOpenAI())
    caution_start = SnapshotSource(
        TelemetrySnapshot(
            session_num=2,
            session_time=100.0,
        )
    )
    later_under_caution = SnapshotSource(
        TelemetrySnapshot(
            session_num=2,
            session_time=140.0,
        )
    )
    engine.race_director.phase_changed = True
    engine.race_director.phase = RacePhase.CAUTION

    engine._handle_caution_phase_change(caution_start)
    engine.queue_incident_marker_replay(
        results=[],
        telemetry=later_under_caution,
        current_lap=12,
        green_lap_count=5,
        reason="test",
    )

    item = engine.broadcast_queue.items[0]
    assert item.replay_session_num == 2
    assert item.replay_session_time == 100.0


def test_leader_story_uses_total_laps_led_and_tight_margin_language():
    engine = BroadcastEngine(openai_director=SilentOpenAI())
    drivers = {
        0: {"name": "Race Leader", "number": "77"},
        1: {"name": "Chaser", "number": "24"},
    }
    results = [
        {"CarIdx": 0, "Position": 0, "Time": 0.0},
        {"CarIdx": 1, "Position": 1, "Time": 0.2},
    ]

    for lap in (1, 2, 3):
        engine._update_leader_laps_led(results, lap)

    engine._queue_leader_story(results, drivers, current_lap=3, total_laps=50)

    item = engine.broadcast_queue.items[0]
    assert "has led 3 laps tonight" in item.message
    assert "tight battle at the front" in item.message
    assert "0.2 seconds" not in item.message


def test_leader_story_uses_singular_lap_word():
    engine = BroadcastEngine(openai_director=SilentOpenAI())
    drivers = {
        0: {"name": "Race Leader", "number": "77"},
        1: {"name": "Chaser", "number": "24"},
    }
    results = [
        {"CarIdx": 0, "Position": 0, "Time": 0.0},
        {"CarIdx": 1, "Position": 1, "Time": 1.2},
    ]

    engine._update_leader_laps_led(results, 3)
    engine._queue_leader_story(results, drivers, current_lap=3, total_laps=50)

    assert "has led 1 lap tonight" in engine.broadcast_queue.items[0].message
    assert "1 laps" not in engine.broadcast_queue.items[0].message


def test_green_phase_change_clears_stale_editorial_stories():
    engine = BroadcastEngine(openai_director=SilentOpenAI())
    engine.editorial_producer.submit_story(
        "battle_for_top_five",
        "Old battle",
        "This was collected before the restart.",
        priority=8,
    )
    engine.race_director.phase_changed = True
    engine.race_director.phase = RacePhase.GREEN

    engine._handle_green_phase_change()

    assert engine.editorial_producer.items == []


def test_restart_launch_story_describes_leader_gap():
    engine = BroadcastEngine(openai_director=SilentOpenAI())
    engine.race_director.previous_phase = RacePhase.ONE_TO_GREEN
    drivers = {
        34: {"name": "T.J. Lee", "number": "34"},
        12: {"name": "Second Place", "number": "12"},
    }
    results = [
        {"CarIdx": 34, "Position": 0, "Time": 0.0},
        {"CarIdx": 12, "Position": 1, "Time": 0.4},
    ]

    queued = engine._queue_restart_launch_story(
        results,
        drivers,
        green_lap_count=1,
    )

    assert queued is True
    item = engine.broadcast_queue.items[0]
    assert item.category == "restart_launch"
    assert "Good start" in item.message
    assert "34" in item.message
    assert item.camera_target_car_idx == 34


def test_restart_launch_story_can_queue_behind_green_flag_call():
    engine = BroadcastEngine(openai_director=SilentOpenAI())
    engine.race_director.previous_phase = RacePhase.ONE_TO_GREEN
    engine.broadcast_queue.add(
        "Green flag is back in the air!",
        priority=12,
        category="race_control",
        protected=True,
        dedupe_key="race_control:green:ONE_TO_GREEN",
    )
    drivers = {
        34: {"name": "T.J. Lee", "number": "34"},
        12: {"name": "Second Place", "number": "12"},
    }
    results = [
        {"CarIdx": 34, "Position": 0, "Time": 0.0},
        {"CarIdx": 12, "Position": 1, "Time": 0.4},
    ]

    queued = engine._queue_restart_launch_story(
        results,
        drivers,
        green_lap_count=1,
    )

    assert queued is True
    assert [item.category for item in engine.broadcast_queue.items] == [
        "race_control",
        "restart_launch",
    ]


def test_restart_launch_story_can_call_tight_lead():
    engine = BroadcastEngine(openai_director=SilentOpenAI())
    engine.race_director.previous_phase = RacePhase.ONE_TO_GREEN
    drivers = {
        34: {"name": "T.J. Lee", "number": "34"},
        12: {"name": "Second Place", "number": "12"},
    }
    results = [
        {"CarIdx": 34, "Position": 0, "Time": 0.0},
        {"CarIdx": 12, "Position": 1, "Time": 0.05},
    ]

    engine._queue_restart_launch_story(results, drivers, green_lap_count=1)

    assert "tight launch" in engine.broadcast_queue.items[0].message


def test_engine_queues_pit_speeding_black_flag_story():
    engine = BroadcastEngine(openai_director=SilentOpenAI())
    drivers = {4: {"name": "Fast Driver", "number": "44"}}
    initial = TelemetrySnapshot(
        lap=4,
        total_laps=40,
        session_flags=RaceFlags.GREEN,
        results=[{"CarIdx": 4, "Position": 1, "LapsComplete": 4}],
        driver_lookup=drivers,
        pit_road_status=[False] * 5,
        track_surface=[3] * 5,
        track_surface_material=[0] * 5,
        lap_dist_pct=[0.0] * 5,
        est_time=[0.0] * 5,
        car_idx_session_flags=[0] * 5,
        car_idx_penalty_reasons=[""] * 5,
    )
    source = SnapshotSource(initial)
    engine.tick(source)
    source.snapshot = TelemetrySnapshot(
        lap=5,
        total_laps=40,
        session_flags=RaceFlags.GREEN,
        results=[{"CarIdx": 4, "Position": 1, "LapsComplete": 5}],
        driver_lookup=drivers,
        pit_road_status=[False] * 5,
        track_surface=[3] * 5,
        track_surface_material=[0] * 5,
        lap_dist_pct=[0.0] * 5,
        est_time=[0.0] * 5,
        car_idx_session_flags=[0, 0, 0, 0, PenaltyDetector.BLACK_FLAG],
        car_idx_penalty_reasons=["", "", "", "", "Speeding on pit road"],
    )

    engine.tick(source)

    item = next(item for item in engine.broadcast_queue.items if item.category == "penalty")
    assert "speeding on pit road" in item.message
    assert item.camera_target_car_idx == 4


def test_engine_ignores_generic_black_flag_without_reason():
    engine = BroadcastEngine(openai_director=SilentOpenAI())
    drivers = {4: {"name": "Quiet Driver", "number": "44"}}
    initial = TelemetrySnapshot(
        lap=4,
        total_laps=40,
        session_flags=RaceFlags.GREEN,
        results=[{"CarIdx": 4, "Position": 1, "LapsComplete": 4}],
        driver_lookup=drivers,
        pit_road_status=[False] * 5,
        track_surface=[3] * 5,
        track_surface_material=[0] * 5,
        lap_dist_pct=[0.0] * 5,
        est_time=[0.0] * 5,
        car_idx_session_flags=[0] * 5,
    )
    source = SnapshotSource(initial)
    engine.tick(source)
    source.snapshot.car_idx_session_flags = [0, 0, 0, 0, PenaltyDetector.BLACK_FLAG]

    engine.tick(source)

    assert not any(item.category == "penalty" for item in engine.broadcast_queue.items)


def test_meatball_flag_waits_when_caution_replay_is_pending():
    engine = BroadcastEngine(openai_director=SilentOpenAI())
    engine.race_director.phase = RacePhase.CAUTION
    drivers = {4: {"name": "Damaged Driver", "number": "44"}}
    snapshot = TelemetrySnapshot(
        lap=10,
        total_laps=40,
        session_flags=RaceFlags.CAUTION,
        results=[{"CarIdx": 4, "Position": 1, "LapsComplete": 10}],
        driver_lookup=drivers,
        pit_road_status=[False] * 5,
        track_surface=[3] * 5,
        track_surface_material=[0] * 5,
        lap_dist_pct=[0.0] * 5,
        est_time=[0.0] * 5,
        car_idx_session_flags=[0, 0, 0, 0, PenaltyDetector.REPAIR_FLAG],
        car_idx_penalty_reasons=[""] * 5,
    )
    engine.broadcast_queue.add(
        "We are going to take a look at what brought out this caution.",
        priority=10,
        category="incident",
        protected=True,
        replay_use_incident_marker=True,
    )

    engine._collect_penalty_stories(
        telemetry=SnapshotSource(snapshot),
        results=snapshot.results,
        driver_lookup=drivers,
        current_lap=10,
        total_laps=40,
    )

    item = next(item for item in engine.broadcast_queue.items if item.category == "penalty")
    assert "required damage repairs" in item.message
    assert "meatball flag" not in item.message.lower()
    assert item.delay_seconds >= 35
    assert item.protected is False


def test_multiple_meatball_flags_are_grouped_into_one_story():
    engine = BroadcastEngine(openai_director=SilentOpenAI())
    drivers = {
        4: {"name": "Damaged Driver", "number": "44"},
        7: {"name": "Second Damaged", "number": "77"},
    }
    snapshot = TelemetrySnapshot(
        lap=12,
        total_laps=40,
        session_flags=RaceFlags.GREEN,
        results=[
            {"CarIdx": 4, "Position": 1, "LapsComplete": 12},
            {"CarIdx": 7, "Position": 2, "LapsComplete": 12},
        ],
        driver_lookup=drivers,
        pit_road_status=[False] * 8,
        track_surface=[3] * 8,
        track_surface_material=[0] * 8,
        lap_dist_pct=[0.0] * 8,
        est_time=[0.0] * 8,
        car_idx_session_flags=[
            0,
            0,
            0,
            0,
            PenaltyDetector.REPAIR_FLAG,
            0,
            0,
            PenaltyDetector.REPAIR_FLAG,
        ],
        car_idx_penalty_reasons=[""] * 8,
    )

    engine._collect_penalty_stories(
        telemetry=SnapshotSource(snapshot),
        results=snapshot.results,
        driver_lookup=drivers,
        current_lap=12,
        total_laps=40,
    )

    penalty_items = [
        item for item in engine.broadcast_queue.items if item.category == "penalty"
    ]
    assert len(penalty_items) == 1
    assert "required damage repairs" in penalty_items[0].message
    assert "Meatball flags" not in penalty_items[0].message
    assert "Damaged Driver" in penalty_items[0].message
    assert "Second Damaged" in penalty_items[0].message
    assert "ending early" in penalty_items[0].message
    assert penalty_items[0].participant_car_indices == (4, 7)


def test_penalty_stories_do_not_air_with_two_or_less_to_go():
    engine = BroadcastEngine(openai_director=SilentOpenAI())
    drivers = {4: {"name": "Damaged Driver", "number": "44"}}
    snapshot = TelemetrySnapshot(
        lap=38,
        total_laps=40,
        session_flags=RaceFlags.GREEN,
        results=[{"CarIdx": 4, "Position": 1, "LapsComplete": 38}],
        driver_lookup=drivers,
        pit_road_status=[False] * 5,
        track_surface=[3] * 5,
        track_surface_material=[0] * 5,
        lap_dist_pct=[0.0] * 5,
        est_time=[0.0] * 5,
        car_idx_session_flags=[0, 0, 0, 0, PenaltyDetector.REPAIR_FLAG],
        car_idx_penalty_reasons=[""] * 5,
    )

    engine._collect_penalty_stories(
        telemetry=SnapshotSource(snapshot),
        results=snapshot.results,
        driver_lookup=drivers,
        current_lap=38,
        total_laps=40,
    )

    assert [item for item in engine.broadcast_queue.items if item.category == "penalty"] == []


def test_final_laps_battle_prioritizes_closest_top_five_gap():
    engine = BroadcastEngine(openai_director=SilentOpenAI())
    results = [
        {"CarIdx": 0, "Position": 0, "Time": 0.0},
        {"CarIdx": 1, "Position": 1, "Time": 2.3},
        {"CarIdx": 2, "Position": 2, "Time": 2.6},
        {"CarIdx": 3, "Position": 3, "Time": 4.0},
        {"CarIdx": 4, "Position": 4, "Time": 5.0},
    ]
    drivers = {
        index: {"name": f"Driver {index + 1}", "number": str(index + 1)}
        for index in range(5)
    }

    queued = engine._queue_final_laps_battle(
        results,
        drivers,
        current_lap=48,
        total_laps=50,
    )

    item = engine.broadcast_queue.items[0]
    assert queued is True
    assert item.category == "final_laps_battle"
    assert item.camera_target_car_idx == 2
    assert "for 3rd" in item.message
    assert "0.3 seconds" in item.message
    assert "comfortable lead" in item.message


def test_final_laps_focuses_leader_when_win_is_close():
    engine = BroadcastEngine(openai_director=SilentOpenAI())
    results = [
        {"CarIdx": 0, "Position": 0, "Time": 0.0},
        {"CarIdx": 1, "Position": 1, "Time": 0.6},
        {"CarIdx": 2, "Position": 2, "Time": 0.9},
    ]
    drivers = {
        0: {"name": "Race Leader", "number": "77"},
        1: {"name": "Chaser", "number": "24"},
        2: {"name": "Third Place", "number": "3"},
    }
    for lap in (46, 47, 48):
        engine._update_leader_laps_led(results, lap)

    queued = engine._queue_final_laps_battle(
        results,
        drivers,
        current_lap=48,
        total_laps=50,
    )

    item = engine.broadcast_queue.items[0]
    assert queued is True
    assert item.category == "final_laps_battle"
    assert item.camera_target_car_idx == 0
    assert "Race Leader" in item.message
    assert "trying to close this out" in item.message
    assert "has led 3 laps" in item.message


def test_final_lap_clears_stale_story_and_keeps_white_flag_first():
    engine = BroadcastEngine(openai_director=SilentOpenAI())
    results = [
        {"CarIdx": 0, "Position": 0, "Time": 0.0},
        {"CarIdx": 1, "Position": 1, "Time": 0.4},
    ]
    drivers = {
        0: {"name": "Race Leader", "number": "77"},
        1: {"name": "Chaser", "number": "24"},
    }
    engine._update_leader_laps_led(results, 48)
    engine._update_leader_laps_led(results, 49)
    engine.broadcast_queue.add(
        "A stale mid-pack Jeff story that should not run on the last lap.",
        priority=11,
        category="race_story",
        protected=True,
        speaker="jeff",
        dedupe_key="stale_story",
    )
    engine.broadcast_queue.add(
        "White flag. One lap to go.",
        priority=13,
        category="race_control",
        protected=True,
        speaker="lead",
        dedupe_key="race_control:white_flag",
    )

    engine.prepare_final_lap_finish(
        results,
        drivers,
        current_lap=49,
        total_laps=50,
    )

    categories = [item.category for item in engine.broadcast_queue.items]
    assert "race_story" not in categories
    assert "race_control" in categories
    assert "final_lap_finish_focus" in categories

    first = engine.broadcast_queue.next_item(now=time.time())
    assert first.dedupe_key == "race_control:white_flag"


def test_final_lap_finish_focus_can_run_even_after_five_to_go_story():
    engine = BroadcastEngine(openai_director=SilentOpenAI())
    engine.final_laps_battle_queued = True
    results = [
        {"CarIdx": 0, "Position": 0, "Time": 0.0},
        {"CarIdx": 1, "Position": 1, "Time": 1.8},
    ]
    drivers = {
        0: {"name": "Race Leader", "number": "77"},
        1: {"name": "Second Place", "number": "24"},
    }

    queued = engine._queue_final_lap_finish_focus(
        results,
        drivers,
        current_lap=49,
        total_laps=50,
    )

    assert queued is True
    item = engine.broadcast_queue.items[0]
    assert item.category == "final_lap_finish_focus"
    assert item.camera_target_car_idx == 0
    assert "Final lap for Race Leader" in item.message


def test_final_laps_can_show_best_battle_outside_top_five_when_leader_checked_out():
    engine = BroadcastEngine(openai_director=SilentOpenAI())
    results = [
        {"CarIdx": 0, "Position": 0, "Time": 0.0},
        {"CarIdx": 1, "Position": 1, "Time": 2.4},
        {"CarIdx": 2, "Position": 2, "Time": 4.0},
        {"CarIdx": 3, "Position": 3, "Time": 5.0},
        {"CarIdx": 4, "Position": 4, "Time": 6.0},
        {"CarIdx": 5, "Position": 5, "Time": 7.0},
        {"CarIdx": 6, "Position": 6, "Time": 7.2},
    ]
    drivers = {
        index: {"name": f"Driver {index + 1}", "number": str(index + 1)}
        for index in range(7)
    }

    queued = engine._queue_final_laps_battle(
        results,
        drivers,
        current_lap=49,
        total_laps=50,
    )

    item = engine.broadcast_queue.items[0]
    assert queued is True
    assert item.camera_target_car_idx == 6
    assert "for 7th" in item.message
    assert "0.2 seconds" in item.message


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

    for _ in range(20):
        engine.tick(source)

    categories = [item.category for item in engine.broadcast_queue.items]
    assert "post_race" in categories
    assert "incident" not in categories


def test_three_quarter_recap_waits_until_three_quarter_distance():
    engine = BroadcastEngine(openai_director=SilentOpenAI())
    race_state = RaceState(
        current_lap=59,
        total_laps=80,
        laps_remaining=21,
        green_lap_count=18,
        caution_count=1,
        is_green=True,
    )

    queued = engine._queue_three_quarter_recap(
        [],
        {},
        race_state,
        current_lap=59,
        total_laps=80,
        track_info={"track_name": "Michigan International Speedway"},
    )

    assert queued is False
    assert engine.three_quarter_recap_queued is False


def test_three_quarter_recap_queues_once_with_key_stats():
    engine = BroadcastEngine(openai_director=SilentOpenAI())
    drivers = {
        1: {"name": "Leader One", "number": "1"},
        2: {"name": "Fast Driver", "number": "2"},
        3: {"name": "Mover Driver", "number": "3"},
        4: {"name": "Fading Driver", "number": "4"},
    }
    race_state = RaceState(
        current_lap=60,
        total_laps=80,
        laps_remaining=20,
        green_lap_count=22,
        caution_count=2,
        is_green=True,
    )
    engine.lead_change_count = 3
    engine.fastest_lap_tracker.fastest_car_idx = 2
    engine.fastest_lap_tracker.fastest_time = 31.234
    engine.race_intelligence.driver_summaries = {
        3: SimpleNamespace(
            car_idx=3,
            driver_name="Mover Driver",
            car_number="3",
            positions_gained=8,
            positions_lost=0,
        ),
        4: SimpleNamespace(
            car_idx=4,
            driver_name="Fading Driver",
            car_number="4",
            positions_gained=0,
            positions_lost=6,
        ),
    }

    queued = engine._queue_three_quarter_recap(
        [],
        drivers,
        race_state,
        current_lap=60,
        total_laps=80,
        track_info={"track_name": "Michigan International Speedway"},
    )

    item = engine.broadcast_queue.items[0]
    assert queued is True
    assert item.category == "race_recap"
    assert item.protected is True
    assert item.dedupe_key == "race_recap:three_quarter:80"
    assert "three-quarter mark" in item.message
    assert "2 cautions" in item.message
    assert "3 lead changes" in item.message
    assert "Fastest lap belongs to Fast Driver in the number 2" in item.message
    assert "Biggest mover is Mover Driver" in item.message
    assert "Fading Driver" in item.message

    queued_again = engine._queue_three_quarter_recap(
        [],
        drivers,
        race_state,
        current_lap=61,
        total_laps=80,
        track_info={"track_name": "Michigan International Speedway"},
    )

    assert queued_again is False


class RaceFlags:
    GREEN = 0x00000004
    CAUTION = 0x00004000
    ONE_TO_GREEN = 0x00000200
    START_READY = 0x20000000
    START_GO = 0x80000000


def test_caution_top_ten_waits_when_top_ten_car_is_on_pit_road():
    engine = BroadcastEngine(openai_director=SilentOpenAI())
    drivers = {
        car_idx: {"name": f"Driver {car_idx}", "number": str(car_idx)}
        for car_idx in range(12)
    }
    results = [
        {"CarIdx": car_idx, "Position": car_idx}
        for car_idx in range(12)
    ]
    pit_road = [False] * 12
    pit_road[4] = True

    for _ in range(10):
        engine._queue_caution_top_ten_reset(
            results,
            drivers,
            current_lap=25,
            pit_road_status=pit_road,
        )

    assert not any(
        item.category == "caution_top_ten_reset"
        for item in engine.broadcast_queue.items
    )


def test_caution_top_ten_queues_after_order_is_stable_and_pit_road_clear():
    engine = BroadcastEngine(openai_director=SilentOpenAI())
    drivers = {
        car_idx: {"name": f"Driver {car_idx}", "number": str(car_idx)}
        for car_idx in range(12)
    }
    results = [
        {"CarIdx": car_idx, "Position": car_idx}
        for car_idx in range(12)
    ]
    pit_road = [False] * 12

    for _ in range(6):
        engine._queue_caution_top_ten_reset(
            results,
            drivers,
            current_lap=25,
            pit_road_status=pit_road,
        )

    item = next(
        item
        for item in engine.broadcast_queue.items
        if item.category == "caution_top_ten_reset"
    )
    assert item.participant_car_indices == tuple(range(10))
    assert item.delay_seconds == 1.5
