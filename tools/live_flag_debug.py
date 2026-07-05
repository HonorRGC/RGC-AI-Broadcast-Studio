import os
import sys
import time

PROJECT_ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))

if PROJECT_ROOT not in sys.path:
    sys.path.insert(0, PROJECT_ROOT)

from broadcaster.telemetry import IRacingTelemetry


INTERESTING_SDK_TERMS = [
    "incident",
    "penalty",
    "black",
    "dq",
    "disqual",
    "limit",
    "drive",
]

KNOWN_INCIDENT_KEYS = [
    "PlayerCarMyIncidentCount",
    "PlayerCarDriverIncidentCount",
    "PlayerCarTeamIncidentCount",
    "PlayerIncidents",
    "CarIdxIncidentCount",
    "CarIdxIncidents",
    "CarIdxMyIncidentCount",
    "CarIdxDriverIncidentCount",
]


def safe_read(telemetry, key):
    try:
        return telemetry.ir[key]
    except Exception:
        return None


def find_sdk_variable_names(telemetry):
    try:
        return list(telemetry.ir.var_headers_names)
    except Exception:
        return []


def find_interesting_sdk_variables(telemetry):
    names = find_sdk_variable_names(telemetry)
    interesting = []

    for name in names:
        lowered = str(name).lower()
        if any(term in lowered for term in INTERESTING_SDK_TERMS):
            interesting.append(name)

    return sorted(interesting, key=str.lower)


def short_value(value, max_items=12):
    if value is None:
        return "MISSING"

    if isinstance(value, (list, tuple)):
        sample = list(value)[:max_items]
        suffix = "" if len(value) <= max_items else f" ... ({len(value)} total)"
        return f"{sample}{suffix}"

    return str(value)


def print_incident_sdk_probe(telemetry):
    print("SDK Incident/Penalty Probe")
    print("-" * 80)

    all_names = find_sdk_variable_names(telemetry)
    print(f"Live SDK variables: {len(all_names)}")

    matches = find_interesting_sdk_variables(telemetry)
    if matches:
        print("Matching SDK variable names:")
        for name in matches:
            value = safe_read(telemetry, name)
            print(f"  {name}: {short_value(value)}")
    else:
        print("No live SDK variable names matched incident/penalty/search terms.")

    print()
    print("Known incident counters this project can use:")
    for key in KNOWN_INCIDENT_KEYS:
        print(f"  {key}: {short_value(safe_read(telemetry, key))}")

    print("-" * 80)


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
        0x00000100: "YELLOW_WAVING",
        0x00000200: "ONE_LAP_TO_GREEN",
        0x00004000: "CAUTION",
        0x00008000: "CAUTION_WAVING",
        0x00400000: "START_READY",
        0x00800000: "START_SET",
        0x01000000: "START_GO",

        # Older/constants currently in race_director.py
        0x00000010: "GREEN_OLD?",
        0x20000000: "START_READY_OLD?",
        0x40000000: "START_SET_OLD?",
        0x80000000: "START_GO_OLD?",
    }

    active = []

    for bit, name in known.items():
        if flags & bit:
            active.append(name)

    return active or ["NONE"]


def main():
    telemetry = IRacingTelemetry()

    print("=" * 80)
    print("RGC AI Broadcast Studio - Live Flag Debug")
    print("=" * 80)
    print("Run this during an AI race or live session.")
    print("Watch grid, parade lap, green flag, caution, one-to-green, restart, finish.")
    print("Press CTRL+C to stop.")
    print("=" * 80)

    while not telemetry.startup():
        print("Waiting for iRacing SDK...")
        time.sleep(2)

    print("Connected.")
    print("=" * 80)
    print_incident_sdk_probe(telemetry)

    last_flags = None
    last_state = None
    last_lap = None
    last_session_time = None

    try:
        while telemetry.is_connected():
            flags = telemetry.get_session_flags()
            state = safe_read(telemetry, "SessionState")
            lap = telemetry.get_lap()
            session_time = safe_read(telemetry, "SessionTime")
            pace_mode = safe_read(telemetry, "PaceMode")
            pace_flags = safe_read(telemetry, "CarIdxPaceFlags")

            changed = (
                flags != last_flags
                or state != last_state
                or lap != last_lap
            )

            if changed:
                print()
                print("-" * 80)
                print(f"SessionTime     : {session_time}")
                print(f"Lap             : {lap}")
                print(f"SessionState    : {state}")
                print(f"PaceMode        : {pace_mode}")
                print(f"SessionFlags Raw: {flags}")
                try:
                    print(f"SessionFlags Hex: 0x{int(flags or 0):08X}")
                except Exception:
                    print("SessionFlags Hex: UNKNOWN")
                print(f"Decoded Flags   : {', '.join(decode_flags(flags))}")

                if pace_flags is not None:
                    try:
                        print(f"PaceFlags Count : {len(pace_flags)}")
                        print(f"PaceFlags Sample: {list(pace_flags)[:10]}")
                    except Exception:
                        print(f"PaceFlags       : {pace_flags}")

                print("-" * 80)

                last_flags = flags
                last_state = state
                last_lap = lap
                last_session_time = session_time

            time.sleep(0.2)

    except KeyboardInterrupt:
        print()
        print("Live flag debug stopped.")


if __name__ == "__main__":
    main()
