from __future__ import annotations

import argparse
import csv
import json
import re
from pathlib import Path


CAR_LABEL = re.compile(r"^Car\s+(\d+)$", re.IGNORECASE)


def load_capture_lookup(path: Path) -> tuple[dict[str, dict], str]:
    lookup: dict[str, dict] = {}
    track_name = ""
    with path.open("r", encoding="utf-8") as handle:
        for line in handle:
            try:
                frame = json.loads(line)
            except (json.JSONDecodeError, UnicodeDecodeError):
                continue
            current = frame.get("driver_lookup")
            if isinstance(current, dict) and len(current) >= len(lookup):
                lookup = current
            track = frame.get("track_info") or {}
            track_name = str(track.get("track_name") or track.get("TrackDisplayName") or track_name).strip()
    return lookup, track_name


def repair(profile: Path, capture: Path, round_number: int) -> int:
    results_path = profile / "results.json"
    payload = json.loads(results_path.read_text(encoding="utf-8-sig"))
    races = payload.get("races", payload if isinstance(payload, list) else [])
    target = next((race for race in races if int(race.get("round_number", 0)) == round_number), None)
    if target is None:
        raise RuntimeError(f"Round {round_number} was not found in {results_path}")

    lookup, track_name = load_capture_lookup(capture)
    repaired = 0
    for entry in target.get("entries", []):
        match = CAR_LABEL.match(str(entry.get("name") or "").strip())
        if not match:
            continue
        driver = lookup.get(match.group(1), {})
        name = str(driver.get("name") or driver.get("UserName") or "").strip()
        if not name or name.casefold() == "pace car":
            continue
        entry["name"] = name
        entry["car_number"] = str(driver.get("number") or driver.get("CarNumber") or "").strip()
        repaired += 1
    if track_name and not str(target.get("track_name") or "").strip():
        target["track_name"] = track_name

    results_path.write_text(json.dumps(payload, indent=2) + "\n", encoding="utf-8")

    drivers_path = profile / "drivers.csv"
    if drivers_path.exists():
        with drivers_path.open("r", newline="", encoding="utf-8-sig") as handle:
            reader = csv.DictReader(handle)
            fields = list(reader.fieldnames or [])
            rows = [row for row in reader if not CAR_LABEL.match(str(row.get("name") or "").strip())]
        with drivers_path.open("w", newline="", encoding="utf-8") as handle:
            writer = csv.DictWriter(handle, fieldnames=fields)
            writer.writeheader()
            writer.writerows(rows)
    return repaired


def main() -> None:
    parser = argparse.ArgumentParser(description="Repair CarIdx fallback labels using a saved broadcast capture.")
    parser.add_argument("profile", type=Path)
    parser.add_argument("capture", type=Path)
    parser.add_argument("round", type=int)
    args = parser.parse_args()
    count = repair(args.profile, args.capture, args.round)
    print(f"Repaired {count} result entries for Round {args.round}.")


if __name__ == "__main__":
    main()
