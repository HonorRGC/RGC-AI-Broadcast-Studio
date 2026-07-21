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
    car_idx = normalize_car_idx(
        driver_info.get("car_idx")
        or driver_info.get("CarIdx")
        or driver_info.get("id")
        or driver_info.get("Id")
    )
    if car_idx is None:
        return ""

    data = fetch_sim_racing_apps_data(
        f"Data/Car/I{car_idx}/ImageUrl",
        base_url=base_url,
        now=now,
    )
    if data.get("State") != "NORMAL":
        return ""

    value = str(data.get("Value") or data.get("ValueFormatted") or "").strip()
    if not value:
        return ""
    if value.startswith(("http://", "https://", "/")):
        return value
    return urljoin(ensure_base_url(base_url), value)


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
