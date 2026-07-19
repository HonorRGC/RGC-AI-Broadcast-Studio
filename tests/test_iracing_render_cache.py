from __future__ import annotations

from pathlib import Path

from production.iracing_render_cache import (
    best_render_template,
    build_iracing_render_image_url,
    cache_metadata_files,
    find_render_requests_in_text,
    recent_cache_blobs,
    render_car_path,
    render_request_matches_driver,
    scan_iracing_render_requests,
    synthesize_render_request_url,
)


def test_find_render_requests_extracts_local_car_render_url(tmp_path):
    text = (
        "http://127.0.0.1:32034/pk_car.png?"
        "size=2&carPath=stockcars2%5Cmustang2019&"
        "carCustPaint=C%3A%5CUsers%5Cleeal%5CDocuments%5CiRacing%5Cpaint%5C"
        "stockcars2+mustang2019%5Ccar_251830.tga&number=34"
    )

    requests = find_render_requests_in_text(text, tmp_path / "data_1")

    assert len(requests) == 1
    assert requests[0].kind == "car"
    assert requests[0].number == "34"
    assert requests[0].cust_id == "251830"
    assert requests[0].car_path == "stockcars2 mustang2019"


def test_render_request_requires_car_path_to_prevent_old_car_match(tmp_path):
    request = find_render_requests_in_text(
        (
            "http://127.0.0.1:32034/pk_car.png?"
            "size=2&carPath=stockcars2%5Cchevy&"
            "carCustPaint=C%3A%5Cpaint%5Cstockcars2+chevy%5Ccar_251830.tga&number=34"
        ),
        tmp_path / "data_1",
    )[0]

    assert not render_request_matches_driver(
        request,
        {"number": "34", "cust_id": "251830", "car_path": "stockcars2 mustang2019"},
    )


def test_render_request_matches_by_number_and_car_path_when_no_customer_id(tmp_path):
    request = find_render_requests_in_text(
        (
            "http://127.0.0.1:32034/pk_car.png?"
            "size=2&carPath=stockcars2%5Ccamaro2019&carCustPaint=%5Bobject+Object%5D&number=2"
        ),
        tmp_path / "data_1",
    )[0]

    assert render_request_matches_driver(
        request,
        {"number": "2", "cust_id": "386497", "car_path": "stockcars2 camaro2019"},
    )


def test_cache_metadata_files_finds_chromium_data_files(tmp_path):
    cache_data = tmp_path / "iracing-electron" / "Cache" / "Cache_Data"
    cache_data.mkdir(parents=True)
    data = cache_data / "data_1"
    data.write_text("cache", encoding="utf-8")
    (cache_data / "f_000001").write_text("blob", encoding="utf-8")

    assert cache_metadata_files(tmp_path / "iracing-electron") == [
        data,
        cache_data / "f_000001",
    ]


def test_recent_cache_blobs_are_bounded_and_newest_first(tmp_path):
    old_blob = tmp_path / "f_old"
    new_blob = tmp_path / "f_new"
    old_blob.write_text("old", encoding="utf-8")
    new_blob.write_text("new", encoding="utf-8")
    old_time = 1000
    new_time = 2000
    import os

    os.utime(old_blob, (old_time, old_time))
    os.utime(new_blob, (new_time, new_time))

    assert recent_cache_blobs(tmp_path, limit=1) == [new_blob]


def test_scan_iracing_render_requests_reads_metadata_files(tmp_path):
    cache_data = tmp_path / "iracing-electron" / "Cache" / "Cache_Data"
    cache_data.mkdir(parents=True)
    data = cache_data / "data_1"
    data.write_text(
        "http://127.0.0.1:32034/pk_car.png?size=2&carPath=stockcars2%5Cmustang2019&number=34",
        encoding="utf-8",
    )

    requests = scan_iracing_render_requests([tmp_path / "iracing-electron"])

    assert len(requests) == 1


def test_build_iracing_render_image_url_uses_matching_render_request(monkeypatch, tmp_path):
    from production import iracing_render_cache

    request = find_render_requests_in_text(
        (
            "http://127.0.0.1:32034/pk_car.png?"
            "size=2&carPath=stockcars2%5Cmustang2019&number=34"
        ),
        Path("data_1"),
    )[0]
    monkeypatch.setattr(iracing_render_cache, "cached_render_requests", lambda now=None: [request])

    assert build_iracing_render_image_url(
        {"number": "34", "car_path": "stockcars2 mustang2019"}
    ).startswith("http://127.0.0.1:32034/pk_car.png")


