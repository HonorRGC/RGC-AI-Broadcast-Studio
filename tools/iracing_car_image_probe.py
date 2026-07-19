from __future__ import annotations

import argparse
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
    args = parser.parse_args()

    now = time.time()
    roots = candidate_roots()

    print("=" * 80)
    print("RGC AI Broadcast Studio - iRacing 3D Car Image Probe")
    print("=" * 80)
    print("Open the iRacing car info/car model page first, then run this probe right away.")
    print("This is read-only. It only lists likely cache/log clues; it does not change files.")
    print("=" * 80)
    print("Folders checked:")

    total_images = 0
    total_hits = 0
    for root in roots:
        status = "FOUND" if root.path.exists() else "missing"
        print(f"  {root.path} [{status}]")

    for root in roots:
        if not root.path.exists():
            continue
        files = recent_files(root.path, minutes=args.minutes, now=now)
        if not files:
            continue
        total_images += print_recent_images(root, files, now)
        total_hits += print_pattern_hits(root, files)

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
