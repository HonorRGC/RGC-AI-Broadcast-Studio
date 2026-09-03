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

IRACECONTROL_INSPIRED_KEYS = [
    "CarIdxSessionFlags",
    "CarIdxPaceFlags",
    "CarIdxTrackSurface",
    "CarIdxTrackSurfaceMaterial",
    "CarIdxLapDistPct",
    "CarIdxEstTime",
    "CarIdxOnPitRoad",
    "CarIdxFastRepairsUsed",
    "PitSvFlags",
    "PitSvFuel",
    "PitSvLFP",
    "PitSvLRP",
    "PitSvRFP",
    "PitSvRRP",
    "PitRepairLeft",
    "PitOptRepairLeft",
    "PitstopActive",
    "PitsOpen",
]

SCALAR_WATCH_KEYS = [
    "PitSvFlags",
    "PitSvFuel",
    "PitSvLFP",
    "PitSvLRP",
    "PitSvRFP",
    "PitSvRRP",
    "PitRepairLeft",
    "PitOptRepairLeft",
    "PitstopActive",
    "PitsOpen",
    "PlayerCarMyIncidentCount",
    "PlayerCarDriverIncidentCount",
    "PlayerCarTeamIncidentCount",
    "PlayerIncidents",
]

ARRAY_WATCH_KEYS = [
    "CarIdxSessionFlags",
    "CarIdxPaceFlags",
    "CarIdxTrackSurface",
    "CarIdxOnPitRoad",
    "CarIdxFastRepairsUsed",
]

