import irsdk
import time

ir = irsdk.IRSDK()

if ir.startup():
    print("Connected. Watching caution-related data...")

    while ir.is_initialized and ir.is_connected:
        keys = [
            "SessionFlags",
            "PaceMode",
            "PaceFlags",
            "PaceCarIdx",
            "CarIdxTrackSurface",
            "CarIdxPosition",
            "CarIdxLap",
        ]

        for key in keys:
            try:
                print(f"{key}: {ir[key]}")
            except Exception:
                print(f"{key}: not available")

        print("-" * 60)
        time.sleep(2)
else:
    print("Not connected to iRacing.")