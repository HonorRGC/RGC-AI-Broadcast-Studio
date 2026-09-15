from types import SimpleNamespace

from production.live_broadcast_validator import LiveBroadcastValidator


class Telemetry:
    def __init__(self, results, pit_road=None, surfaces=None):
        self.results = results
        self.pit_road = pit_road or []
        self.surfaces = surfaces or []

    def get_results(self):
        return self.results

    def get_car_idx_on_pit_road(self):
        return self.pit_road

    def get_car_idx_track_surface(self):
        return self.surfaces


def story(message, car_idx=1):
    return SimpleNamespace(
        category="race_story",
        message=message,
        camera_target_car_idx=car_idx,
    )


def order_item(car_indices):
    return SimpleNamespace(
        category="caution_top_ten_reset",
        message="Before this restart, here is the top ten.",
        participant_car_indices=tuple(car_indices),
        camera_target_car_idx=None,
    )


def test_validator_skips_leader_story_when_driver_is_no_longer_leading():
    telemetry = Telemetry(
        results=[
            {"CarIdx": 0, "Position": 0},
            {"CarIdx": 1, "Position": 1},
        ],
        pit_road=[False, False],
        surfaces=[3, 3],
    )

    result = LiveBroadcastValidator().validate(
        story("The 24 controls the lead right now."),
        telemetry,
    )

    assert result.valid is False
    assert "live position is P2" in result.reason


def test_validator_skips_story_when_driver_pits_before_it_airs():
    telemetry = Telemetry(
        results=[{"CarIdx": 1, "Position": 0}],
        pit_road=[False, True],
        surfaces=[3, 3],
    )

    result = LiveBroadcastValidator().validate(
        story("The 24 has climbed into the top five."),
        telemetry,
    )

    assert result.valid is False
    assert "pit road" in result.reason


def test_validator_allows_current_leader_story():
    telemetry = Telemetry(
        results=[{"CarIdx": 1, "Position": 0}],
        pit_road=[False, False],
        surfaces=[3, 3],
    )

    result = LiveBroadcastValidator().validate(
        story("The 24 is the leader and starting to stretch it."),
        telemetry,
    )

    assert result.valid is True


def test_validator_skips_restart_top_ten_when_live_order_changed():
    telemetry = Telemetry(
        results=[
            {"CarIdx": 2, "Position": 0},
            {"CarIdx": 1, "Position": 1},
            {"CarIdx": 3, "Position": 2},
        ],
    )

    result = LiveBroadcastValidator().validate(order_item((1, 2, 3)), telemetry)

    assert result.valid is False
    assert "top ten" in result.reason


def test_validator_allows_restart_top_ten_when_live_order_matches():
    telemetry = Telemetry(
        results=[
            {"CarIdx": 1, "Position": 0},
            {"CarIdx": 2, "Position": 1},
            {"CarIdx": 3, "Position": 2},
        ],
    )

    result = LiveBroadcastValidator().validate(order_item((1, 2, 3)), telemetry)

    assert result.valid is True
