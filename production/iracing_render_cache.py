from __future__ import annotations

import ctypes
import os
import re
import time
from dataclasses import dataclass
from pathlib import Path
from urllib.parse import parse_qs, quote_plus, unquote, urlparse

from production.car_paint_locator import find_car_paint


WINDOWS_ERROR_HANDLE = -1
CACHE_TTL_SECONDS = 20
MAX_CACHE_BLOB_FILES = 250


@dataclass(frozen=True)
class RenderRequest:
    url: str
    kind: str
    source_path: Path
    car_path: str = ""
    number: str = ""
    cust_id: str = ""
    size: str = ""


_CACHE = {
    "loaded_at": 0.0,
    "requests": [],
}


def build_iracing_render_image_url(driver_info, *, now=None):
    """Return iRacing's locally rendered 3D car image URL for a live driver.

    iRacing's UI asks a local renderer for car images at URLs like:
    http://127.0.0.1:<port>/pk_car.png?... .

    This resolver reads the local Electron cache metadata, finds those render
    URLs, and conservatively matches them to the live driver. It avoids loose
    customer-id-only matches because the cache may contain old cars from other
    sessions or car pages.
    """
    driver = normalize_driver_info(driver_info)
    if not driver["number"] and not driver["cust_id"]:
        return ""

    matches = [
        request
        for request in cached_render_requests(now=now)
        if request.kind == "car" and render_request_matches_driver(request, driver)
    ]
    if not matches:
        return synthesize_render_request_url(driver_info, driver, cached_render_requests(now=now))

    return best_render_request(matches, driver).url


def cached_render_requests(*, now=None):
    now = time.time() if now is None else float(now)
    if now - float(_CACHE["loaded_at"] or 0) <= CACHE_TTL_SECONDS:
        return list(_CACHE["requests"])

    requests = scan_iracing_render_requests()
    _CACHE["loaded_at"] = now
    _CACHE["requests"] = requests
    return list(requests)


def scan_iracing_render_requests(roots=None):
    requests = []
    for root in roots or default_iracing_electron_roots():
        for path in cache_metadata_files(root):
            requests.extend(scan_render_requests(path))
    return unique_render_requests(requests)


def default_iracing_electron_roots(env=None):
    env = env or os.environ
    roots = []
    for key in ("APPDATA", "LOCALAPPDATA"):
        base = env.get(key, "").strip()
        if base:
            roots.append(Path(base) / "iracing-electron")

    unique = []
    seen = set()
    for root in roots:
        key = str(root).lower()
        if key not in seen:
            unique.append(root)
            seen.add(key)
    return unique


def cache_metadata_files(root: Path):
    candidates = []
    for directory in (root, root / "Cache", root / "Cache" / "Cache_Data"):
        if not directory.exists() or not directory.is_dir():
            continue
        try:
            candidates.extend(sorted(directory.glob("data_*")))
            candidates.extend(recent_cache_blobs(directory))
        except OSError:
            continue

    unique = []
    seen = set()
    for path in candidates:
        try:
            if not path.is_file():
                continue
        except OSError:
            continue
        key = str(path).lower()
        if key not in seen:
            unique.append(path)
            seen.add(key)
    return unique


def recent_cache_blobs(directory: Path, *, limit=MAX_CACHE_BLOB_FILES):
    """Return recent Chromium cache blobs that may contain loading-screen render URLs.

    iRacing's loading UI can place useful /pk_car.png references in Chromium
    cache blobs rather than only the data_* metadata files. Keep this bounded
    so runtime scans do not walk every old cache object.
    """
    try:
        files = [path for path in directory.glob("f_*") if path.is_file()]
    except OSError:
        return []
    return sorted(files, key=lambda path: safe_mtime(path), reverse=True)[:limit]


def safe_mtime(path: Path):
    try:
        return path.stat().st_mtime
    except OSError:
        return 0.0


def scan_render_requests(path: Path, *, max_bytes=80_000_000):
    try:
        stat = path.stat()
        if stat.st_size > max_bytes:
            return []
        raw = read_bytes_shared(path, max_bytes=max_bytes)
    except OSError:
        return []
    text = raw.decode("utf-8", errors="ignore")
    return find_render_requests_in_text(text, path)


def find_render_requests_in_text(text: str, source_path: Path):
    requests = []
    pattern = r"http://127\.0\.0\.1:\d+/(?:pk_car|pk_helmet)\.png\?[^\\\x00\s\"'}<>]+"
    for match in re.finditer(pattern, text):
        url = match.group(0)
        context = text[max(0, match.start() - 500) : match.end() + 500]
        requests.append(render_request_from_url(url, source_path, context))
    return requests


def render_request_from_url(url: str, source_path: Path, context: str = ""):
    parsed = urlparse(url)
    query = parse_qs(parsed.query)
    kind = "car" if parsed.path.endswith("/pk_car.png") else "helmet"
    custom_paint = unquote(first_query_value(query, "carCustPaint") or "")
    return RenderRequest(
        url=url,
        kind=kind,
        source_path=source_path,
        car_path=clean_car_path(first_query_value(query, "carPath")),
        number=normalize_number(first_query_value(query, "number")),
        cust_id=first_possible_id(custom_paint),
        size=first_query_value(query, "size"),
    )


def unique_render_requests(requests):
    unique = []
    seen = set()
    for request in requests:
        if request.url in seen:
            continue
        unique.append(request)
        seen.add(request.url)
    return unique


