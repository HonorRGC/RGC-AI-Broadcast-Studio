import json
import os
import sys
from collections import defaultdict


PROJECT_ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))

if PROJECT_ROOT not in sys.path:
    sys.path.insert(0, PROJECT_ROOT)


def safe_int(value, default=0):
    try:
        return int(value)
    except Exception:
        return default


def safe_float(value, default=0.0):
    try:
        return float(value)
    except Exception:
        return default


def get_race_lap(snapshot):
    laps = []

    lap = snapshot.get("lap")
    if lap is not None:
        laps.append(safe_int(lap))

    for car in snapshot.get("results", []) or []:
        laps_complete = car.get("LapsComplete")
        if laps_complete is not None:
            laps.append(safe_int(laps_complete))

    return max(laps) if laps else 0


def get_leader_car_idx(snapshot):
    results = snapshot.get("results", []) or []

    if not results:
        return None

    sorted_results = sorted(
        results,
        key=lambda car: safe_int(car.get("Position", 999)),
    )

    return sorted_results[0].get("CarIdx")


def count_pit_road_cars(snapshot):
    pit_status = snapshot.get("pit_road_status", []) or []

    count = 0

    for value in pit_status:
        if value:
            count += 1

    return count


def inspect_recording(filename):
    if not os.path.exists(filename):
        print(f"Recording not found: {filename}")
        return

    snapshot_count = 0
    first_timestamp = None
    last_timestamp = None

    first_lap = None
    last_lap = 0

    track_name = "Unknown Track"
    total_laps = 0
    max_drivers = 0

    caution_snapshots = 0
    pit_activity_snapshots = 0
    lead_changes = 0

    previous_leader = None

    positions_by_car = defaultdict(list)

    with open(filename, "r", encoding="utf-8") as file:
        for line in file:
            if not line.strip():
                continue

            snapshot = json.loads(line)
            snapshot_count += 1

            timestamp = snapshot.get("timestamp")

            if first_timestamp is None:
                first_timestamp = timestamp

            last_timestamp = timestamp

            track_info = snapshot.get("track_info", {}) or {}

            if track_info.get("track_name"):
                track_name = track_info.get("track_name")

            total_laps = snapshot.get("total_laps") or total_laps

            race_lap = get_race_lap(snapshot)

            if first_lap is None:
                first_lap = race_lap

            last_lap = max(last_lap, race_lap)

            results = snapshot.get("results", []) or []
            max_drivers = max(max_drivers, len(results))

            session_flags = safe_int(snapshot.get("session_flags", 0))

            # Broad caution flag check.
            if session_flags & 0x00000008 or session_flags & 0x00000100 or session_flags & 0x00004000 or session_flags & 0x00008000:
                caution_snapshots += 1

            pit_count = count_pit_road_cars(snapshot)

            if pit_count > 0:
                pit_activity_snapshots += 1

            leader = get_leader_car_idx(snapshot)

            if previous_leader is not None and leader is not None and leader != previous_leader:
                lead_changes += 1

            if leader is not None:
                previous_leader = leader

            for car in results:
                car_idx = car.get("CarIdx")
                position = car.get("Position")

                if car_idx is not None and position is not None:
                    positions_by_car[car_idx].append(safe_int(position))

    duration_seconds = 0

    if first_timestamp and last_timestamp:
        duration_seconds = int(last_timestamp - first_timestamp)

    biggest_gain = None
    biggest_loss = None

    for car_idx, positions in positions_by_car.items():
        if not positions:
            continue

        start_position = positions[0]
        end_position = positions[-1]
        movement = start_position - end_position

        if biggest_gain is None or movement > biggest_gain[1]:
            biggest_gain = (car_idx, movement)

        if biggest_loss is None or movement < biggest_loss[1]:
            biggest_loss = (car_idx, movement)

    print("=" * 70)
    print("RGC AI Broadcast Studio - Recording Inspector")
    print("=" * 70)
    print(f"File              : {filename}")
    print(f"Track             : {track_name}")
    print(f"Snapshots         : {snapshot_count}")
    print(f"Duration          : {format_duration(duration_seconds)}")
    print(f"First Race Lap    : {first_lap}")
    print(f"Last Race Lap     : {last_lap}")
    print(f"Total Laps        : {total_laps}")
    print(f"Max Drivers       : {max_drivers}")
    print(f"Caution Snapshots : {caution_snapshots}")
    print(f"Pit Activity      : {pit_activity_snapshots} snapshots")
    print(f"Lead Changes      : {lead_changes}")

    if biggest_gain:
        print(f"Biggest Gain      : CarIdx {biggest_gain[0]} gained {biggest_gain[1]} positions")

    if biggest_loss:
        print(f"Biggest Loss      : CarIdx {biggest_loss[0]} lost {abs(biggest_loss[1])} positions")

    print("=" * 70)


def format_duration(seconds):
    hours = seconds // 3600
    minutes = (seconds % 3600) // 60
    secs = seconds % 60

    if hours > 0:
        return f"{hours:02d}:{minutes:02d}:{secs:02d}"

    return f"{minutes:02d}:{secs:02d}"


def main():
    if len(sys.argv) < 2:
        print("Usage:")
        print("python tools/recording_inspector.py recordings/your_recording.jsonl")
        return

    inspect_recording(sys.argv[1])


if __name__ == "__main__":
    main()