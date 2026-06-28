import irsdk
import pprint

ir = irsdk.IRSDK()

print("Checking iRacing session data...")

if ir.startup():
    session_info = ir["SessionInfo"]

    print("\nTop-level keys:")
    print(session_info.keys())

    print("\nLooking for DriverInfo:")
    if "DriverInfo" in session_info:
        pprint.pprint(session_info["DriverInfo"])
    else:
        print("DriverInfo not found.")

    print("\nFull SessionInfo sample:")
    pprint.pprint(session_info)
else:
    print("Not connected to iRacing.")