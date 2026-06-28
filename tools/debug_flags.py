import irsdk
import time

ir = irsdk.IRSDK()

if ir.startup():
    print("Connected to iRacing. Watching flags...")

    while ir.is_initialized and ir.is_connected:
        print("SessionFlags:", ir["SessionFlags"])
        print("CamCarIdx:", ir["CamCarIdx"])
        print("-" * 40)
        time.sleep(2)
else:
    print("Not connected to iRacing.")