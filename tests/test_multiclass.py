from production.multiclass import build_multiclass_context


def test_builds_multiclass_context_and_class_positions():
    results = [
        {"CarIdx": 1, "Position": 1},
        {"CarIdx": 2, "Position": 2},
        {"CarIdx": 3, "Position": 3},
        {"CarIdx": 4, "Position": 4},
    ]
    drivers = {
        1: {"name": "Prototype Leader", "number": "1", "car_class_id": "p2", "car_class_short_name": "LMP2"},
        2: {"name": "GT Leader", "number": "21", "car_class_id": "gt3", "car_class_short_name": "GT3"},
        3: {"name": "Prototype Two", "number": "2", "car_class_id": "p2", "car_class_short_name": "LMP2"},
        4: {"name": "GT Two", "number": "22", "car_class_id": "gt3", "car_class_short_name": "GT3"},
    }

    context = build_multiclass_context(results, drivers)

    assert context.active is True
    assert [class_.class_name for class_ in context.classes] == ["LMP2", "GT3"]
    assert context.positions[1].class_position == 1
    assert context.positions[3].class_position == 2
    assert context.positions[2].class_position == 1
    assert context.positions[4].class_size == 2


def test_single_class_context_is_inactive():
    context = build_multiclass_context(
        [{"CarIdx": 1, "Position": 1}, {"CarIdx": 2, "Position": 2}],
        {
            1: {"name": "Driver One", "car_class_id": "gt3"},
            2: {"name": "Driver Two", "car_class_id": "gt3"},
        },
    )

    assert context.active is False
