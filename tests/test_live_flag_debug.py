from tools.live_flag_debug import (
    ARRAY_WATCH_KEYS,
    changed_array_indices,
    compact_value,
    print_watch_changes,
    track_surface_name,
)


def test_changed_array_indices_reports_car_idx_deltas():
    assert changed_array_indices((0, 0, 0), (0, 4, 0)) == [(1, 0, 4)]


def test_compact_value_rounds_floats_for_readable_debug_output():
    assert compact_value(1.23456) == 1.235
    assert compact_value(True) is True


def test_track_surface_names_are_human_readable():
    assert track_surface_name(3) == "racing surface"
    assert track_surface_name(2) == "pit road"
    assert track_surface_name(-1) == "not in world"


def test_event_probe_ignores_noisy_track_surface_material_watch():
    assert "CarIdxTrackSurfaceMaterial" not in ARRAY_WATCH_KEYS


def test_print_watch_changes_formats_pit_road_event(capsys):
    printed = print_watch_changes(
        previous_scalars={},
        current_scalars={},
        previous_arrays={"CarIdxOnPitRoad": (False,)},
        current_arrays={"CarIdxOnPitRoad": (True,)},
        driver_lookup={0: {"number": "34", "name": "T.J. Lee"}},
    )

    output = capsys.readouterr().out
    assert printed is True
    assert "#34 T.J. Lee" in output
    assert "entered pit road" in output
