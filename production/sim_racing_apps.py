from __future__ import annotations

import json
import os
import time
from urllib.error import URLError
from urllib.parse import urljoin
from urllib.request import urlopen


DEFAULT_BASE_URL = os.getenv("SIM_RACING_APPS_BASE_URL", "http://127.0.0.1/SIMRacingApps/")
CACHE_TTL_SECONDS = 3.0
ROSTER_CACHE_TTL_SECONDS = 15.0
REQUEST_TIMEOUT_SECONDS = 0.35
MAX_ROSTER_CARS = 80
OFFLINE_RETRY_SECONDS = 45.0

_CACHE = {}
_ROSTER_CACHE = {}
_LAST_GOOD_RENDER_INFO = {}
_OFFLINE_UNTIL_BY_BASE = {}
CAR_FIELDS = (
    "Number",
    "DriverName",
    "Name",
    "DriverNameShort",
    "ImageUrl",
    "ColorNumber",
    "ColorNumberBackground",
    "ColorNumberOutline",
    "NumberFont",
    "NumberSlant",
)


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
    if not sim_racing_apps_enabled():
        return {}

    car_idx = normalize_car_idx(first_present(driver_info, "car_idx", "CarIdx", "id", "Id"))
    render_cache_key = driver_render_cache_key(driver_info)
    if sim_racing_apps_temporarily_offline(base_url, now=now):
        return last_good_render_info(render_cache_key)

    has_identity = bool(
        first_present(driver_info, "number", "car_number", "CarNumber")
        or first_present(driver_info, "name", "driver_name", "UserName")
    )

    data = {}
    if car_idx is not None:
        data = fetch_sim_racing_apps_car_data(car_idx, base_url=base_url, now=now)
        if data.get("State") == "NORMAL" and sim_racing_apps_car_matches(data, driver_info):
            return remember_render_info(
                render_cache_key,
                render_info_from_car_data(data, base_url=base_url),
            )

    matched_data = find_matching_sim_racing_apps_car_data(
        driver_info,
        base_url=base_url,
        now=now,
    )
    if matched_data:
        return remember_render_info(
            render_cache_key,
            render_info_from_car_data(matched_data, base_url=base_url),
        )

    if data.get("State") != "NORMAL":
        return last_good_render_info(render_cache_key)
    if has_identity:
        return {}
    return remember_render_info(
        render_cache_key,
        render_info_from_car_data(data, base_url=base_url),
    )


def driver_render_cache_key(driver_info):
    car_idx = normalize_car_idx(first_present(driver_info, "car_idx", "CarIdx", "id", "Id"))
    number = normalize_text(
        first_present(driver_info, "number", "car_number", "CarNumber")
    )
    name = normalize_text(
        first_present(driver_info, "name", "driver_name", "UserName")
    )
    if name or number:
        return (car_idx, number, name)
    if car_idx is not None:
        return (car_idx, "", "")
    return None


def remember_render_info(cache_key, render_info):
    render_info = normalize_render_info(render_info)
    if cache_key and (render_info.get("image_url") or render_info.get("number_style")):
        _LAST_GOOD_RENDER_INFO[cache_key] = dict(render_info)
    return render_info


def last_good_render_info(cache_key):
    cached = _LAST_GOOD_RENDER_INFO.get(cache_key) if cache_key else None
    return dict(cached) if cached else {}


def normalize_render_info(render_info):
    if not isinstance(render_info, dict):
        return {}
    image_url = str(render_info.get("image_url") or "").strip()
    number_style = render_info.get("number_style")
    number_style = dict(number_style) if isinstance(number_style, dict) else {}
    if not image_url and not number_style:
        return {}
    return {
        "image_url": image_url,
        "number_style": number_style,
    }


