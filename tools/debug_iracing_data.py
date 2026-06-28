import irsdk

ir = irsdk.IRSDK()

print("Checking iRacing data...")

if ir.startup():
    print("Connected!")

    print("\nTrying common driver fields:")
    keys_to_check = [
        "SessionInfo",
        "DriverInfo",
        "CarIdx",
        "CarIdxPosition",
        "CarIdxClassPosition",
        "CarIdxLap",
        "CarIdxLapDistPct",
        "CarIdxTrackSurface",
        "CarIdxOnPitRoad",
    ]

    for key in keys_to_check:
        try:
            value = ir[key]
            print(f"\n{key}:")
            print(value)
        except Exception as e:
            print(f"\n{key}: not available")

else:
    print("Not connected to iRacing.")