def render_request_matches_driver(request: RenderRequest, driver):
    request_car_path = normalize_car_path(request.car_path)
    driver_car_path = normalize_car_path(driver["car_path"])

    if driver_car_path and request_car_path:
        if request_car_path not in driver_car_path and driver_car_path not in request_car_path:
            return False

    if request.cust_id and driver["cust_id"] and request.cust_id == driver["cust_id"]:
        return True

    return bool(request.number and driver["number"] and request.number == driver["number"])


def best_render_request(matches, driver):
    def score(request):
        value = 0
        if request.cust_id and request.cust_id == driver["cust_id"]:
            value += 10
        if request.number and request.number == driver["number"]:
            value += 5
        if request.size == "2":
            value += 2
        elif request.size == "0":
            value += 1
        return value

    return max(matches, key=score)


def synthesize_render_request_url(driver_info, driver, requests):
    """Build a fresh local iRacing car-render URL from live driver data.

    iRacing's Electron UI starts a local renderer and calls /pk_car.png with
    the car folder, local custom-paint path, and car number. If we have seen
    any recent pk_car request, we can reuse that local host/port and ask it to
    render the current driver's paint directly instead of waiting for the UI to
    request that exact driver first.
    """
    base_url = render_server_base_url(requests)
    if not base_url or not driver["car_path"]:
        return ""

    paint = find_car_paint(driver_info)
    if not paint:
        return ""

    query = {
        "size": "2",
        "carPath": render_car_path(driver_info, driver),
        "carCustPaint": str(paint.path),
    }
    if driver["number"]:
        query["number"] = driver["number"]
    return f"{base_url}/pk_car.png?{encode_render_query(query)}"


def render_server_base_url(requests):
    for request in requests or []:
        if request.kind != "car":
            continue
        parsed = urlparse(request.url)
        if parsed.scheme and parsed.netloc:
            return f"{parsed.scheme}://{parsed.netloc}"
    return ""


def render_car_path(driver_info, driver):
    raw = str(driver_info.get("car_path") or driver_info.get("CarPath") or "").strip().strip("\\/")
    if "\\" in raw or "/" in raw:
        return raw.replace("/", "\\")

    cleaned = driver["car_path"]
    if " " in cleaned:
        first, rest = cleaned.split(" ", 1)
        return f"{first}\\{rest}"
    return cleaned


def encode_render_query(query):
    return "&".join(
        f"{quote_plus(str(key))}={quote_plus(str(value))}"
        for key, value in query.items()
        if value not in (None, "")
    )


def normalize_driver_info(driver_info):
    return {
        "number": normalize_number(
            driver_info.get("number")
            or driver_info.get("CarNumber")
            or driver_info.get("car_number")
        ),
        "cust_id": normalize_digits(
            driver_info.get("cust_id")
            or driver_info.get("user_id")
            or driver_info.get("UserID")
            or driver_info.get("CustID")
        ),
        "car_path": clean_car_path(driver_info.get("car_path") or driver_info.get("CarPath")),
    }


def first_query_value(query, key):
    values = query.get(key) or []
    return str(values[0]) if values else ""


def first_possible_id(text):
    for pattern in (r"car(?:_num)?_(\d{4,10})", r"helmet_(\d{4,10})", r"suit_(\d{4,10})"):
        match = re.search(pattern, text, flags=re.IGNORECASE)
        if match:
            return match.group(1)
    return ""


def normalize_number(value):
    return str(value or "").strip().lstrip("0")


def normalize_digits(value):
    text = str(value or "").strip()
    if text.startswith("-"):
        return ""
    return "".join(ch for ch in text if ch.isdigit())


def clean_car_path(value):
    return unquote(str(value or "")).replace("\\", " ").replace("/", " ").strip()


def normalize_car_path(value):
    return re.sub(r"[^a-z0-9]+", "", str(value or "").lower())


def read_bytes_shared(path: Path, *, max_bytes: int | None = None):
    path = Path(path)
    try:
        data = path.read_bytes()
        return data[:max_bytes] if max_bytes else data
    except PermissionError:
        if os.name != "nt":
            raise
        return read_bytes_windows_shared(path, max_bytes=max_bytes)


def read_bytes_windows_shared(path: Path, *, max_bytes: int | None = None):
    kernel32 = ctypes.WinDLL("kernel32", use_last_error=True)
    handle = kernel32.CreateFileW(
        str(path),
        0x80000000,  # GENERIC_READ
        0x00000001 | 0x00000002 | 0x00000004,  # FILE_SHARE_READ/WRITE/DELETE
        None,
        3,  # OPEN_EXISTING
        0x00000080 | 0x08000000,  # NORMAL + SEQUENTIAL_SCAN
        None,
    )
    if handle == WINDOWS_ERROR_HANDLE:
        raise PermissionError(ctypes.get_last_error(), f"Could not open locked file: {path}")

    chunks = []
    total = 0
    chunk_size = 1024 * 1024
    try:
        while max_bytes is None or total < max_bytes:
            remaining = chunk_size if max_bytes is None else min(chunk_size, max_bytes - total)
            if remaining <= 0:
                break
            buffer = ctypes.create_string_buffer(remaining)
            bytes_read = ctypes.c_ulong(0)
            ok = kernel32.ReadFile(handle, buffer, remaining, ctypes.byref(bytes_read), None)
            if not ok:
                raise OSError(ctypes.get_last_error(), f"Could not read locked file: {path}")
            if bytes_read.value == 0:
                break
            chunks.append(buffer.raw[: bytes_read.value])
            total += bytes_read.value
    finally:
        kernel32.CloseHandle(handle)
    return b"".join(chunks)
