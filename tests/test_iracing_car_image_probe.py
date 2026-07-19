from __future__ import annotations

from pathlib import Path

from tools.iracing_car_image_probe import (
    ProbeRoot,
    cache_metadata_files,
    candidate_roots,
    detect_image_type,
    extract_images_from_bytes,
    find_render_requests_in_text,
    image_like_files,
    match_driver_label,
    match_render_request_label,
    possible_ids_from_context,
    recent_files,
    scan_text_file_for_patterns,
    scan_recent_render_requests,
    scan_render_requests_from_cache_metadata,
    write_extracted_images,
    write_manifest,
    write_render_request_manifest,
)


def test_candidate_roots_include_iracing_electron_and_onedrive_paths(tmp_path):
    env = {
        "APPDATA": str(tmp_path / "appdata"),
        "LOCALAPPDATA": str(tmp_path / "local"),
        "OneDrive": str(tmp_path / "onedrive"),
    }

    roots = candidate_roots(home=tmp_path / "home", env=env)
    paths = [root.path for root in roots]

    assert Path(env["APPDATA"]) / "iracing-electron" in paths
    assert Path(env["LOCALAPPDATA"]) / "iracing-electron" in paths
    assert Path(env["OneDrive"]) / "Documents" / "iRacing" / "paint" in paths


def test_recent_files_filters_by_age(tmp_path):
    fresh = tmp_path / "fresh.png"
    old = tmp_path / "old.png"
    fresh.write_bytes(b"new")
    old.write_bytes(b"old")

    now = 2_000_000.0
    fresh_time = now - 10
    old_time = now - 7200
    import os

    os.utime(fresh, (fresh_time, fresh_time))
    os.utime(old, (old_time, old_time))

    files = recent_files(tmp_path, minutes=30, now=now)

    assert [item.path for item in files] == [fresh]


def test_image_like_files_only_keeps_browser_image_extensions(tmp_path):
    png = tmp_path / "render.png"
    log = tmp_path / "debug.log"
    png.write_bytes(b"image")
    log.write_text("paint render", encoding="utf-8")

    files = recent_files(tmp_path, minutes=30)

    assert [item.path for item in image_like_files(files)] == [png]


def test_scan_text_file_for_patterns_returns_snippet(tmp_path):
    log = tmp_path / "ui.log"
    log.write_text(
        "opened car model viewer and requested purple-car-thumbnail.webp for paint render",
        encoding="utf-8",
    )

    hits = scan_text_file_for_patterns(log, patterns=["thumbnail"])

    assert len(hits) == 1
    assert hits[0].pattern == "thumbnail"
    assert "purple-car-thumbnail.webp" in hits[0].snippet


def test_detect_image_type_identifies_common_image_headers():
    assert detect_image_type(b"\x89PNG\r\n\x1a\nrest") == "png"
    assert detect_image_type(b"\xff\xd8\xffrest") == "jpg"
    assert detect_image_type(b"RIFF\x04\x00\x00\x00WEBPrest") == "webp"
    assert detect_image_type(b"not image") == ""


def test_extract_images_from_bytes_carves_png_from_cache_blob():
    png = b"\x89PNG\r\n\x1a\nfake image dataIEND\xaeB`\x82"
    images = extract_images_from_bytes(b"prefix" + png + b"suffix")

    assert len(images) == 1
    assert images[0].extension == "png"
    assert images[0].data == png


def test_write_extracted_images_writes_deduped_images(tmp_path):
    cache = tmp_path / "Cache_Data"
    cache.mkdir()
    blob = cache / "f_000001"
    png = b"\x89PNG\r\n\x1a\nfake image dataIEND\xaeB`\x82"
    blob.write_bytes(b"prefix" + png + png + b"suffix")

    files = recent_files(cache, minutes=30)
    output_dir = tmp_path / "out"
    written = write_extracted_images(files, output_dir)

    assert len(written) == 1
    assert written[0].path.suffix == ".png"
    assert written[0].path.read_bytes() == png


def test_possible_ids_from_context_finds_customer_and_car_paint_ids():
    context = "https://members-ng.iracing.com/render?customer_id=251830 car_num_90223.tga"

    assert possible_ids_from_context(context) == ("251830", "90223")


def test_match_driver_label_matches_live_customer_id():
    live_drivers = {24: {"number": "34", "name": "T.J. Lee", "cust_id": "251830"}}

    assert match_driver_label(("251830",), live_drivers) == "#34 T.J. Lee"


