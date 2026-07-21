from __future__ import annotations

import json
import time
from urllib.error import URLError
from urllib.parse import urljoin
from urllib.request import urlopen


DEFAULT_BASE_URL = "http://127.0.0.1/SIMRacingApps/"
CACHE_TTL_SECONDS = 3.0
REQUEST_TIMEOUT_SECONDS = 0.35

_CACHE = {}


def build_sim_racing_apps_car_image_url(
    driver_info,
    *,
    base_url=DEFAULT_BASE_URL,
    now=None,
):
    """Return SimRacingApps' live iRacing car render URL for a CarIdx.

    SimRacingApps exposes the current-session render request as:
    /SIMRacingApps/Data/Car/I{car_idx}/ImageUrl

    That is better than guessing from stale iRacing Electron cache entries,
    because it is tied to the live session car index.
    """
    return build_sim_racing_apps_car_render_info(
        driver_info,
        base_url=base_url,
        now=now,
    ).get("image_url", "")


def build_sim_racing_apps_car_render_info(
    driver_info,
    *,
    base_url=DEFAULT_BASE_URL,
    now=None,
):
    """Return live car render image plus number styling from SimRacingApps."""
    car_idx = normalize_car_idx(
        driver_info.get("car_idx")
        or driver_info.get("CarIdx")
        or driver_info.get("id")
        or driver_info.get("Id")
    )
    if car_idx is None:
        return {}

    data = fetch_sim_racing_apps_data(
        f"Data/Car/I{car_idx}",
        base_url=base_url,
        now=now,
    )
    if data.get("State") != "NORMAL":
        return {}

    values = data.get("Value") if isinstance(data.get("Value"), dict) else {}
    image_url = resolve_sim_racing_apps_image_url(
        data_value(values, "ImageUrl"),
        base_url,
    )
    number_style = build_number_style(values)
    if not image_url and not number_style:
        return {}

    return {
        "image_url": image_url,
        "number_style": number_style,
    }


def resolve_sim_racing_apps_image_url(value, base_url=DEFAULT_BASE_URL):
    value = str(value or "").strip()
    if not value:
        return ""
    if value.startswith(("http://", "https://", "/")):
        return value
    return urljoin(ensure_base_url(base_url), value)


def build_number_style(values):
    style = {}
    text_color = rgb_int_to_hex(data_value(values, "ColorNumber"))
    background = rgb_int_to_hex(data_value(values, "ColorNumberBackground"))
    outline = rgb_int_to_hex(data_value(values, "ColorNumberOutline"))
    font = str(data_value(values, "NumberFont") or "").strip()
    slant = str(data_value(values, "NumberSlant") or "").strip().lower()

    if text_color:
        style["color"] = text_color
    if background:
        style["background"] = background
    if outline:
        style["outline"] = outline
    if font:
        style["font_family"] = font
    if slant and slant not in ("normal", "none"):
        style["font_style"] = "italic"
    return style


def data_value(values, key):
    item = values.get(key) if isinstance(values, dict) else None
    if not isinstance(item, dict) or item.get("State") != "NORMAL":
        return None
    return item.get("Value")


def rgb_int_to_hex(value):
    try:
        number = int(value)
    except (TypeError, ValueError):
        return ""
    if number < 0:
        return ""
    return f"#{number & 0xFFFFFF:06x}"


def fetch_sim_racing_apps_data(path, *, base_url=DEFAULT_BASE_URL, now=None):
    now = time.time() if now is None else float(now)
    url = urljoin(ensure_base_url(base_url), str(path).lstrip("/"))
    cached = _CACHE.get(url)
    if cached and now - cached["time"] <= CACHE_TTL_SECONDS:
        return dict(cached["data"])

    try:
        with urlopen(url, timeout=REQUEST_TIMEOUT_SECONDS) as response:
            raw = response.read(64_000).decode("utf-8", errors="ignore")
    except (OSError, TimeoutError, URLError):
        return {}

    try:
        data = json.loads(raw)
    except json.JSONDecodeError:
        return {}

    _CACHE[url] = {"time": now, "data": data}
    return dict(data)


def ensure_base_url(base_url):
    text = str(base_url or DEFAULT_BASE_URL).strip()
    return text if text.endswith("/") else f"{text}/"


def normalize_car_idx(value):
    if value in (None, ""):
        return None
    try:
        number = int(value)
    except (TypeError, ValueError):
        return None
    return number if number >= 0 else None
