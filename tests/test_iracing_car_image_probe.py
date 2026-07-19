from __future__ import annotations

from pathlib import Path

from tools.iracing_car_image_probe import (
    candidate_roots,
    detect_image_type,
    extract_images_from_bytes,
    image_like_files,
    match_driver_label,
    possible_ids_from_context,
    recent_files,
    scan_text_file_for_patterns,
    write_extracted_images,
    write_manifest,
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