def test_write_manifest_includes_matched_driver(tmp_path):
    cache = tmp_path / "Cache_Data"
    cache.mkdir()
    blob = cache / "f_000001"
    png = b"\x89PNG\r\n\x1a\nfake image dataIEND\xaeB`\x82"
    blob.write_bytes(b"customer_id=251830 " + png)

    files = recent_files(cache, minutes=30)
    output_dir = tmp_path / "out"
    written = write_extracted_images(files, output_dir)
    manifest_json, manifest_csv = write_manifest(
        written,
        output_dir,
        {24: {"number": "34", "name": "T.J. Lee", "cust_id": "251830"}},
    )

    assert "#34 T.J. Lee" in manifest_json.read_text(encoding="utf-8")
    assert "#34 T.J. Lee" in manifest_csv.read_text(encoding="utf-8")


def test_find_render_requests_extracts_iracing_local_car_renderer_url(tmp_path):
    text = (
        "1/0/http://127.0.0.1:32034/pk_car.png?"
        "size=2&carPath=stockcars2%5Cmustang2019&"
        "carCustPaint=C%3A%5CUsers%5Cleeal%5CDocuments%5CiRacing%5Cpaint%5C"
        "stockcars2+mustang2019%5Ccar_251830.tga&number=34"
        "\x00HTTP/1.1 200 OK\x00Content-Length: 72649"
    )

    requests = find_render_requests_in_text(text, tmp_path / "data_1")

    assert len(requests) == 1
    assert requests[0].kind == "car"
    assert requests[0].number == "34"
    assert requests[0].cust_id == "251830"
    assert requests[0].car_path == "stockcars2 mustang2019"


def test_match_render_request_label_uses_number_and_car_path_when_no_customer_id(tmp_path):
    request = find_render_requests_in_text(
        (
            "http://127.0.0.1:32034/pk_car.png?"
            "size=2&carPath=stockcars2%5Ccamaro2019&carCustPaint=%5Bobject+Object%5D&number=2"
        ),
        tmp_path / "data_1",
    )[0]

    assert (
        match_render_request_label(
            request,
            {
                1: {"number": "2", "name": "Nate Amiot", "car_path": "stockcars2 camaro2019"},
                2: {"number": "3", "name": "Other Driver", "car_path": "stockcars2 camaro2019"},
            },
        )
        == "#2 Nate Amiot"
    )


def test_scan_recent_render_requests_reads_cache_metadata(tmp_path):
    cache = tmp_path / "Cache_Data"
    cache.mkdir()
    data = cache / "data_1"
    data.write_text(
        "http://127.0.0.1:32034/pk_helmet.png?size=2&hlmtCustPaint=null",
        encoding="utf-8",
    )
    files = recent_files(cache, minutes=30)

    requests = scan_recent_render_requests([(type("Root", (), {"label": "iRacing Electron"})(), files)])

    assert len(requests) == 1
    assert requests[0].kind == "helmet"


def test_write_render_request_manifest_includes_matches(tmp_path):
    request = find_render_requests_in_text(
        "http://127.0.0.1:32034/pk_car.png?size=2&carPath=stockcars2%5Cmustang2019&number=34",
        tmp_path / "data_1",
    )[0]

    manifest_json, manifest_csv = write_render_request_manifest(
        [request],
        tmp_path,
        {24: {"number": "34", "name": "T.J. Lee", "car_path": "stockcars2 mustang2019"}},
    )

    assert "#34 T.J. Lee" in manifest_json.read_text(encoding="utf-8")
    assert "#34 T.J. Lee" in manifest_csv.read_text(encoding="utf-8")


def test_cache_metadata_files_include_chromium_data_files(tmp_path):
    app_root = tmp_path / "iracing-electron"
    cache_data = app_root / "Cache" / "Cache_Data"
    cache_data.mkdir(parents=True)
    data = cache_data / "data_1"
    data.write_text("metadata", encoding="utf-8")
    non_data = cache_data / "f_000001"
    non_data.write_text("blob", encoding="utf-8")

    assert cache_metadata_files(app_root) == [data]


def test_scan_render_requests_from_cache_metadata_ignores_file_age(tmp_path):
    app_root = tmp_path / "iracing-electron"
    cache_data = app_root / "Cache" / "Cache_Data"
    cache_data.mkdir(parents=True)
    data = cache_data / "data_1"
    data.write_text(
        "http://127.0.0.1:32034/pk_car.png?size=2&carPath=stockcars2%5Cmustang2019&number=34",
        encoding="utf-8",
    )

    requests = scan_render_requests_from_cache_metadata(
        [ProbeRoot("iRacing Electron app data", app_root)]
    )

    assert len(requests) == 1
    assert requests[0].kind == "car"
