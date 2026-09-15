from __future__ import annotations

import argparse
import json

from broadcaster.telemetry import IRacingTelemetry


COUNTRY_FIELD_HINTS = (
    "country",
    "club",
    "region",
    "division",
    "license",
    "lic",
    "flair",
)


def interesting_driver_fields(driver):
    fields = {}
    for key, value in sorted((driver or {}).items(), key=lambda item: str(item[0]).lower()):
        key_text = str(key)
        key_lower = key_text.lower()
        if any(hint in key_lower for hint in COUNTRY_FIELD_HINTS):
            fields[key_text] = value
    return fields


def main():
    parser = argparse.ArgumentParser(
        description="Probe iRacing official/hosted driver country and club fields."
    )
    parser.add_argument(
        "--limit",
        type=int,
        default=40,
        help="Maximum number of drivers to print. Default: 40.",
    )
    parser.add_argument(
        "--json",
        action="store_true",
        help="Print compact JSON for copying back into Codex.",
    )
    args = parser.parse_args()

    telemetry = IRacingTelemetry()
    print("=" * 80)
    print("RGC AI Broadcast Studio - Driver Country Probe")
    print("=" * 80)
    print("Run this while you are loaded into an official, hosted, league, or AI session.")
    print("This is read-only. It only prints what the iRacing SDK exposes for each driver.")
    print("=" * 80)

    if not telemetry.startup():
        print("Could not connect to iRacing telemetry.")
        return

    driver_info = telemetry.get_driver_info() or {}
    raw_drivers = driver_info.get("Drivers") or []
    lookup = telemetry.get_driver_lookup()

    rows = []
    for raw_driver in raw_drivers:
        car_idx = raw_driver.get("CarIdx")
        if car_idx is None or int(car_idx) < 0:
            continue
        lookup_driver = lookup.get(car_idx, {})
        rows.append(
            {
                "car_idx": car_idx,
                "number": lookup_driver.get("number") or raw_driver.get("CarNumber") or "?",
                "name": lookup_driver.get("name") or raw_driver.get("UserName") or f"CarIdx {car_idx}",
                "lookup_country": lookup_driver.get("country", ""),
                "lookup_country_code": lookup_driver.get("country_code", ""),
                "lookup_country_name": lookup_driver.get("country_name", ""),
                "lookup_club": lookup_driver.get("club", ""),
                "lookup_club_id": lookup_driver.get("club_id", ""),
                "lookup_division": lookup_driver.get("division_name", ""),
                "raw_fields": interesting_driver_fields(raw_driver),
            }
        )

    rows = rows[: max(args.limit, 0)]

    if args.json:
        print(json.dumps(rows, indent=2, default=str))
        return

    if not rows:
        print("Connected, but no driver list is available yet.")
        return

    for row in rows:
        print("-" * 80)
        print(f"#{row['number']} {row['name']} (CarIdx {row['car_idx']})")
        print(f"  lookup country     : {row['lookup_country'] or 'MISSING'}")
        print(f"  lookup country code: {row['lookup_country_code'] or 'MISSING'}")
        print(f"  lookup country name: {row['lookup_country_name'] or 'MISSING'}")
        print(f"  lookup club        : {row['lookup_club'] or 'MISSING'}")
        print(f"  lookup club id     : {row['lookup_club_id'] or 'MISSING'}")
        print(f"  lookup division    : {row['lookup_division'] or 'MISSING'}")
        if row["raw_fields"]:
            print("  raw country/club-like SDK fields:")
            for key, value in row["raw_fields"].items():
                print(f"    {key}: {value}")
        else:
            print("  raw country/club-like SDK fields: none found")

    print("-" * 80)
    print(
        "If country is missing but club/region is present, send this output back and "
        "we can map those values into cleaner country text on the driver card."
    )


if __name__ == "__main__":
    main()