def test_synthesize_render_request_url_uses_local_paint_and_renderer_port(monkeypatch, tmp_path):
    from production import iracing_render_cache
    from production.car_paint_locator import CarPaintMatch

    paint = tmp_path / "paint" / "stockcars2 mustang2019" / "car_251830.tga"
    paint.parent.mkdir(parents=True)
    paint.write_text("paint", encoding="utf-8")
    request = find_render_requests_in_text(
        (
            "http://127.0.0.1:32034/pk_car.png?"
            "size=0&carPath=stockcars2%5Cmustang2019&noDecal=false&"
            "carCustPaint=%5Bobject+Object%5D&carPat=19&"
            "carCol=16002d%2C00a1ff%2Cf70077&licCol=&sponsors=0%2C0&"
            "noNum=false&number=2&numSlnt=3&numPat=48&"
            "numCol=ffffff%2Cf70077%2C16002d&carRimType=3&"
            "carRimCol=16002d&carCfg=-1&carCfgSubDir=&carCfgCustomPaintExt="
        ),
        Path("data_1"),
    )[0]
    monkeypatch.setattr(
        iracing_render_cache,
        "find_car_paint",
        lambda driver: CarPaintMatch(path=paint, source="car_path"),
    )

    url = synthesize_render_request_url(
        {"number": "34", "cust_id": "251830", "car_path": "stockcars2 mustang2019"},
        {"number": "34", "cust_id": "251830", "car_path": "stockcars2 mustang2019"},
        [request],
    )

    assert url.startswith("http://127.0.0.1:32034/pk_car.png?")
    assert "size=2" in url
    assert "carPath=stockcars2%5Cmustang2019" in url
    assert "carCustPaint=" in url
    assert "carPat=19" in url
    assert "numPat=48" in url
    assert "carRimType=3" in url
    assert "carCfgCustomPaintExt=tga" in url
    assert "number=34" in url


def test_build_iracing_render_image_url_can_synthesize_when_exact_driver_was_not_cached(monkeypatch, tmp_path):
    from production import iracing_render_cache
    from production.car_paint_locator import CarPaintMatch

    paint = tmp_path / "paint" / "stockcars2 mustang2019" / "car_251830.tga"
    paint.parent.mkdir(parents=True)
    paint.write_text("paint", encoding="utf-8")
    renderer_request = find_render_requests_in_text(
        "http://127.0.0.1:32034/pk_car.png?size=2&carPath=stockcars2%5Cmustang2019&number=2",
        Path("data_1"),
    )[0]
    monkeypatch.setattr(
        iracing_render_cache,
        "cached_render_requests",
        lambda now=None: [renderer_request],
    )
    monkeypatch.setattr(
        iracing_render_cache,
        "find_car_paint",
        lambda driver: CarPaintMatch(path=paint, source="car_path"),
    )

    url = build_iracing_render_image_url(
        {"number": "34", "cust_id": "251830", "car_path": "stockcars2 mustang2019"}
    )

    assert url.startswith("http://127.0.0.1:32034/pk_car.png?")
    assert "carCustPaint=" in url
    assert "number=34" in url


def test_best_render_template_prefers_same_car_path_over_first_available(tmp_path):
    requests = find_render_requests_in_text(
        (
            "http://127.0.0.1:32034/pk_car.png?size=2&carPath=rt2000&number=64 "
            "http://127.0.0.1:32034/pk_car.png?size=0&carPath=stockcars2%5Cmustang2019&number="
        ),
        tmp_path / "data_1",
    )

    template = best_render_template(
        requests,
        {"number": "34", "cust_id": "251830", "car_path": "stockcars2 mustang2019"},
    )

    assert template.car_path == "stockcars2 mustang2019"


def test_render_car_path_preserves_explicit_slash_path():
    assert (
        render_car_path(
            {"car_path": "stockcars2\\mustang2019"},
            {"car_path": "stockcars2 mustang2019"},
        )
        == "stockcars2\\mustang2019"
    )
