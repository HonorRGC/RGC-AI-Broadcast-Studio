import os
import sys
import time

PROJECT_ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))

if PROJECT_ROOT not in sys.path:
    sys.path.insert(0, PROJECT_ROOT)

from replay.replay_telemetry import ReplayTelemetry


REPLAY_SPEED_SECONDS = 0.25


def get_leader(results, driver_lookup):
    if not results:
        return "Unknown"

    leader = sorted(results, key=lambda car: int(car.get("Position", 999)))[0]
    car_idx = leader.get("CarIdx")
    driver = driver_lookup.get(car_idx, {})

    name = driver.get("name", f"Car {car_idx}")
    number = driver.get("number", "?")

    return f"#{number} {name}"


def main():
    if len(sys.argv) < 2:
        print("Usage:")
        print("python replay/replay_player.py recordings/your_recording.jsonl")
        return

    filename = sys.argv[1]
    replay = ReplayTelemetry(filename)

    if not replay.startup():
        print("Replay could not start.")
        return

    print("=" * 60)
    print("RGC AI Broadcast Studio - Replay Player")
    print("=" * 60)
    print(f"File      : {filename}")
    print(f"Snapshots : {replay.snapshot_count()}")
    print("=" * 60)

    while replay.is_connected():
        results = replay.get_results()
        driver_lookup = replay.get_driver_lookup()

        lap = replay.get_lap()
        total_laps = replay.get_total_laps()
        track = replay.get_track_info().get("track_name", "Unknown Track")
        leader = get_leader(results, driver_lookup)

        print(
            f"[{replay.current_position():>5}/{replay.snapshot_count()}] "
            f"{track} | Lap {lap}/{total_laps} | Leader: {leader}"
        )

        replay.next_snapshot()
        time.sleep(REPLAY_SPEED_SECONDS)

    print("=" * 60)
    print("Replay complete.")
    print("=" * 60)


if __name__ == "__main__":
    main()