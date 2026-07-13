from production.car_paint_locator import (
    candidate_filenames,
    car_path_candidates,
    default_paint_roots,
    find_car_paint,
)


def test_candidate_filenames_include_trading_paints_car_files():
    names = candidate_filenames("90223")

    assert "car_num_90223.tga" in names
    assert "car_90223.tga" in names
    assert "car_decal_90223.tga" in names


def test_car_path_candidates_include_exact_and_last_folder(tmp_path):
    root = tmp_path / "paint"

    candidates = car_path_candidates(root, "stockcars/chevycamarozl12022")

    assert root / "stockcars/chevycamarozl12022" in candidates
    assert root / "chevycamarozl12022" in candidates


def test_find_car_paint_prefers_car_path_match(tmp_path):
    paint_root = tmp_path / "iRacing" / "paint"
    car_folder = paint_root / "stockcars" / "truck"
    car_folder.mkdir(parents=True)
    paint = car_folder / "car_num_90223.tga"
    paint.write_text("fake paint")

    match = find_car_paint(
        {"cust_id": "90223", "car_path": "stockcars/truck"},
        paint_roots=[paint_root],
    )

    assert match.path == paint
    assert match.source == "car_path"
    assert match.browser_ready is False


def test_find_car_paint_scans_when_car_path_folder_is_missing(tmp_path):
    paint_root = tmp_path / "iRacing" / "paint"
    car_folder = paint_root / "unknown" / "car"
    car_folder.mkdir(parents=True)
    paint = car_folder / "car_90223.png"
    paint.write_text("fake preview")

    match = find_car_paint(
        {"cust_id": "90223", "car_path": "wrong/folder"},
        paint_roots=[paint_root],
    )

    assert match.path == paint
    assert match.source == "scan"
    assert match.browser_ready is True


def test_default_paint_roots_include_documents_folder(tmp_path):
    roots = default_paint_roots(home=tmp_path)

    assert tmp_path / "Documents" / "iRacing" / "paint" in roots

