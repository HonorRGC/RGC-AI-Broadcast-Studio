from types import SimpleNamespace
from production.split_strategy import SplitStrategyReporter


def state(name, lap):
    return SimpleNamespace(driver_name=name, last_pit_lap=lap, green_flag_pit_stop_count=int(lap > 0), last_pit_under_caution=False, on_pit_road=False)


def test_split_stops_and_caution_are_reported_once_without_guessed_fuel():
    reporter = SplitStrategyReporter()
    states = [state("Early", 75), state("Late", 0)]
    assert "halfway" in reporter.update(states, 76, 150)
    assert reporter.update(states, 77, 150) == ""
    states[1] = state("Late", 102)
    assert "27 laps between" in reporter.update(states, 103, 150)
    assert reporter.update(states, 104, 150) == ""
    message = reporter.update(states, 119, 150, True)
    assert "31 laps remaining" in message
    assert "any fresher-tire advantage" in message
    assert reporter.update(states, 120, 150, True) == ""


def test_caution_stops_do_not_supply_green_strategy_comparison():
    reporter = SplitStrategyReporter()
    early, late = state("Early", 75), state("Late", 102)
    late.last_pit_under_caution = True
    assert reporter.update([early, late], 119, 150, True) == ""
