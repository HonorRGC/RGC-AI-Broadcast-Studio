"""Save actual broadcast renders once, away from the telemetry polling thread."""
import hashlib
import json
import threading
import time
from pathlib import Path
from urllib.parse import urlparse

MAX_IMAGE_BYTES = 5 * 1024 * 1024


def image_directory(capture):
    return Path(capture).with_suffix(".images")


def driver_key(driver):
    # CarIdx alone is unsafe when a different replay or roster is loaded.
    identity = str(driver.get("cust_id") or driver.get("user_id") or driver.get("name", "")).casefold()
    return hashlib.sha256(json.dumps([identity, str(driver.get("number", ""))]).encode()).hexdigest()


def fetch_image(url):
    if url.startswith(("/assets/", "/paint-previews/")):
        from production.overlay import OverlayServer
        root = (Path(__file__).parent / "static" if url.startswith("/assets/")
                else OverlayServer.default_paint_preview_dir()).resolve()
        path = (root / url.rsplit("/", 1)[-1]).resolve()
        if path.parent != root:
            raise ValueError("Image outside preview directory")
        with path.open("rb") as handle:
            body = handle.read(MAX_IMAGE_BYTES + 1)
        if len(body) > MAX_IMAGE_BYTES or not body.startswith(b"\x89PNG\r\n\x1a\n"):
            raise ValueError("Render is not a supported PNG")
        return body
    parsed = urlparse(url)
    # These renders come from local iRacing/SIMRacingApps, never an arbitrary
    # remote host nominated by captured telemetry. Do not follow redirects.
    if parsed.scheme != "http" or parsed.hostname not in ("localhost", "127.0.0.1"):
        raise ValueError("Not a local render")
    from urllib.request import build_opener, HTTPRedirectHandler
    class NoRedirect(HTTPRedirectHandler):
        def redirect_request(self, *args, **kwargs):
            return None
    with build_opener(NoRedirect).open(url, timeout=2) as response:
        body = response.read(MAX_IMAGE_BYTES + 1)
    if len(body) > MAX_IMAGE_BYTES or not body.startswith(b"\x89PNG\r\n\x1a\n"):
        raise ValueError("Render is not a supported PNG")
    return body


class CaptureImages:
    def __init__(self, capture, resolver=None, fetcher=None):
        self.root = image_directory(capture)
        self.resolver, self.fetcher = resolver, fetcher or fetch_image
        self.entries, self.pending, self.attempted = {}, {}, {}
        self.lock, self.wake, self.stopped = threading.Lock(), threading.Event(), threading.Event()
        self.thread = None
        self.last_submit = -30.0
        self.expected = set()

    def submit(self, lookup):
        now = time.monotonic()
        if now - self.last_submit < 10 or self.stopped.is_set():
            return
        self.last_submit = now
        with self.lock:
            for idx, info in (lookup or {}).items():
                if not info.get("name") or not str(info.get("number", "")):
                    continue
                driver = dict(info, car_idx=int(idx))
                key = driver_key(driver)
                self.expected.add(key)
                if key not in self.entries and now - self.attempted.get(key, -60) >= 30:
                    self.pending[key] = driver
            if self.pending and self.thread is None:
                self.thread = threading.Thread(target=self.run, name="capture-car-images", daemon=True)
                self.thread.start()
        self.wake.set()

    def status(self):
        with self.lock:
            return {"saved": len(self.entries), "drivers": len(self.expected), "folder": self.root.name}

    def run(self):
        while not self.stopped.is_set():
            self.wake.wait(1)
            self.wake.clear()
            while not self.stopped.is_set():
                with self.lock:
                    if not self.pending:
                        break
                    key = next(iter(self.pending))
                    driver = self.pending.pop(key)
                    self.attempted[key] = time.monotonic()
                try:
                    resolver = self.resolver
                    if resolver is None:
                        from app import build_featured_driver_render_info
                        # Do not freeze a generic fallback into the archive while
                        # SIMRacingApps is still connecting to the original race.
                        resolver = lambda info: build_featured_driver_render_info(info, require_live_render_match=True)
                    render = resolver(driver)
                    body = self.fetcher(render.get("image_url", ""))
                    if self.stopped.is_set() or not body or len(body) > MAX_IMAGE_BYTES:
                        continue
                    digest = hashlib.sha256(body).hexdigest()
                    self.root.mkdir(parents=True, exist_ok=True)
                    (self.root / (digest + ".png")).write_bytes(body)
                    entry = {"file": digest + ".png", "number_style": render.get("number_style", {})}
                    with self.lock:
                        self.entries[key] = entry
                        manifest = dict(self.entries)
                    temporary = self.root / "manifest.tmp"
                    temporary.write_text(json.dumps(manifest), encoding="utf-8")
                    temporary.replace(self.root / "manifest.json")
                    self.stopped.wait(.1)
                except Exception:
                    # An unavailable render must never stop a race capture.
                    continue

    def close(self):
        self.stopped.set()
        self.wake.set()
        if self.thread:
            self.thread.join(timeout=3)


def archived_entries(capture):
    root = image_directory(capture).resolve()
    try:
        manifest = json.loads((root / "manifest.json").read_text(encoding="utf-8"))
        return root, manifest if isinstance(manifest, dict) else {}
    except (OSError, ValueError):
        return root, {}


def asset_files(capture):
    """Validate every flat archive file before retention may remove anything."""
    root = image_directory(capture)
    if not root.exists():
        return []
    if root.is_symlink() or root.resolve().parent != Path(capture).resolve().parent:
        raise ValueError("Capture images must stay inside recordings")
    files = list(root.iterdir())
    if any(not p.is_file() or p.is_symlink() or p.resolve().parent != root.resolve() for p in files):
        raise ValueError("Unexpected entry in capture image folder")
    return files