def build_sim_racing_apps_car_debug_info(
    driver_info,
    *,
    base_url=DEFAULT_BASE_URL,
    now=None,
):
    """Return match diagnostics for the current live SimRacingApps roster."""
    if not sim_racing_apps_enabled():
        return {
            "expected": {
                "car_idx": normalize_car_idx(first_present(driver_info, "car_idx", "CarIdx", "id", "Id")),
                "number": driver_info.get("number")
                or driver_info.get("car_number")
                or driver_info.get("CarNumber"),
                "name": driver_info.get("name")
                or driver_info.get("driver_name")
                or driver_info.get("UserName"),
            },
            "session_cars": 0,
            "direct": {"state": "DISABLED"},
            "direct_matches": False,
            "matched": {"state": "DISABLED"},
            "render_info": {},
        }
    car_idx = normalize_car_idx(first_present(driver_info, "car_idx", "CarIdx", "id", "Id"))
    direct = (
        fetch_sim_racing_apps_car_data(car_idx, base_url=base_url, now=now)
        if car_idx is not None
        else {}
    )
    direct_summary = summarize_car_data(direct)
    matched = find_matching_sim_racing_apps_car_data(
        driver_info,
        base_url=base_url,
        now=now,
    )
    matched_summary = summarize_car_data(matched)
    return {
        "expected": {
            "car_idx": car_idx,
            "number": driver_info.get("number")
            or driver_info.get("car_number")
            or driver_info.get("CarNumber"),
            "name": driver_info.get("name")
            or driver_info.get("driver_name")
            or driver_info.get("UserName"),
        },
        "session_cars": sim_racing_apps_session_car_count(base_url=base_url, now=now),
        "direct": direct_summary,
        "direct_matches": bool(
            direct.get("State") == "NORMAL"
            and sim_racing_apps_car_matches(direct, driver_info)
        ),
        "matched": matched_summary,
        "render_info": build_sim_racing_apps_car_render_info(
            driver_info,
            base_url=base_url,
            now=now,
        ),
    }


def render_info_from_car_data(data, *, base_url=DEFAULT_BASE_URL):
    values = data.get("Value") if isinstance(data.get("Value"), dict) else {}
    image_url = resolve_sim_racing_apps_image_url(
        data_value(values, "ImageUrl"),
        base_url,
    )
    image_url = ensure_car_specific_image_url(image_url, data.get("CarIdx"))
    number_style = build_number_style(values)
    if not image_url and not number_style:
        return {}

    return {
        "image_url": image_url,
        "number_style": number_style,
    }


def summarize_car_data(data):
    if data.get("State") != "NORMAL":
        return {"state": data.get("State", "MISSING")}
    values = data.get("Value") if isinstance(data.get("Value"), dict) else {}
    return {
        "state": data.get("State"),
        "name": data_value(values, "DriverName") or data_value(values, "Name"),
        "number": data_value(values, "Number"),
        "image_url": data_value(values, "ImageUrl"),
        "number_style": build_number_style(values),
    }


def find_matching_sim_racing_apps_car_data(driver_info, *, base_url=DEFAULT_BASE_URL, now=None):
    if not (
        first_present(driver_info, "number", "car_number", "CarNumber")
        or first_present(driver_info, "name", "driver_name", "UserName")
    ):
        return {}
    for data in sim_racing_apps_roster(base_url=base_url, now=now):
        if data.get("State") == "NORMAL" and sim_racing_apps_car_matches(data, driver_info):
            return data
    return {}


def sim_racing_apps_roster(*, base_url=DEFAULT_BASE_URL, now=None):
    now = time.time() if now is None else float(now)
    if not sim_racing_apps_enabled() or sim_racing_apps_temporarily_offline(
        base_url,
        now=now,
    ):
        return []
    key = ensure_base_url(base_url)
    cached = _ROSTER_CACHE.get(key)
    if cached and now - cached["time"] <= ROSTER_CACHE_TTL_SECONDS:
        return list(cached["data"])

    count = sim_racing_apps_session_car_count(base_url=base_url, now=now)
    if count <= 0:
        _ROSTER_CACHE[key] = {"time": now, "data": []}
        return []

    roster = []
    for car_idx in range(min(count, MAX_ROSTER_CARS)):
        data = fetch_sim_racing_apps_car_data(car_idx, base_url=base_url, now=now)
        if data.get("State") == "NORMAL":
            roster.append(data)
    _ROSTER_CACHE[key] = {"time": now, "data": roster}
    return list(roster)


def sim_racing_apps_session_car_count(*, base_url=DEFAULT_BASE_URL, now=None):
    if not sim_racing_apps_enabled() or sim_racing_apps_temporarily_offline(
        base_url,
        now=now,
    ):
        return 0
    data = fetch_sim_racing_apps_data("Data/Session/Cars", base_url=base_url, now=now)
    if data.get("State") != "NORMAL":
        return 0
    try:
        count = int(data.get("Value") or data.get("ValueFormatted") or 0)
    except (TypeError, ValueError):
        return 0
    return max(0, count)


