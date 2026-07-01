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


def decode_flags(flags):
    try:
        flags = int(flags or 0)
    except Exception:
        return ["UNKNOWN"]

    known = {
        0x00000001: "CHECKERED",
        0x00000002: "WHITE",
        0x00000004: "GREEN",
        0x00000008: "YELLOW",
        0x00000010: "RED",
        0x00000020: "BLUE",
        0x00000040: "DEBRIS",
        0x00000080: "CROSSED",
        0x00000100: "YELLOW_WAVING",
        0x00000200: "ONE_LAP_TO_GREEN",
        0x00000400: "GREEN_HELD",
        0x00000800: "TEN_TO_GO",
        0x00001000: "FIVE_TO_GO",
        0x00002000: "RANDOM_WAVING",
        0x00004000: "CAUTION",
        0x00008000: "CAUTION_WAVING",
        0x00010000: "BLACK",
        0x00020000: "DISQUALIFY",
        0x00040000: "SERVICIBLE",
        0x00080000: "FURLED",
        0x00100000: "REPAIR",
        0x00200000: "START_HIDDEN",
        0x00400000: "START_READY",
        0x00800000: "START_SET",
        0x01000000: "START_GO",
    }

    active = []

    for bit, name in known.items():
        if flags & bit:
            active.append(name)

    return active or ["NONE"]


def get_leader(results, driver_lookup):
    if not results:
        return "Unknown"

    try:
        leader = sorted(
            results,
            key=lambda car: int(car.get("Position", 999)),
        )[0]
    except Exception:
        return "Unknown"

    car_idx = leader.get("CarIdx")
    driver = driver_lookup.get(car_idx, {})

    return f"#{driver.get('number', '?')} {driver.get('name', f'Car {car_idx}')}"


def main():
    telemetry = IRacingTelemetry()

    print("=" * 80)
    print("RGC AI Broadcast Studio - Race Control Debug")
    print("=" * 80)
    print("Use this during replay OR live/spectator.")
    print("Watch the values during parade lap, green, caution, restart, and checkered.")
    print("Press CTRL+C to stop.")
    print("=" * 80)

    while not telemetry.startup():
        print("Waiting for iRacing SDK...")
        time.sleep(2)

    print("Connected.")
    print("=" * 80)

    try:
        while telemetry.is_connected():
            results = telemetry.get_results()
            driver_lookup = telemetry.get_driver_lookup()

            session_flags = telemetry.get_session_flags()

            print()
            print("-" * 80)
            print(f"IsReplayPlaying       : {safe_read(telemetry, 'IsReplayPlaying')}")
            print(f"ReplayFrameNum        : {safe_read(telemetry, 'ReplayFrameNum')}")
            print(f"ReplaySessionTime     : {safe_read(telemetry, 'ReplaySessionTime')}")
            print(f"SessionState          : {safe_read(telemetry, 'SessionState')}")
            print(f"SessionFlags Raw      : {session_flags}")
            print(f"SessionFlags Decoded  : {', '.join(decode_flags(session_flags))}")
            print(f"Lap                   : {telemetry.get_lap()}")
            print(f"Total Laps            : {telemetry.get_total_laps()}")
            print(f"Leader                : {get_leader(results, driver_lookup)}")
            print(f"Result Count          : {len(results)}")
            print("-" * 80)

            time.sleep(1)

    except KeyboardInterrupt:
        print()
        print("Race control debug stopped.")


if __name__ == "__main__":
    main()