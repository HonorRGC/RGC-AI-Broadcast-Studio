import pprint
import time

import irsdk


def main():
    ir = irsdk.IRSDK()

    print("=" * 70)
    print("RGC AI Broadcast Studio - iRacing SDK Inspector")
    print("=" * 70)

    print("Connecting to iRacing...")

    if not ir.startup():
        print("Could not connect to iRacing.")
        return

    time.sleep(1)

    print("Connected.")
    print()

    print("=" * 70)
    print("SESSION INFO")
    print("=" * 70)

    try:
        session_info = ir["SessionInfo"]
        pprint.pprint(session_info)
    except Exception as error:
        print(f"Could not read SessionInfo: {error}")

    print()
    print("=" * 70)
    print("COMMON TRACK / WEEKEND KEYS")
    print("=" * 70)

    keys_to_check = [
        "WeekendInfo",
        "TrackName",
        "TrackDisplayName",
        "TrackDisplayShortName",
        "TrackConfigName",
        "TrackCity",
        "TrackCountry",
        "TrackLength",
        "TrackType",
        "TrackDirection",
        "TrackWeatherType",
        "TrackSkies",
        "AirTemp",
        "TrackTemp",
        "TrackTempCrew",
        "WindVel",
        "WindDir",
        "RelativeHumidity",
        "FogLevel",
        "Skies",
        "WeatherType",
    ]

    for key in keys_to_check:
        try:
            value = ir[key]
            print(f"{key}: {value}")
        except Exception as error:
            print(f"{key}: unavailable ({error})")

    print()
    print("=" * 70)
    print("AVAILABLE SDK VARIABLE HEADERS")
    print("=" * 70)

    try:
        headers = ir.var_headers_names
        for name in sorted(headers):
            print(name)
    except Exception as error:
        print(f"Could not read variable headers: {error}")

    print()
    print("=" * 70)
    print("DONE")
    print("=" * 70)


if __name__ == "__main__":
    main()