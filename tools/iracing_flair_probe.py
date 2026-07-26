from __future__ import annotations

import argparse
import json
import os
import sys
from urllib.error import HTTPError, URLError
from urllib.request import Request, urlopen


PROJECT_ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))

if PROJECT_ROOT not in sys.path:
    sys.path.insert(0, PROJECT_ROOT)

from broadcaster.telemetry import IRacingTelemetry


FLAIRS_URL = "https://members-ng.iracing.com/data/lookup/flairs"


def fetch_flairs(timeout=10):
    request = Request(
        FLAIRS_URL,
        headers={
            "Accept": "application/json",
            "User-Agent": "RGC-AI-Broadcast-Studio/1.0",
        },
    )
    with urlopen(request, timeout=timeout) as response:
        payload = response.read().decode("utf-8", errors="replace")
        return response.status, payload


def safe_flair_id(driver):
    value = driver.get("FlairID") or driver.get("flair_id") or ""
    return str(value).strip()


def safe_flair_name(driver):
    return str(driver.get("FlairName") or driver.get("flair_name") or "").strip()


def live_driver_flairs(limit):
    telemetry = IRacingTelemetry()
    if not telemetry.startup():
        return [], "Could not connect to iRacing telemetry."

    driver_info = telemetry.get_driver_info() or {}
    lookup = telemetry.get_driver_lookup()
    rows = []
    for raw_driver in driver_info.get("Drivers") or []:
        car_idx = raw_driver.get("CarIdx")
        if car_idx is None or int(car_idx) < 0:
            continue
        driver = lookup.get(car_idx, {}) or {}
        rows.append(
            {
                "car_idx": car_idx,
                "number": driver.get("number") or raw_driver.get("CarNumber") or "?",
                "name": driver.get("name") or raw_driver.get("UserName") or f"CarIdx {car_idx}",
                "flair_id": safe_flair_id(raw_driver) or safe_flair_id(driver),
                "flair_name": safe_flair_name(raw_driver) or safe_flair_name(driver),
            }
        )
        if len(rows) >= limit:
            break
    return rows, ""


def normalize_flair_records(payload):
    try:
        data = json.loads(payload)
    except json.JSONDecodeError:
        return []

    if isinstance(data, dict):
        for key in ("flairs", "data", "items"):
            if isinstance(data.get(key), list):
                data = data[key]
                break
        else:
            data = list(data.values())

    if not isinstance(data, list):
        return []

    rows = []
    for item in data:
        if not isinstance(item, dict):
            continue
        flair_id = (
            item.get("flair_id")
            or item.get("flairId")
            or item.get("id")
            or item.get("flairID")
            or ""
        )
        name = (
            item.get("flair_name")
            or item.get("flairName")
            or item.get("name")
            or item.get("display_name")
            or ""
        )
        code = (
            item.get("country_code")
            or item.get("countryCode")
            or item.get("code")
            or item.get("iso_code")
            or item.get("isoCode")
            or ""
        )
        icon = (
            item.get("icon")
            or item.get("icon_url")
            or item.get("image")
            or item.get("image_url")
            or item.get("flag")
            or item.get("flag_url")
            or ""
        )
        rows.append(
            {
                "flair_id": str(flair_id).strip(),
                "name": str(name).strip(),
                "country_code": str(code).strip(),
                "icon": str(icon).strip(),
                "raw_keys": sorted(item.keys()),
            }
        )
    return rows


def main():
    parser = argparse.ArgumentParser(
        description="Probe iRacing live driver FlairID/FlairName and the official /data/lookup/flairs endpoint."
    )
    parser.add_argument("--limit", type=int, default=30)
    parser.add_argument("--json", action="store_true", help="Print machine-readable JSON.")
    args = parser.parse_args()

    live_rows, live_error = live_driver_flairs(max(args.limit, 1))

    endpoint = {
        "url": FLAIRS_URL,
        "status": None,
        "error": "",
        "sample": [],
        "matched_live_flairs": [],
    }

    flair_rows = []
    try:
        status, payload = fetch_flairs()
        endpoint["status"] = status
        flair_rows = normalize_flair_records(payload)
        endpoint["sample"] = flair_rows[:10]
    except HTTPError as error:
        endpoint["status"] = error.code
        endpoint["error"] = (
            f"HTTP {error.code}. This usually means the iRacing data endpoint needs an authenticated "
            "iRacing data session, not just the live telemetry SDK."
        )
    except URLError as error:
        endpoint["error"] = f"Network error: {error.reason}"
    except Exception as error:
        endpoint["error"] = f"{type(error).__name__}: {error}"

    if flair_rows and live_rows:
        by_id = {row["flair_id"]: row for row in flair_rows if row.get("flair_id")}
        for driver in live_rows:
            match = by_id.get(str(driver.get("flair_id") or ""))
            if match:
                endpoint["matched_live_flairs"].append(
                    {
                        "driver": driver,
                        "flair_lookup": match,
                    }
                )

    result = {
        "live_driver_flairs": live_rows,
        "live_error": live_error,
        "iracing_flairs_endpoint": endpoint,
    }

    if args.json:
        print(json.dumps(result, indent=2))
        return

    print("=" * 80)
    print("RGC AI Broadcast Studio - iRacing Flair / Flag Probe")
    print("=" * 80)
    print("Live SDK driver flair fields:")
    if live_error:
        print(f"  {live_error}")
    elif not live_rows:
        print("  Connected, but no driver flair data is available yet.")
    else:
        for row in live_rows:
            print(
                f"  #{row['number']} {row['name']} | "
                f"FlairID={row['flair_id'] or 'MISSING'} | "
                f"FlairName={row['flair_name'] or 'MISSING'}"
            )

    print("-" * 80)
    print(f"iRacing flair lookup endpoint: {FLAIRS_URL}")
    if endpoint["status"]:
        print(f"  HTTP status: {endpoint['status']}")
    if endpoint["error"]:
        print(f"  {endpoint['error']}")
    elif endpoint["sample"]:
        print("  Endpoint responded. First flair records:")
        for row in endpoint["sample"]:
            print(
                f"    FlairID={row['flair_id'] or 'MISSING'} | "
                f"name={row['name'] or 'MISSING'} | "
                f"code={row['country_code'] or 'MISSING'} | "
                f"icon={row['icon'] or 'MISSING'}"
            )
    else:
        print("  Endpoint responded, but no recognizable flair records were parsed.")

    if endpoint["matched_live_flairs"]:
        print("-" * 80)
        print("Matched live drivers to flair lookup records:")
        for match in endpoint["matched_live_flairs"][:10]:
            driver = match["driver"]
            flair = match["flair_lookup"]
            print(f"  #{driver['number']} {driver['name']} -> {flair}")

    print("-" * 80)
    print(
        "If the endpoint returns HTTP 401/403, that is expected without a proper iRacing "
        "data API login. The live SDK still gives us FlairID and FlairName, which is enough "
        "for the driver card text and enough to wire official flags once we add authenticated lookup."
    )


if __name__ == "__main__":
    main()
