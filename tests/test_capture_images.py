import json
import threading
import time

import pytest

from production.capture_images import CaptureImages, archived_entries, driver_key, fetch_image, image_directory
from production.capture_library import capture_bundles, set_capture_retention


def test_archive_saves_once_in_background_and_keeps_driver_identity(tmp_path):
    capture = tmp_path / "race.jsonl"
    calls, threads = [], []
    def resolve(driver):
        calls.append(driver["number"])
        threads.append(threading.current_thread().name)
        return {"image_url": "http://localhost/pk_car.png", "number_style": {"color": "#fff"}}
    archive = CaptureImages(capture, resolver=resolve, fetcher=lambda url: b"exact original PNG")
    lookup = {0: {"name": "One", "number": "5", "cust_id": 111},
              1: {"name": "Two", "number": "81", "cust_id": 222}}
    try:
        archive.submit(lookup)
        deadline = time.monotonic() + 3
        while not (archive.root / "manifest.json").exists() or archive.status()["saved"] < 2:
            assert time.monotonic() < deadline
            time.sleep(.01)
        archive.last_submit = -30
        archive.submit(lookup)
    finally:
        archive.close()
    root, manifest = archived_entries(capture)
    assert calls == ["5", "81"]
    assert all(name == "capture-car-images" for name in threads)
    assert archive.status()["saved"] == 2
    assert (root / manifest[driver_key(lookup[0])]["file"]).read_bytes() == b"exact original PNG"
    assert driver_key(dict(lookup[0], cust_id=999)) not in manifest


def test_capture_discard_includes_images_and_keeps_other_race(tmp_path):
    capture = tmp_path / "race.jsonl"
    capture.write_text("telemetry")
    capture.with_suffix(".events.jsonl").write_text("events")
    capture.with_suffix(".capture.json").write_text(json.dumps({"process_id": 123}))
    images = image_directory(capture)
    images.mkdir()
    image = images / "saved.png"
    image.write_bytes(b"pixels")
    other = tmp_path / "other.images"
    other.mkdir()
    (other / "saved.png").write_bytes(b"other")
    bundle, = capture_bundles(tmp_path, 123)
    assert bundle["size_bytes"] == sum(p.stat().st_size for p in (*bundle["paths"], image))
    set_capture_retention(bundle, True, tmp_path)
    assert image.is_file()
    set_capture_retention(bundle, False, tmp_path)
    assert not images.exists()
    assert (other / "saved.png").read_bytes() == b"other"


def test_render_download_rejects_remote_hosts():
    with pytest.raises(ValueError):
        fetch_image("https://example.com/car.png")


def test_unavailable_render_is_retried_without_archiving_a_generic_fallback(tmp_path, monkeypatch):
    calls = []
    available = threading.Event()
    attempted = threading.Event()
    def render(driver, require_live_render_match=False):
        calls.append(require_live_render_match)
        attempted.set()
        return {"image_url": "http://localhost/pk_car.png" if available.is_set() else ""}
    monkeypatch.setattr("app.build_featured_driver_render_info", render)
    def fetch(url):
        if not url:
            raise ValueError("not connected yet")
        return b"correct render"
    archive = CaptureImages(tmp_path / "race.jsonl", fetcher=fetch)
    lookup = {0: {"name": "Driver", "number": "34"}}
    try:
        archive.submit(lookup)
        assert attempted.wait(2)
        assert not archive.entries
        available.set()
        with archive.lock:
            archive.attempted.clear()
        archive.last_submit = -30
        archive.submit(lookup)
        deadline = time.monotonic() + 3
        while not (archive.root / "manifest.json").exists():
            assert time.monotonic() < deadline
            time.sleep(.01)
        assert archive.status()["saved"] == 1
        assert calls == [True, True]
    finally:
        archive.close()


def test_overlay_serves_archived_pixels_and_rejects_path_traversal(tmp_path):
    import hashlib
    from urllib.error import HTTPError
    from urllib.request import urlopen
    from production.overlay import OverlayServer
    body = b"\x89PNG\r\n\x1a\noriginal pixels"
    name = hashlib.sha256(body).hexdigest() + ".png"
    (tmp_path / name).write_bytes(body)
    server = OverlayServer(port=0)
    server.capture_image_dir = tmp_path
    server.start()
    base = "http://127.0.0.1:" + str(server.httpd.server_address[1])
    try:
        with urlopen(base + "/capture-images/" + name) as response:
            assert response.read() == body
            assert response.headers["Content-Type"] == "image/png"
        with pytest.raises(HTTPError):
            urlopen(base + "/capture-images/../secret.png")
    finally:
        server.stop()


def test_discard_rejects_unexpected_image_subdirectories_before_deletion(tmp_path):
    capture = tmp_path / "race.jsonl"
    capture.write_text("keep")
    capture.with_suffix(".events.jsonl").write_text("keep")
    capture.with_suffix(".capture.json").write_text("{}")
    image_directory(capture).mkdir()
    (image_directory(capture) / "unexpected").mkdir()
    with pytest.raises(ValueError):
        set_capture_retention({"paths": (capture, capture.with_suffix(".events.jsonl"), capture.with_suffix(".capture.json"))}, False, tmp_path)
    assert capture.read_text() == "keep"
