import irsdk
import time

ir = irsdk.IRSDK()

print("=" * 60)
print("RGC AI Broadcaster")
print("=" * 60)

while True:

    if ir.startup():

        print("\nConnected to iRacing!\n")

        while ir.is_connected:

            print("-" * 60)

            print(f"Track Temperature : {ir['TrackTemp']}")
            print(f"Air Temperature   : {ir['AirTemp']}")
            print(f"Session Time      : {ir['SessionTime']:.1f}")
            print(f"Lap               : {ir['Lap']}")
            print(f"Speed             : {ir['Speed']:.2f} m/s")

            print("-" * 60)

            time.sleep(2)

    else:

        print("Waiting for iRacing...")
        time.sleep(5)