import os
import sys

# -------------------------------------------------------------
# Allow this tool to be run from anywhere inside the project.
# -------------------------------------------------------------
PROJECT_ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))

if PROJECT_ROOT not in sys.path:
    sys.path.insert(0, PROJECT_ROOT)

import json
import time
from datetime import datetime

from broadcaster.telemetry import IRacingTelemetry


RECORDING_INTERVAL_SECONDS = 1.0


def make_recording_filename(track_name):
    safe_track = str(track_name or "unknown_track")
    safe_track = (
        safe_track.lower()
        .replace(" ", "_")
        .replace("/", "_")
        .replace("\\", "_")
    )

    timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")

    return os.path.join("recordings", f"{safe_track}_{timestamp}.jsonl")


def build_snapshot(telemetry):
    return {
        "timestamp": time.time(),
        "lap": telemetry.get_lap(),
        "total_laps": telemetry.get_total_laps(),
        "session_flags": telemetry.get_session_flags(),
        "track_info": telemetry.get_track_info(),
        "results": telemetry.get_results(),
        "driver_lookup": telemetry.get_driver_lookup(),
        "pit_road_status": telemetry.get_car_idx_on_pit_road(),
        "track_surface": telemetry.get_car_idx_track_surface(),
        "track_surface_material": telemetry.get_car_idx_track_surface_material(),
        "lap_dist_pct": telemetry.get_car_idx_lap_dist_pct(),
        "est_time": telemetry.get_car_idx_est_time(),
    }


def main():
    os.makedirs("recordings", exist_ok=True)

    telemetry = IRacingTelemetry()

    print("=" * 60)
    print("RGC AI Broadcast Studio - Telemetry Recorder")
    print("=" * 60)
    print()

    print("Connecting to iRacing...")

    while not telemetry.startup():
        print("Waiting for iRacing...")
        time.sleep(5)

    print("Connected!")

    track_info = telemetry.get_track_info()

    filename = make_recording_filename(
        track_info.get("track_name", "unknown_track")
    )

    print()
    print(f"Recording Track : {track_info.get('track_name')}")
    print(f"Saving File     : {filename}")
    print()
    print("Recording...")
    print("Press CTRL+C at any time to stop.")
    print("=" * 60)

    snapshot_count = 0

    try:
        with open(filename, "w", encoding="utf-8") as file:

            while telemetry.is_connected():

                snapshot = build_snapshot(telemetry)

                file.write(json.dumps(snapshot) + "\n")

                snapshot_count += 1

                if snapshot_count % 10 == 0:
                    print(
                        f"Snapshots: {snapshot_count:6d} | "
                        f"Lap {snapshot['lap']}"
                    )

                time.sleep(RECORDING_INTERVAL_SECONDS)

    except KeyboardInterrupt:
        print()
        print("Recording stopped by user.")

    print()
    print("=" * 60)
    print("Recording Complete")
    print("=" * 60)
    print(f"Snapshots Recorded : {snapshot_count}")
    print(f"Saved To           : {filename}")
    print("=" * 60)


if __name__ == "__main__":
    main()