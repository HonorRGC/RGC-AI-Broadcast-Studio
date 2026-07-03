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

    assert "A majority of the field" in report.message
    assert "3 of 5 cars" in report.message
    assert "Driver 1, Driver 2, and Driver 3" in report.message
    assert report.car_indices == (0, 1, 2)
    assert repeated is None
