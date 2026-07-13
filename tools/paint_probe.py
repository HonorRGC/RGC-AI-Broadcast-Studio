from __future__ import annotations

from pathlib import Path

from broadcaster.telemetry import IRacingTelemetry
from production.car_paint_locator import default_paint_roots, find_car_paint


def main():
    print("=" * 80)
    print("RGC AI Broadcast Studio - Paint Auto-Detect Probe")
    print("=" * 80)
    print("Run this while iRacing is open and Trading Paints has loaded the session.")
    print("This only reads local files. It does not upload, delete, or change paints.")
    print("=" * 80)

    roots = default_paint_roots()
    print("Paint folders checked:")
    for root in roots:
        status = "FOUND" if Path(root).exists() else "missing"
        print(f"  {root} [{status}]")
    print("-" * 80)

    telemetry = IRacingTelemetry()
    if not telemetry.startup():
        print("Could not connect to iRacing telemetry.")
        return

    drivers = telemetry.get_driver_lookup()
    if not drivers:
        print("Connected, but no driver list is available yet.")
        return

    found = 0
    missing = 0
    for car_idx, driver in sorted(drivers.items(), key=lambda item: str(item[1].get("number", ""))):
        match = find_car_paint(driver, roots)
        label = f"#{driver.get('number', '?')} {driver.get('name', f'CarIdx {car_idx}')}"
        cust_id = driver.get("cust_id") or "unknown"
        car_path = driver.get("car_path") or "unknown car folder"

        if match:
            found += 1
            ready = "browser-ready" if match.browser_ready else "needs preview conversion"
            print(f"FOUND   {label} | cust_id={cust_id} | {ready}")
            print(f"        {match.path}")
        else:
            missing += 1
            print(f"MISSING {label} | cust_id={cust_id} | car_path={car_path}")

    print("-" * 80)
    print(f"Paint matches: {found} found, {missing} missing")
    if missing:
        print("Tip: make sure Trading Paints Downloader is running and refresh/re-download current session paints.")


if __name__ == "__main__":
    main()

