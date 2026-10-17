import pytest

from production.live_timing import LiveTimingTracker
from production.overlay import OverlayStateBuilder


def cars():
    return [{"CarIdx": i, "Position": i + 1, "LapsComplete": 5,
             "FastestTime": 100, "Time": i * 10} for i in range(3)]


def update(tracker, now, positions, **kwargs):
    return tracker.update(now=now, session="race", results=cars(),
                          positions=positions, **kwargs)


def test_gaps_change_without_scored_time_changes_and_interval_is_separate():
    tracker = LiveTimingTracker()
    first = update(tracker, 10, {0: .5, 1: .45, 2: .42})
    second = update(tracker, 10.1, {0: .501, 1: .452, 2: .421})
    assert first[1]["gap"] == pytest.approx(5)
    assert second[1]["gap"] == pytest.approx(4.9)
    assert second[2]["gap"] == pytest.approx(8)
    assert second[2]["interval"] == pytest.approx(3.1)


def test_start_finish_crossing_has_no_lap_sized_jump():
    tracker = LiveTimingTracker()
    first = update(tracker, 10, {0: .99, 1: .98})
    second = update(tracker, 11, {0: .01, 1: .999})
    assert first[1]["gap"] == pytest.approx(1)
    assert second[1]["gap"] == pytest.approx(.55)


def test_mid_race_start_uses_live_completed_laps_instead_of_stale_results():
    output = update(LiveTimingTracker(), 10, {0: .01, 1: .99},
                    completed_laps={0: 6, 1: 5})
    assert output[1]["gap"] == pytest.approx(2)


def test_history_measures_crossing_time_instead_of_uniform_lap_projection():
    tracker = LiveTimingTracker()
    update(tracker, 10, {0: .5, 1: .45})
    update(tracker, 11, {0: .52, 1: .48})
    timing = update(tracker, 12, {0: .53, 1: .51})
    assert timing[1]["gap"] == pytest.approx(1.5)


def test_lapped_cars_are_not_reported_as_close_same_lap_gaps():
    result = cars()
    result[1]["LapsComplete"] = 3
    output = LiveTimingTracker().update(now=10, session="race", results=result,
                                       positions={0: .5, 1: .45})
    assert output[1]["gap"] == "-2 laps"


def test_practice_relative_ignores_completed_lap_counts():
    output = update(LiveTimingTracker(), 10, {0: .01, 1: .99}, race=False)
    assert output[1]["gap"] == pytest.approx(2)


@pytest.mark.parametrize("invalid", [-1, float("nan"), None, 1.1])
def test_invalid_positions_do_not_fabricate_live_timing(invalid):
    tracker = LiveTimingTracker()
    update(tracker, 10, {0: .5, 1: .45})
    assert 1 not in update(tracker, 11, {0: .51, 1: invalid})


def test_missing_leader_pit_and_off_world_suppress_live_values():
    tracker = LiveTimingTracker()
    assert update(tracker, 10, {1: .45})[1]["gap"] is None
    assert 1 not in update(tracker, 11, {0: .5, 1: .45}, pit_road={1: True})
    assert 1 not in update(tracker, 12, {0: .5, 1: .45}, surfaces={1: -1})


def test_replay_seek_and_session_change_clear_previous_history():
    tracker = LiveTimingTracker()
    update(tracker, 10, {0: .99, 1: .98})
    update(tracker, 11, {0: .01, 1: .999})
    output = update(tracker, 1, {0: .5, 1: .4})
    assert output[1]["gap"] == pytest.approx(10)
    tracker.update(now=2, session="practice", results=cars(), positions={0: .2, 1: .1})
    assert len(tracker.samples[0]) == 1


def test_overlay_integration_exposes_both_live_values_in_practice():
    from tests.test_overlay import LiveDriverTelemetry

    class Telemetry(LiveDriverTelemetry):
        now = 10
        pct = [0] * 10

        def get_session_type(self):
            return "Practice"

        def get_session_time(self):
            return self.now

        def get_car_idx_lap_dist_pct(self):
            return self.pct

    telemetry = Telemetry()
    telemetry.pct[7], telemetry.pct[3], telemetry.pct[9] = .5, .45, .4
    builder = OverlayStateBuilder()
    first = builder.build_from_telemetry(telemetry).to_dict()["leaderboard"]
    telemetry.now = 10.1
    telemetry.pct[3] = .451
    second = builder.build_from_telemetry(telemetry).to_dict()["leaderboard"]
    assert first[1]["gap_to_leader"] != second[1]["gap_to_leader"]
    assert second[2]["interval_to_ahead"]
    assert second[1]["fastest_lap"] == "31.456"


def test_overlay_worker_refreshes_independently_and_stops():
    import threading
    from production.overlay import OverlayServer

    refreshed = threading.Event()
    calls = []
    server = OverlayServer()

    class Telemetry:
        def is_connected(self):
            return True

    def refresh(telemetry):
        calls.append(telemetry)
        if len(calls) >= 3:
            refreshed.set()

    server.update_from_telemetry = refresh
    telemetry = Telemetry()
    try:
        server.start_live_refresh(telemetry)
        assert refreshed.wait(2), "No continuous telemetry updates"
        assert server.live_refresh_active
    finally:
        server.stop_live_refresh()
    count = len(calls)
    assert not server.live_refresh_active
    assert len(calls) == count


def test_repeated_driver_features_keep_rpm_and_both_fixed_timing_values():
    from production.overlay import OverlayServer
    from tests.test_overlay import LiveDriverTelemetry

    telemetry = LiveDriverTelemetry()
    server = OverlayServer()
    server.update_from_telemetry(telemetry)
    entry = next(entry for entry in server.state.producer_leaderboard if entry.car_idx == 3)
    entry.gap_to_leader = "+4.91"
    entry.interval_to_ahead = "+2.13"
    for story in ("Rundown", "Race call", "Rundown again"):
        server.show_featured_driver("77", "Austin Peterson", car_idx=3,
                                    story=story, telemetry=telemetry)
        card = server.state.featured_driver.to_dict()
        assert card["rpm"] == 8353
        assert card["gear"] == 5
        assert card["gap_to_leader"] == "+4.91"
        assert card["interval_to_ahead"] == "+2.13"