def sim_racing_apps_car_matches(data, driver_info):
    values = data.get("Value") if isinstance(data.get("Value"), dict) else {}
    expected_number = normalize_text(
        driver_info.get("number")
        or driver_info.get("car_number")
        or driver_info.get("CarNumber")
    )
    expected_name = normalize_text(
        driver_info.get("name")
        or driver_info.get("driver_name")
        or driver_info.get("UserName")
    )
    actual_number = normalize_text(data_value(values, "Number"))
    actual_name = normalize_text(
        data_value(values, "DriverName")
        or data_value(values, "Name")
        or data_value(values, "DriverNameShort")
    )
    number_matches = not expected_number or expected_number == actual_number
    name_matches = not expected_name or names_match(expected_name, actual_name)
    return number_matches and name_matches


def fetch_sim_racing_apps_car_data(car_idx, *, base_url=DEFAULT_BASE_URL, now=None):
    """Fetch only the small per-car fields needed for render matching.

    The full /Data/Car/I# payload can be very large. Pulling the entire bundle
    can timeout or be truncated, which made live cars look missing even while
    SimRacingApps widgets were working.
    """
    values = {}
    any_ok = False
    for field_name in CAR_FIELDS:
        if not sim_racing_apps_enabled() or sim_racing_apps_temporarily_offline(
            base_url,
            now=now,
        ):
            break
        data = fetch_sim_racing_apps_data(
            f"Data/Car/I{car_idx}/{field_name}",
            base_url=base_url,
            now=now,
        )
        if data.get("State") == "ERROR":
            continue
        values[field_name] = data
        if data:
            any_ok = True
    if not any_ok:
        return {}
    return {
        "State": "NORMAL",
        "Value": values,
        "CarIdx": car_idx,
        "Name": f"Car/I{car_idx}",
    }


def first_present(mapping, *keys):
    for key in keys:
        value = mapping.get(key)
        if value is not None and value != "":
            return value
    return None


def names_match(expected, actual):
    if not expected or not actual:
        return False
    return expected == actual or expected in actual or actual in expected


def normalize_text(value):
    return " ".join(str(value or "").strip().lower().replace(".", "").split())


def resolve_sim_racing_apps_image_url(value, base_url=DEFAULT_BASE_URL):
    value = str(value or "").strip()
    if not value:
        return ""
    if value.startswith(("http://", "https://", "/")):
        return value
    return urljoin(ensure_base_url(base_url), value)


def ensure_car_specific_image_url(image_url, car_idx):
    image_url = str(image_url or "").strip()
    if not image_url or "pk_car.png" not in image_url or "?" in image_url:
        return image_url
    car_idx = normalize_car_idx(car_idx)
    if car_idx is None:
        return image_url
    separator = "&" if "?" in image_url else "?"
    return f"{image_url}{separator}car=I{car_idx}"


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
    if not isinstance(item, dict) or item.get("State") == "ERROR":
        return None
    value = item.get("Value")
    return value if value not in (None, "") else item.get("ValueFormatted")


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
    if not sim_racing_apps_enabled() or sim_racing_apps_temporarily_offline(
        base_url,
        now=now,
    ):
        return {}
    base_url = ensure_base_url(base_url)
    url = urljoin(base_url, str(path).lstrip("/"))
    cached = _CACHE.get(url)
    if cached and now - cached["time"] <= CACHE_TTL_SECONDS:
        return dict(cached["data"])

    try:
        with urlopen(url, timeout=REQUEST_TIMEOUT_SECONDS) as response:
            raw = response.read(64_000).decode("utf-8", errors="ignore")
    except (OSError, TimeoutError, URLError):
        mark_sim_racing_apps_offline(base_url, now=now)
        _CACHE[url] = {"time": now, "data": {}}
        return {}

    try:
        data = json.loads(raw)
    except json.JSONDecodeError:
        return {}

    _CACHE[url] = {"time": now, "data": data}
    return dict(data)


def sim_racing_apps_enabled():
    return str(os.getenv("USE_SIM_RACING_APPS", "true") or "true").strip().lower() in {
        "1",
        "true",
        "yes",
        "on",
    }


def sim_racing_apps_temporarily_offline(base_url=DEFAULT_BASE_URL, *, now=None):
    now = time.time() if now is None else float(now)
    offline_until = _OFFLINE_UNTIL_BY_BASE.get(ensure_base_url(base_url), 0.0)
    return now < offline_until


def mark_sim_racing_apps_offline(base_url=DEFAULT_BASE_URL, *, now=None):
    now = time.time() if now is None else float(now)
    _OFFLINE_UNTIL_BY_BASE[ensure_base_url(base_url)] = now + OFFLINE_RETRY_SECONDS


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
