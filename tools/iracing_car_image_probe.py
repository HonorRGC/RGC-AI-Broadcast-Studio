from __future__ import annotations

import argparse
import csv
import ctypes
import hashlib
import json
import os
import re
import time
from dataclasses import dataclass
from pathlib import Path
from urllib.parse import parse_qs, unquote, urlparse


IMAGE_EXTENSIONS = {".png", ".jpg", ".jpeg", ".webp", ".gif", ".bmp", ".avif"}
TEXT_EXTENSIONS = {".log", ".txt", ".json", ".html", ".js", ".css", ".ldb", ".manifest"}
DEFAULT_PATTERNS = [
    "car info",
    "carinfo",
    "car model",
    "carmodel",
    "carviewer",
    "paint",
    "thumbnail",
    "screenshot",
    "render",
    "texture",
    "members-ng",
    ".png",
    ".jpg",
    ".jpeg",
    ".webp",
]
PNG_START = b"\x89PNG\r\n\x1a\n"
PNG_END = b"IEND\xaeB`\x82"
JPEG_START = b"\xff\xd8\xff"
JPEG_END = b"\xff\xd9"
WEBP_START = b"RIFF"
WEBP_MARKER = b"WEBP"
WINDOWS_ERROR_HANDLE = -1


@dataclass(frozen=True)
class ProbeRoot:
    label: str
    path: Path


@dataclass(frozen=True)
class RecentFile:
    path: Path
    modified_at: float
    size: int


@dataclass(frozen=True)
class PatternHit:
    path: Path
    pattern: str
    snippet: str


@dataclass(frozen=True)
class ExtractedImage:
    extension: str
    data: bytes
    offset: int
    context: str = ""


@dataclass(frozen=True)
class WrittenImage:
    path: Path
    source_path: Path
    extension: str
    offset: int
    size: int
    possible_ids: tuple[str, ...] = ()


@dataclass(frozen=True)
class RenderRequest:
    url: str
    kind: str
    source_path: Path
    car_path: str = ""
    number: str = ""
    cust_id: str = ""
    size: str = ""
    content_length: str = ""


def candidate_roots(home: Path | None = None, env: dict[str, str] | None = None):
    env = env or os.environ
    home = home or Path.home()
    roots = []

    appdata = env.get("APPDATA", "").strip()
    if appdata:
        roots.append(ProbeRoot("iRacing Electron app data", Path(appdata) / "iracing-electron"))

    local_appdata = env.get("LOCALAPPDATA", "").strip()
    if local_appdata:
        roots.append(
            ProbeRoot("iRacing Electron local app data", Path(local_appdata) / "iracing-electron")
        )

    roots.extend(
        [
            ProbeRoot("iRacing Documents logs", home / "Documents" / "iRacing" / "logs"),
            ProbeRoot("iRacing Documents paint", home / "Documents" / "iRacing" / "paint"),
            ProbeRoot(
                "iRacing OneDrive logs",
                home / "OneDrive" / "Documents" / "iRacing" / "logs",
            ),
            ProbeRoot(
                "iRacing OneDrive paint",
                home / "OneDrive" / "Documents" / "iRacing" / "paint",
            ),
        ]
    )

    for env_name in ("OneDrive", "OneDriveConsumer", "OneDriveCommercial"):
        one_drive = env.get(env_name, "").strip()
        if one_drive:
            roots.append(
                ProbeRoot(
                    f"iRacing {env_name} logs",
                    Path(one_drive) / "Documents" / "iRacing" / "logs",
                )
            )
            roots.append(
                ProbeRoot(
                    f"iRacing {env_name} paint",
                    Path(one_drive) / "Documents" / "iRacing" / "paint",
                )
            )

    unique = []
    seen = set()
    for root in roots:
        key = str(root.path).lower()
        if key not in seen:
            unique.append(root)
            seen.add(key)
    return unique


