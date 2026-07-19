from __future__ import annotations

import argparse
import csv
import hashlib
import json
import os
import re
import time
from dataclasses import dataclass
from pathlib import Path


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


def scan_text_file_for_patterns(path: Path, patterns=None, *, max_bytes=1_000_000):
    patterns = patterns or DEFAULT_PATTERNS
    try:
        raw = path.read_bytes()[:max_bytes]
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
        raw = path.read_bytes()
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
