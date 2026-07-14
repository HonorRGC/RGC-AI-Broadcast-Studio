from __future__ import annotations

import os
from dataclasses import dataclass
from pathlib import Path


BROWSER_READY_EXTENSIONS = {".png", ".jpg", ".jpeg", ".webp", ".gif"}
PAINT_EXTENSIONS = [".png", ".jpg", ".jpeg", ".webp", ".tga", ".mip"]


@dataclass(frozen=True)
class CarPaintMatch:
    path: Path
    source: str
    browser_ready: bool = False

    def to_dict(self):
        return {
            "path": str(self.path),
            "source": self.source,
            "browser_ready": self.browser_ready,
        }


def default_paint_roots(home: Path | None = None):
    """Likely local folders where iRacing/Trading Paints stores session paints."""
    home = home or Path.home()
    roots = []

    env_root = os.environ.get("IRACING_PAINT_ROOT", "").strip()
    if env_root:
        roots.append(Path(env_root).expanduser())

    roots.append(home / "Documents" / "iRacing" / "paint")

    for env_name in ("OneDrive", "OneDriveConsumer", "OneDriveCommercial"):
        one_drive = os.environ.get(env_name, "").strip()
        if one_drive:
            roots.append(Path(one_drive).expanduser() / "Documents" / "iRacing" / "paint")

    roots.append(home / "OneDrive" / "Documents" / "iRacing" / "paint")

    unique = []
    seen = set()
    for root in roots:
        resolved = Path(root)
        key = str(resolved).lower()
        if key not in seen:
            unique.append(resolved)
            seen.add(key)
    return unique


def normalize_cust_id(value):
    if value in (None, ""):
        return ""
    text = str(value).strip()
    if text.startswith("-"):
        return ""
    if text.endswith(".0"):
        text = text[:-2]
    return "".join(ch for ch in text if ch.isdigit())


def car_path_candidates(paint_root: Path, car_path: str):
    car_path = str(car_path or "").strip().strip("\\/")
    if not car_path:
        return []

    candidates = [paint_root / car_path]

    parts = [part for part in car_path.replace("\\", "/").split("/") if part]
    if parts:
        candidates.append(paint_root / parts[-1])

    safe_name = car_path.replace("\\", "_").replace("/", "_").replace(" ", "_")
    if safe_name:
        candidates.append(paint_root / safe_name)

    unique = []
    seen = set()
    for candidate in candidates:
        key = str(candidate).lower()
        if key not in seen:
            unique.append(candidate)
            seen.add(key)
    return unique


def candidate_filenames(cust_id):
    cust_id = normalize_cust_id(cust_id)
    if not cust_id:
        return []

    bases = [
        f"car_num_{cust_id}",
        f"car_{cust_id}",
        f"car_decal_{cust_id}",
    ]
    return [f"{base}{extension}" for base in bases for extension in PAINT_EXTENSIONS]


def find_car_paint(driver_info, paint_roots=None):
    """Find the best local paint file for a telemetry driver record.

    Trading Paints and iRacing custom paints are normally downloaded into
    Documents/iRacing/paint/<car folder>/car_<customer id>.tga or
    car_num_<customer id>.tga. This locator is intentionally read-only.
    """
    cust_id = normalize_cust_id(
        driver_info.get("cust_id")
        or driver_info.get("user_id")
        or driver_info.get("UserID")
        or driver_info.get("CustID")
        or driver_info.get("CustomerID")
    )
    if not cust_id:
        return None

    roots = [Path(root) for root in (paint_roots or default_paint_roots())]
    filenames = candidate_filenames(cust_id)
    car_path = (
        driver_info.get("car_path")
        or driver_info.get("CarPath")
        or driver_info.get("car_folder")
        or ""
    )

    for root in roots:
        if not root.exists():
            continue

        for directory in car_path_candidates(root, car_path):
            match = first_existing_file(directory, filenames)
            if match:
                return CarPaintMatch(
                    path=match,
                    source="car_path",
                    browser_ready=match.suffix.lower() in BROWSER_READY_EXTENSIONS,
                )

        match = scan_for_paint(root, filenames)
        if match:
            return CarPaintMatch(
                path=match,
                source="scan",
                browser_ready=match.suffix.lower() in BROWSER_READY_EXTENSIONS,
            )

    return None


def first_existing_file(directory: Path, filenames):
    if not directory.exists() or not directory.is_dir():
        return None
    for filename in filenames:
        path = directory / filename
        if path.exists() and path.is_file():
            return path
    return None


def scan_for_paint(root: Path, filenames):
    filename_set = {filename.lower() for filename in filenames}
    try:
        for path in root.rglob("*"):
            if path.is_file() and path.name.lower() in filename_set:
                return path
    except OSError:
        return None
    return None
