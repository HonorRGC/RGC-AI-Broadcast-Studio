from __future__ import annotations

from pathlib import Path

from production.iracing_render_cache import (
    build_iracing_render_image_url,
    cache_metadata_files,
    find_render_requests_in_text,
    render_request_matches_driver,
    scan_iracing_render_requests,
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

    assert cache_metadata_files(tmp_path / "iracing-electron") == [data]


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
