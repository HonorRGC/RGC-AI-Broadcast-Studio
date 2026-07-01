import os
import sys
import time

PROJECT_ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))

if PROJECT_ROOT not in sys.path:
    sys.path.insert(0, PROJECT_ROOT)

from broadcaster.telemetry import IRacingTelemetry


def safe_read(telemetry, key):
    try:
        return telemetry.ir[key]
    except Exception:
        return None


def get_leader(results, driver_lookup):
    if not results:
        return "Unknown"

    try:
        leader = sorted(results, key=lambda car: int(car.get("Position", 999)))[0]
    except Exception:
        return "Unknown"

    car_idx = leader.get("CarIdx")
    driver = driver_lookup.get(car_idx, {})

    name = driver.get("name", f"Car {car_idx}")
    number = driver.get("number", "?")

    return f"#{number} {name}"


def main():
    telemetry = IRacingTelemetry()

    print("=" * 70)
    print("RGC AI Broadcast Studio - iRacing Replay SDK Debug")
    print("=" * 70)
    print("Open an iRacing replay, press play, then run this tool.")
    print("Press CTRL+C to stop.")
    print("=" * 70)

    if not telemetry.startup():
        print("Could not start iRacing SDK.")
        return

    try:
        while True:
            if not telemetry.is_connected():
                print("Waiting for iRacing connection...")
                time.sleep(1)
                continue

            results = telemetry.get_results()
            driver_lookup = telemetry.get_driver_lookup()

            print()
            print("-" * 70)
            print(f"IsReplayPlaying  : {safe_read(telemetry, 'IsReplayPlaying')}")
            print(f"ReplayFrameNum   : {safe_read(telemetry, 'ReplayFrameNum')}")
            print(f"ReplaySessionTime: {safe_read(telemetry, 'ReplaySessionTime')}")
            print(f"Lap              : {telemetry.get_lap()}")
            print(f"Total Laps       : {telemetry.get_total_laps()}")
            print(f"Session Flags    : {telemetry.get_session_flags()}")
            print(f"Result Count     : {len(results)}")
            print(f"Leader           : {get_leader(results, driver_lookup)}")
            print("-" * 70)

            time.sleep(2)

    except KeyboardInterrupt:
        print()
        print("Replay SDK debug stopped.")


if __name__ == "__main__":
    main()