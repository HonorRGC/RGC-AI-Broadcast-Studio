from __future__ import annotations

from pathlib import Path

from tools.iracing_car_image_probe import (
    candidate_roots,
    image_like_files,
    recent_files,
    scan_text_file_for_patterns,
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
