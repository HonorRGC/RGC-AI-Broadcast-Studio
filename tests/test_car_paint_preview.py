from production.car_paint_preview import (
    build_car_paint_preview_url,
    ensure_preview_file,
    safe_filename_part,
)


def test_safe_filename_part_removes_unsafe_characters():
    assert safe_filename_part("TJ Lee #34") == "TJLee34"


def test_build_car_paint_preview_url_returns_empty_when_missing(tmp_path):
    assert (
        build_car_paint_preview_url(
            {"cust_id": "90223", "car_path": "stockcars/truck"},
            paint_roots=[tmp_path],
            cache_dir=tmp_path / "cache",
        )
        == ""
    )


def test_ensure_preview_file_copies_browser_ready_png(tmp_path):
    paint = tmp_path / "car_90223.png"
    paint.write_bytes(b"fake png")

    preview = ensure_preview_file(
        paint,
        {"cust_id": "90223"},
        cache_dir=tmp_path / "cache",
    )

    assert preview is not None
    assert preview.name.startswith("car_90223_")
    assert preview.suffix == ".png"
    assert preview.read_bytes() == b"fake png"


def test_build_car_paint_preview_url_uses_detected_car_file(tmp_path):
    paint_root = tmp_path / "paint"
    car_folder = paint_root / "stockcars2 camaro2019"
    car_folder.mkdir(parents=True)
    paint = car_folder / "car_251830.png"
    paint.write_bytes(b"fake png")

    url = build_car_paint_preview_url(
        {"cust_id": "251830", "car_path": "stockcars2 camaro2019"},
        paint_roots=[paint_root],
        cache_dir=tmp_path / "cache",
    )

    assert url.startswith("/paint-previews/car_251830_")
