from types import SimpleNamespace

from production.caution_pit_reporter import CautionPitReporter


def test_caution_pit_reporter_announces_one_majority_wave_with_leaders():
    reporter = CautionPitReporter()
    results = [
        {"CarIdx": index, "Position": index} for index in range(5)
    ]
    drivers = {
        index: {"name": f"Driver {index + 1}", "number": str(index + 1)}
        for index in range(5)
    }

    assert reporter.update(True, results, drivers, [True, True, False, False, False]) is None
    report = reporter.update(True, results, drivers, [False, False, True, False, False])
    repeated = reporter.update(True, results, drivers, [False, False, False, True, True])
    restart_report = reporter.build_majority_report()
    restart_repeated = reporter.build_majority_report()

    assert report is None
    assert repeated is None
    assert "A majority of the field" in restart_report.message
    assert "5 of 5 cars" in restart_report.message
    assert "Driver 1, Driver 2, and Driver 3" in restart_report.message
    assert restart_report.car_indices == (0, 1, 2)
    assert restart_repeated is None


def test_caution_pit_reporter_announces_small_group_before_restart():
    reporter = CautionPitReporter()
    results = [
        {"CarIdx": index, "Position": index} for index in range(8)
    ]
    drivers = {
        index: {"name": f"Driver {index + 1}", "number": str(index + 1)}
        for index in range(8)
    }

    assert reporter.update(True, results, drivers, [False, True, False, True, False, False, False, False]) is None
    report = reporter.build_small_group_report()
    repeated = reporter.build_small_group_report()

    assert "Only a few takers" in report.message
    assert "2 cars have come in" in report.message
    assert "Driver 2 and Driver 4" in report.message
    assert report.car_indices == (1, 3)
    assert repeated is None


def test_caution_pit_reporter_mentions_extended_damage_stop():
    reporter = CautionPitReporter()
    results = [{"CarIdx": index, "Position": index} for index in range(5)]
    drivers = {
        index: {"name": f"Driver {index + 1}", "number": str(index + 1)}
        for index in range(5)
    }

    reporter.update(True, results, drivers, [True, True, True, False, False])
    pit_states = {
        0: SimpleNamespace(
            driver_name="Driver 1",
            car_idx=0,
            last_pit_stop_seconds=30.0,
            last_pit_lane_seconds=70.0,
        ),
        1: SimpleNamespace(
            driver_name="Driver 2",
            car_idx=1,
            last_pit_stop_seconds=8.0,
            last_pit_lane_seconds=25.0,
        ),
        2: SimpleNamespace(
            driver_name="Driver 3",
            car_idx=2,
            last_pit_stop_seconds=10.0,
            last_pit_lane_seconds=30.0,
        ),
    }

    report = reporter.build_majority_report(pit_states)

    assert "extended stop" in report.message
    assert "damage repair" in report.message
    assert "Driver 1" in report.message


def test_caution_pit_reporter_mentions_full_service_stops():
    reporter = CautionPitReporter()
    results = [{"CarIdx": index, "Position": index} for index in range(4)]
    drivers = {
        index: {"name": f"Driver {index + 1}", "number": str(index + 1)}
        for index in range(4)
    }

    reporter.update(True, results, drivers, [False, True, False, False])
    pit_states = {
        1: SimpleNamespace(
            driver_name="Driver 2",
            car_idx=1,
            last_pit_stop_seconds=14.0,
            last_pit_lane_seconds=36.0,
        ),
    }

    report = reporter.build_small_group_report(pit_states)

    assert "full service" in report.message
    assert "tires and fuel" in report.message
