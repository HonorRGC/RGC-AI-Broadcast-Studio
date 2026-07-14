from __future__ import annotations

import os
import shutil
from pathlib import Path

from production.car_paint_locator import find_car_paint


def default_preview_cache_dir():
    base = os.environ.get("LOCALAPPDATA") or os.environ.get("APPDATA")
    if base:
        return Path(base) / "RGC AI Broadcast Studio" / "paint_previews"
    return Path.home() / ".rgc_ai_broadcast_studio" / "paint_previews"


def build_car_paint_preview_url(
    driver_info,
    *,
    paint_roots=None,
    cache_dir=None,
    url_prefix="/paint-previews",
):
    """Return an overlay URL for a driver's local paint, creating a PNG if needed."""
    match = find_car_paint(driver_info, paint_roots=paint_roots)
    if not match:
        return ""

    preview_path = ensure_preview_file(match.path, driver_info, cache_dir=cache_dir)
    if not preview_path:
        return ""

    return f"{url_prefix.rstrip('/')}/{preview_path.name}"


def ensure_preview_file(paint_path, driver_info, *, cache_dir=None):
    paint_path = Path(paint_path)
    if not paint_path.exists() or not paint_path.is_file():
        return None

    cache_dir = Path(cache_dir or default_preview_cache_dir())
    cache_dir.mkdir(parents=True, exist_ok=True)

    cust_id = safe_filename_part(
        driver_info.get("cust_id")
        or driver_info.get("user_id")
        or driver_info.get("UserID")
        or driver_info.get("CustID")
        or "driver"
    )
    stat = paint_path.stat()
    output = cache_dir / f"car_{cust_id}_{stat.st_size}_{stat.st_mtime_ns}.png"
    if output.exists():
        return output

    if paint_path.suffix.lower() == ".png":
        shutil.copy2(paint_path, output)
        return output

    try:
        from PIL import Image
    except Exception:
        return None

    try:
        with Image.open(paint_path) as image:
            image = image.convert("RGBA")
            image.thumbnail((720, 360))
            image.save(output, "PNG")
    except Exception:
        return None

    return output if output.exists() else None


def safe_filename_part(value):
    text = str(value or "").strip()
    cleaned = "".join(ch for ch in text if ch.isalnum() or ch in ("-", "_"))
    return cleaned or "driver"