def recent_files(root: Path, *, minutes: int, now: float | None = None, max_files: int = 2000):
    now = time.time() if now is None else now
    cutoff = now - max(1, minutes) * 60
    found = []
    inspected = 0
    if not root.exists() or not root.is_dir():
        return found

    try:
        paths = root.rglob("*")
        for path in paths:
            if inspected >= max_files:
                break
            try:
                if not path.is_file():
                    continue
                inspected += 1
                stat = path.stat()
            except OSError:
                continue
            if stat.st_mtime >= cutoff:
                found.append(RecentFile(path=path, modified_at=stat.st_mtime, size=stat.st_size))
    except OSError:
        return found

    return sorted(found, key=lambda item: item.modified_at, reverse=True)


def image_like_files(files):
    return [item for item in files if item.path.suffix.lower() in IMAGE_EXTENSIONS]


def text_like_files(files, *, max_size=5_000_000):
    return [
        item
        for item in files
        if item.size <= max_size
        and (
            item.path.suffix.lower() in TEXT_EXTENSIONS
            or item.path.name.lower() in {"log", "current", "data_0"}
        )
    ]


def read_bytes_shared(path: Path, *, max_bytes: int | None = None):
    """Read a file even when Chromium/iRacing has it open on Windows."""
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
    generic_read = 0x80000000
    file_share_read = 0x00000001
    file_share_write = 0x00000002
    file_share_delete = 0x00000004
    open_existing = 3
    file_attribute_normal = 0x00000080
    file_flag_sequential_scan = 0x08000000

    handle = kernel32.CreateFileW(
        str(path),
        generic_read,
        file_share_read | file_share_write | file_share_delete,
        None,
        open_existing,
        file_attribute_normal | file_flag_sequential_scan,
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


def scan_text_file_for_patterns(path: Path, patterns=None, *, max_bytes=1_000_000):
    patterns = patterns or DEFAULT_PATTERNS
    try:
        raw = read_bytes_shared(path, max_bytes=max_bytes)
    except OSError:
        return []

    text = raw.decode("utf-8", errors="ignore")
    if not text.strip():
        return []

    hits = []
    lowered = text.lower()
    for pattern in patterns:
        index = lowered.find(pattern.lower())
        if index < 0:
            continue
        start = max(0, index - 90)
        end = min(len(text), index + len(pattern) + 140)
        snippet = re.sub(r"\s+", " ", text[start:end]).strip()
        hits.append(PatternHit(path=path, pattern=pattern, snippet=snippet))
    return hits


def detect_image_type(raw: bytes):
    if raw.startswith(PNG_START):
        return "png"
    if raw.startswith(JPEG_START):
        return "jpg"
    if raw.startswith(WEBP_START) and len(raw) >= 12 and raw[8:12] == WEBP_MARKER:
        return "webp"
    return ""


def context_near_offset(raw: bytes, offset: int, *, radius=1600):
    start = max(0, offset - radius)
    end = min(len(raw), offset + radius)
    text = raw[start:end].decode("utf-8", errors="ignore")
    return re.sub(r"\s+", " ", text).strip()


def possible_ids_from_context(context: str):
    if not context:
        return ()
    ids = set()
    for pattern in (
        r"(?:cust(?:omer)?[_-]?id|user[_-]?id|driver[_-]?id)[\"'=:\s]+(\d{4,10})",
        r"(?:car[_-]?id|carId)[\"'=:\s]+(\d{1,8})",
        r"car(?:_num)?_(\d{4,10})",
        r"helmet_(\d{4,10})",
        r"suit_(\d{4,10})",
    ):
        ids.update(re.findall(pattern, context, flags=re.IGNORECASE))
    return tuple(sorted(ids))


def find_render_requests_in_text(text: str, source_path: Path):
    requests = []
    for match in re.finditer(r"http://127\.0\.0\.1:\d+/(?:pk_car|pk_helmet)\.png\?[^\\\x00\s\"'}<>]+", text):
        url = match.group(0)
        requests.append(render_request_from_url(url, source_path, text[max(0, match.start() - 500) : match.end() + 500]))
    return requests


def render_request_from_url(url: str, source_path: Path, context: str = ""):
    parsed = urlparse(url)
    query = parse_qs(parsed.query)
    kind = "car" if parsed.path.endswith("/pk_car.png") else "helmet"
    car_path = unquote(first_query_value(query, "carPath")).replace("\\", " ").replace("/", " ")
    custom_paint = unquote(first_query_value(query, "carCustPaint") or first_query_value(query, "hlmtCustPaint"))
    ids = possible_ids_from_context(custom_paint)
    length_match = re.search(r"Content-Length:\s*(\d+)", context, flags=re.IGNORECASE)
    return RenderRequest(
        url=url,
        kind=kind,
        source_path=source_path,
        car_path=car_path,
        number=first_query_value(query, "number"),
        cust_id=ids[0] if ids else "",
        size=first_query_value(query, "size"),
        content_length=length_match.group(1) if length_match else "",
    )


def first_query_value(query, key):
    values = query.get(key) or []
    return str(values[0]) if values else ""


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


def unique_render_requests(requests):
    unique = []
    seen = set()
    for request in requests:
        key = request.url
        if key in seen:
            continue
        unique.append(request)
        seen.add(key)
    return unique


def scan_recent_render_requests(recent_by_root):
    requests = []
    for root, files in recent_by_root:
        if "electron" not in root.label.lower():
            continue
        for item in files:
            requests.extend(scan_render_requests(item.path))
    return unique_render_requests(requests)


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


def recent_cache_blobs(directory: Path, *, limit=250):
    try:
        files = [path for path in directory.glob("f_*") if path.is_file()]
    except OSError:
        return []
    return sorted(files, key=lambda path: safe_stat_mtime(path), reverse=True)[:limit]


def safe_stat_mtime(path: Path):
    try:
        return path.stat().st_mtime
    except OSError:
        return 0.0


def scan_render_requests_from_cache_metadata(roots):
    requests = []
    for root in roots:
        if "electron" not in root.label.lower():
            continue
        for path in cache_metadata_files(root.path):
            requests.extend(scan_render_requests(path))
    return unique_render_requests(requests)


def match_render_request_label(request: RenderRequest, live_drivers):
    if request.cust_id:
        label = match_driver_label((request.cust_id,), live_drivers)
        if label:
            return label

    request_number = normalize_number(request.number)
    request_car_path = normalize_car_path(request.car_path)
    candidates = []
    for driver in (live_drivers or {}).values():
        if request_number and normalize_number(driver.get("number")) != request_number:
            continue
        driver_car_path = normalize_car_path(driver.get("car_path"))
        if request_car_path and driver_car_path and request_car_path not in driver_car_path and driver_car_path not in request_car_path:
            continue
        candidates.append(driver)

    if len(candidates) == 1:
        driver = candidates[0]
        return f"#{driver.get('number', '?')} {driver.get('name', 'Unknown')}"
    if len(candidates) > 1:
        return "multiple possible live drivers"
    return ""


def normalize_number(value):
    return str(value or "").strip().lstrip("0")


def normalize_car_path(value):
    return re.sub(r"[^a-z0-9]+", "", str(value or "").lower())


def extract_images_from_bytes(raw: bytes):
    """Return (extension, image bytes) carved from a Chromium cache-like blob."""
    images = []

    offset = 0
    while True:
        start = raw.find(PNG_START, offset)
        if start < 0:
            break
        end = raw.find(PNG_END, start)
        if end < 0:
            break
        end += len(PNG_END)
        images.append(
            ExtractedImage(
                extension="png",
                data=raw[start:end],
                offset=start,
                context=context_near_offset(raw, start),
            )
        )
        offset = end

    offset = 0
    while True:
        start = raw.find(JPEG_START, offset)
        if start < 0:
            break
        end = raw.find(JPEG_END, start + len(JPEG_START))
        if end < 0:
            break
        end += len(JPEG_END)
        images.append(
            ExtractedImage(
                extension="jpg",
                data=raw[start:end],
                offset=start,
                context=context_near_offset(raw, start),
            )
        )
        offset = end

    offset = 0
    while True:
        start = raw.find(WEBP_START, offset)
        if start < 0:
            break
        if len(raw) < start + 12 or raw[start + 8 : start + 12] != WEBP_MARKER:
            offset = start + 4
            continue
        size = int.from_bytes(raw[start + 4 : start + 8], "little") + 8
        end = start + size
        if end > len(raw):
            break
        images.append(
            ExtractedImage(
                extension="webp",
                data=raw[start:end],
                offset=start,
                context=context_near_offset(raw, start),
            )
        )
        offset = end

    return images


def extract_images_from_file(path: Path, *, max_bytes=60_000_000):
    try:
        stat = path.stat()
        if stat.st_size > max_bytes:
            return []
        raw = read_bytes_shared(path, max_bytes=max_bytes)
    except OSError:
        return []

    image_type = detect_image_type(raw)
    if image_type:
        return [
            ExtractedImage(
                extension=image_type,
                data=raw,
                offset=0,
                context=context_near_offset(raw, 0),
            )
        ]
    return extract_images_from_bytes(raw)


def write_extracted_images(recent_items, output_dir: Path, *, max_images=100):
    output_dir.mkdir(parents=True, exist_ok=True)
    written = []
    seen_hashes = set()

    for item in recent_items:
        for extracted in extract_images_from_file(item.path):
            digest = hashlib.sha1(extracted.data).hexdigest()[:12]
            if digest in seen_hashes:
                continue
            seen_hashes.add(digest)
            safe_stem = re.sub(r"[^A-Za-z0-9_.-]+", "_", item.path.stem)[:40] or "cache"
            output = output_dir / f"{safe_stem}_{digest}.{extracted.extension}"
            output.write_bytes(extracted.data)
            written.append(
                WrittenImage(
                    path=output,
                    source_path=item.path,
                    extension=extracted.extension,
                    offset=extracted.offset,
                    size=len(extracted.data),
                    possible_ids=possible_ids_from_context(extracted.context),
                )
            )
            if len(written) >= max_images:
                return written
    return written


def write_manifest(written_images, output_dir: Path, live_drivers=None):
    live_drivers = live_drivers or {}
    json_path = output_dir / "manifest.json"
    csv_path = output_dir / "manifest.csv"
    rows = []
    for image in written_images:
        rows.append(
            {
                "image": str(image.path),
                "source_cache": str(image.source_path),
                "offset": image.offset,
                "extension": image.extension,
                "size": image.size,
                "possible_ids": ";".join(image.possible_ids),
                "matched_driver": match_driver_label(image.possible_ids, live_drivers),
            }
        )

    json_path.write_text(
        json.dumps(
            {
                "images": rows,
                "live_drivers": live_driver_rows(live_drivers),
            },
            indent=2,
        ),
        encoding="utf-8",
    )
    with csv_path.open("w", newline="", encoding="utf-8") as handle:
        fieldnames = [
            "image",
            "source_cache",
            "offset",
            "extension",
            "size",
            "possible_ids",
            "matched_driver",
        ]
        writer = csv.DictWriter(handle, fieldnames=fieldnames)
        writer.writeheader()
        writer.writerows(rows)
    return json_path, csv_path


def write_render_request_manifest(render_requests, output_dir: Path, live_drivers=None):
    output_dir.mkdir(parents=True, exist_ok=True)
    json_path = output_dir / "render_requests.json"
    csv_path = output_dir / "render_requests.csv"
    rows = []
    for request in render_requests:
        rows.append(
            {
                "kind": request.kind,
                "matched_driver": match_render_request_label(request, live_drivers),
                "number": request.number,
                "cust_id": request.cust_id,
                "car_path": request.car_path,
                "size": request.size,
                "content_length": request.content_length,
                "source_cache": str(request.source_path),
                "url": request.url,
            }
        )

    json_path.write_text(
        json.dumps(
            {
                "render_requests": rows,
                "live_drivers": live_driver_rows(live_drivers or {}),
            },
            indent=2,
        ),
        encoding="utf-8",
    )
    with csv_path.open("w", newline="", encoding="utf-8") as handle:
        fieldnames = [
            "kind",
            "matched_driver",
            "number",
            "cust_id",
            "car_path",
            "size",
            "content_length",
            "source_cache",
            "url",
        ]
        writer = csv.DictWriter(handle, fieldnames=fieldnames)
        writer.writeheader()
        writer.writerows(rows)
    return json_path, csv_path


def live_driver_rows(live_drivers):
    rows = []
    for car_idx, driver in sorted((live_drivers or {}).items(), key=lambda item: str(item[1].get("number", ""))):
        rows.append(
            {
                "car_idx": car_idx,
                "number": driver.get("number", ""),
                "name": driver.get("name", ""),
                "cust_id": driver.get("cust_id", ""),
                "car_id": driver.get("car_id", ""),
                "car_path": driver.get("car_path", ""),
            }
        )
    return rows


def match_driver_label(possible_ids, live_drivers):
    possible = {str(value) for value in possible_ids or () if str(value)}
    if not possible:
        return ""
    for driver in (live_drivers or {}).values():
        if str(driver.get("cust_id") or "") in possible or str(driver.get("user_id") or "") in possible:
            return f"#{driver.get('number', '?')} {driver.get('name', 'Unknown')}"
    return ""


def read_live_drivers():
    try:
        from broadcaster.telemetry import IRacingTelemetry
    except Exception as exc:
        return {}, f"Could not import iRacing telemetry: {exc}"

    telemetry = IRacingTelemetry()
    if not telemetry.startup():
        return {}, "Could not connect to iRacing telemetry."
    return telemetry.get_driver_lookup(), ""


def print_live_drivers(live_drivers, error=""):
    print("\nLive session drivers:")
    if error:
        print(f"  {error}")
        return
    if not live_drivers:
        print("  Connected, but no driver list is available yet.")
        return
    for driver in live_driver_rows(live_drivers)[:80]:
        print(
            "  "
            f"#{driver['number']} {driver['name']} | "
            f"cust_id={driver['cust_id']} | "
            f"car_id={driver['car_id']} | "
            f"car_path={driver['car_path']}"
        )


def print_render_requests(render_requests, live_drivers):
    print("\niRacing local render requests:")
    if not render_requests:
        print("  none found")
        return
    for request in render_requests[:80]:
        label = match_render_request_label(request, live_drivers)
        match_text = f" | match={label}" if label else ""
        id_text = f" | cust_id={request.cust_id}" if request.cust_id else ""
        print(
            "  "
            f"{request.kind.upper()} size={request.size or '?'} "
            f"#{request.number or '?'} {request.car_path or '?'}"
            f"{id_text}{match_text}"
        )
        print(f"    {request.url}")
    if len(render_requests) > 80:
        print(f"  ... {len(render_requests) - 80} more render request(s)")


def format_size(size):
    units = ["B", "KB", "MB", "GB"]
    value = float(size)
    for unit in units:
        if value < 1024 or unit == units[-1]:
            return f"{value:.1f} {unit}" if unit != "B" else f"{int(value)} B"
        value /= 1024
    return f"{size} B"


def format_age(modified_at, now=None):
    now = time.time() if now is None else now
    seconds = max(0, int(now - modified_at))
    if seconds < 60:
        return f"{seconds}s ago"
    minutes = seconds // 60
    if minutes < 60:
        return f"{minutes}m ago"
    return f"{minutes // 60}h {minutes % 60}m ago"


def print_recent_images(root: ProbeRoot, files, now):
    images = image_like_files(files)
    if not images:
        return 0
    print(f"\nRecent image files in {root.label}:")
    for item in images[:40]:
        print(f"  {format_age(item.modified_at, now):>8}  {format_size(item.size):>9}  {item.path}")
    if len(images) > 40:
        print(f"  ... {len(images) - 40} more image file(s)")
    return len(images)


def print_pattern_hits(root: ProbeRoot, files):
    hits = []
    for item in text_like_files(files):
        hits.extend(scan_text_file_for_patterns(item.path))

    if not hits:
        return 0
    print(f"\nPossible render/cache references in {root.label}:")
    for hit in hits[:30]:
        print(f"  {hit.path}")
        print(f"    matched: {hit.pattern}")
        print(f"    {hit.snippet}")
    if len(hits) > 30:
        print(f"  ... {len(hits) - 30} more reference(s)")
    return len(hits)


def main():
    parser = argparse.ArgumentParser(
        description=(
            "Look for iRacing UI rendered car-image cache clues after opening the "
            "iRacing Car Info or Car Model screen."
        )
    )
    parser.add_argument(
        "--minutes",
        type=int,
        default=60,
        help="Only show files modified in the last N minutes. Default: 60.",
    )
    parser.add_argument(
        "--extract-images",
        action="store_true",
        help="Extract embedded PNG/JPG/WebP files from recent iRacing UI cache files.",
    )
    parser.add_argument(
        "--session",
        action="store_true",
        help=(
            "Also read the live iRacing driver list so extracted cache images can be "
            "compared against current driver customer IDs."
        ),
    )
    parser.add_argument(
        "--output-dir",
        default="outputs/iracing_car_image_probe",
        help="Folder for --extract-images output. Default: outputs/iracing_car_image_probe.",
    )
    args = parser.parse_args()

    now = time.time()
    roots = candidate_roots()
    live_drivers = {}
    live_driver_error = ""
    if args.session:
        live_drivers, live_driver_error = read_live_drivers()

    print("=" * 80)
    print("RGC AI Broadcast Studio - iRacing 3D Car Image Probe")
    print("=" * 80)
    print("Open the iRacing car info/car model page first, then run this probe right away.")
    print("This is read-only. It only lists likely cache/log clues; it does not change files.")
    print("=" * 80)
    print("Folders checked:")

    total_images = 0
    total_hits = 0
    recent_by_root = []
    for root in roots:
        status = "FOUND" if root.path.exists() else "missing"
        print(f"  {root.path} [{status}]")

    if args.session:
        print_live_drivers(live_drivers, live_driver_error)

    for root in roots:
        if not root.path.exists():
            continue
        files = recent_files(root.path, minutes=args.minutes, now=now)
        if not files:
            continue
        recent_by_root.append((root, files))
        total_images += print_recent_images(root, files, now)
        total_hits += print_pattern_hits(root, files)

    if args.extract_images:
        all_recent = []
        for root, files in recent_by_root:
            if "electron" in root.label.lower():
                all_recent.extend(files)
        output_dir = Path(args.output_dir)
        extracted = write_extracted_images(all_recent, output_dir)
        print("\nExtracted cache images:")
        if extracted:
            manifest_json, manifest_csv = write_manifest(extracted, output_dir, live_drivers)
            for image in extracted[:50]:
                label = match_driver_label(image.possible_ids, live_drivers)
                suffix = f" | possible match: {label}" if label else ""
                ids = f" | nearby ids: {', '.join(image.possible_ids)}" if image.possible_ids else ""
                print(f"  {image.path}{ids}{suffix}")
            if len(extracted) > 50:
                print(f"  ... {len(extracted) - 50} more extracted image(s)")
            print(f"  manifest: {manifest_json}")
            print(f"  manifest CSV: {manifest_csv}")
        else:
            print("  none")

    render_requests = unique_render_requests(
        scan_recent_render_requests(recent_by_root)
        + scan_render_requests_from_cache_metadata(roots)
    )
    if render_requests:
        output_dir = Path(args.output_dir)
        render_json, render_csv = write_render_request_manifest(
            render_requests,
            output_dir,
            live_drivers,
        )
        print_render_requests(render_requests, live_drivers)
        print(f"  render request manifest: {render_json}")
        print(f"  render request CSV: {render_csv}")

    print("\n" + "-" * 80)
    print(f"Recent image files found: {total_images}")
    print(f"Possible cache/log references found: {total_hits}")
    if total_images == 0 and total_hits == 0:
        print(
            "No obvious saved render was found. That may mean the iRacing UI draws the car "
            "inside a live 3D/WebGL viewer instead of saving a PNG/JPG preview."
        )
    else:
        print(
            "If you see a likely PNG/JPG/WebP path above, open it and check whether it is "
            "the rendered car. If it is, we can wire that folder into the overlay."
        )


if __name__ == "__main__":
    main()
