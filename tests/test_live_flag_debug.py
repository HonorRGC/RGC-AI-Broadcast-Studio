from tools.live_flag_debug import changed_array_indices, compact_value


def test_changed_array_indices_reports_car_idx_deltas():
    assert changed_array_indices((0, 0, 0), (0, 4, 0)) == [(1, 0, 4)]


def test_compact_value_rounds_floats_for_readable_debug_output():
    assert compact_value(1.23456) == 1.235
    assert compact_value(True) is True