WEEKEND_INFO_KEYS = [
    "Official",
    "LeagueID",
    "SeasonID",
    "SessionID",
    "SubSessionID",
    "RaceWeek",
    "EventType",
    "Category",
    "SimMode",
    "TeamRacing",
    "MinDrivers",
    "MaxDrivers",
    "TrackDisplayName",
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


def classify_weekend(weekend_info):
    official = normalize_bool(weekend_info.get("Official"))
    league_id = safe_int(weekend_info.get("LeagueID"), 0)

    if official is True:
        return "Official iRacing session"
    if league_id > 0:
        return f"League/hosted session (LeagueID {league_id})"
    if official is False:
        return "Hosted, test, or non-official session"
    return "Unknown session type"


def normalize_bool(value):
    if isinstance(value, bool):
        return value
    text = str(value).strip().lower()
    if text in ("1", "true", "yes", "y"):
        return True
    if text in ("0", "false", "no", "n"):
        return False
    return None


def safe_int(value, default=0):
    try:
        return int(value)
    except Exception:
        return default


def compact_value(value):
    if isinstance(value, float):
        return round(value, 3)
    return value


def scalar_watch_snapshot(telemetry):
    return {key: compact_value(safe_read(telemetry, key)) for key in SCALAR_WATCH_KEYS}


def array_watch_snapshot(telemetry):
    snapshot = {}
    for key in ARRAY_WATCH_KEYS:
        value = safe_read(telemetry, key)
        if isinstance(value, (list, tuple)):
            snapshot[key] = tuple(compact_value(item) for item in value)
        elif value is None:
            snapshot[key] = None
        else:
            try:
                snapshot[key] = tuple(compact_value(item) for item in list(value))
            except Exception:
                snapshot[key] = value
    return snapshot


def changed_array_indices(previous, current, limit=16):
    if previous is None or current is None:
        return []
    try:
        max_len = min(len(previous), len(current))
    except Exception:
        return []
    changes = []
    for index in range(max_len):
        if previous[index] != current[index]:
            changes.append((index, previous[index], current[index]))
            if len(changes) >= limit:
                break
    return changes


def driver_label(driver_lookup, car_idx):
    driver = (driver_lookup or {}).get(car_idx, {})
    number = driver.get("number") or "--"
    name = driver.get("name") or f"CarIdx {car_idx}"
    return f"#{number} {name} (CarIdx {car_idx})"


def track_surface_name(value):
    names = {
        -1: "not in world",
        0: "off track",
        1: "pit stall",
        2: "pit road",
        3: "racing surface",
    }
    return names.get(safe_int(value, value), str(value))


def should_print_event(
    recent_events,
    event_key,
    current_time=None,
    cooldown_seconds=4.0,
):
    if recent_events is None:
        return True

    try:
        event_time = float(current_time)
    except Exception:
        event_time = time.monotonic()

    last_time = recent_events.get(event_key)
    if last_time is not None and event_time - last_time < cooldown_seconds:
        return False

    recent_events[event_key] = event_time
    return True


def print_meaningful_array_events(
    key,
    changes,
    driver_lookup,
    recent_events=None,
    current_time=None,
):
    if not changes:
        return False

    printed = False
    for car_idx, old, new in changes:
        event_key = (key, car_idx, old, new)
        if not should_print_event(recent_events, event_key, current_time):
            continue

        driver = driver_label(driver_lookup, car_idx)
        if key == "CarIdxOnPitRoad":
            action = "entered pit road" if bool(new) else "left pit road"
            print(f"  Pit Road: {driver} {action}.")
            printed = True
        elif key == "CarIdxFastRepairsUsed":
            print(f"  Fast Repair: {driver} changed from {old} to {new}.")
            printed = True
        elif key == "CarIdxTrackSurface":
            old_name = track_surface_name(old)
            new_name = track_surface_name(new)
            if old_name == new_name:
                continue
            print(f"  Surface: {driver} moved {old_name} -> {new_name}.")
            printed = True
        elif key == "CarIdxSessionFlags":
            print(f"  Session Flags: {driver} changed {old} -> {new}.")
            printed = True
        elif key == "CarIdxPaceFlags":
            print(f"  Pace Flags: {driver} changed {old} -> {new}.")
            printed = True
    return printed


def print_watch_changes(
    previous_scalars,
    current_scalars,
    previous_arrays,
    current_arrays,
    driver_lookup=None,
    recent_events=None,
    current_time=None,
):
    scalar_changes = [
        (key, previous_scalars.get(key), value)
        for key, value in current_scalars.items()
        if previous_scalars.get(key) != value
    ]
    array_changes = []
    for key, value in current_arrays.items():
        changes = changed_array_indices(previous_arrays.get(key), value)
        if changes:
            array_changes.append((key, changes))

    meaningful_scalar_changes = [
        (key, old, new)
        for key, old, new in scalar_changes
        if key not in ("PitSvLFP", "PitSvLRP", "PitSvRFP", "PitSvRRP")
    ]

    if not meaningful_scalar_changes and not array_changes:
        return False

    print()
    print("Race Control Event Probe")
    print("-" * 80)
    for key, old, new in meaningful_scalar_changes:
        if key == "PitsOpen":
            print(f"  Pit Road: {'OPEN' if new else 'CLOSED'}")
        else:
            print(f"  {key}: {old} -> {new}")
    printed_array_event = False
    for key, changes in array_changes:
        printed_array_event = (
            print_meaningful_array_events(
                key,
                changes,
                driver_lookup,
                recent_events=recent_events,
                current_time=current_time,
            )
            or printed_array_event
        )
    if not meaningful_scalar_changes and not printed_array_event:
        print("  Only noisy/unusable watched values changed; baseline updated.")
    print("-" * 80)
    return True


def print_weekend_probe(telemetry):
    try:
        weekend_info = telemetry.get_weekend_info() or {}
    except Exception:
        weekend_info = {}

    print("Session Type Probe")
    print("-" * 80)
    print(f"Detected Type: {classify_weekend(weekend_info)}")

    if not weekend_info:
        print("WeekendInfo: MISSING")
        print("-" * 80)
        return

    print("WeekendInfo fields:")
    for key in WEEKEND_INFO_KEYS:
        if key in weekend_info:
            print(f"  {key}: {weekend_info.get(key)}")

    print("-" * 80)


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


def print_race_control_data_probe(telemetry):
    print("Race Control Data Probe")
    print("-" * 80)
    print("iRaceControl-inspired SDK variables this project may be able to use:")
    for key in IRACECONTROL_INSPIRED_KEYS:
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
    print_weekend_probe(telemetry)
    print()
    print_incident_sdk_probe(telemetry)
    print()
    print_race_control_data_probe(telemetry)

    last_flags = None
    last_state = None
    last_lap = None
    last_session_time = None
    last_scalar_watch = scalar_watch_snapshot(telemetry)
    last_array_watch = array_watch_snapshot(telemetry)
    recent_events = {}

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

            current_scalar_watch = scalar_watch_snapshot(telemetry)
            current_array_watch = array_watch_snapshot(telemetry)
            driver_lookup = telemetry.get_driver_lookup()
            if print_watch_changes(
                last_scalar_watch,
                current_scalar_watch,
                last_array_watch,
                current_array_watch,
                driver_lookup,
                recent_events=recent_events,
                current_time=session_time,
            ):
                last_scalar_watch = current_scalar_watch
                last_array_watch = current_array_watch

            time.sleep(0.2)

    except KeyboardInterrupt:
        print()
        print("Live flag debug stopped.")


if __name__ == "__main__":
    main()
