"""Build a fact-based, editable highlights programme from recorded telemetry."""
import hashlib
import json
import time
from pathlib import Path

from replay.replay_reader import ReplayReader

CAUTION = 0x8 | 0x100 | 0x4000 | 0x8000


def number(value, default=0):
    try:
        return int(value)
    except (TypeError, ValueError):
        return default


def race_lap(snapshot):
    completed = max((number(row.get("LapsComplete", row.get("Lap", 0))) for row in snapshot.results), default=0)
    lap = max(number(snapshot.lap), completed + int(snapshot.session_state == 4))
    return min(lap, snapshot.total_laps) if snapshot.total_laps > 0 else lap


def ordered(snapshot):
    rows = [dict(row) for row in snapshot.results if row.get("CarIdx") is not None]
    base = int(any(number(row.get("Position"), -1) == 0 for row in rows))
    for row in rows:
        row["position"] = number(row.get("Position"), -1) + base
    return sorted((row for row in rows if row["position"] > 0), key=lambda row: row["position"])


def driver(snapshot, idx):
    info = snapshot.driver_lookup.get(idx) or snapshot.driver_lookup.get(str(idx)) or {}
    return {"car_idx": idx, "driver_name": info.get("name") or f"Car {idx}",
            "car_number": str(info.get("number") or ""), "car_image_url": info.get("car_image_url", ""),
            "render_driver": dict(info, car_idx=idx)}


def pit(snapshot, idx):
    return isinstance(idx, int) and 0 <= idx < len(snapshot.pit_road_status) and bool(snapshot.pit_road_status[idx])


def caution_slowdown_candidate(samples, caution_time):
    """Find an isolated, sustained pre-yellow slowdown; do not infer contact or fault."""
    import math
    from statistics import median
    def speed(snapshot, idx):
        value = snapshot.car_speed_mph.get(idx, snapshot.car_speed_mph.get(str(idx)))
        try:
            value = float(value)
            return value if math.isfinite(value) and 0 <= value <= 300 else None
        except (TypeError, ValueError):
            return None
    best = None
    for i, current in enumerate(samples):
        if not caution_time - 20 <= current.session_time < caution_time or current.session_flags & CAUTION:
            continue
        prior = next((s for s in reversed(samples[:i]) if .8 <= current.session_time - s.session_time <= 2), None)
        following = next((s for s in samples[i + 1:] if .8 <= s.session_time - current.session_time <= 2
                          and s.session_time < caution_time), None)
        if prior is None or following is None:
            continue
        for row in ordered(current):
            idx = row["CarIdx"]
            if any(pit(s, idx) for s in samples if current.session_time - 3 <= s.session_time <= current.session_time + 10):
                continue
            before, now, after = speed(prior, idx), speed(current, idx), speed(following, idx)
            if before is None or now is None or after is None or before < 60 or before - now < 35 or now > before * .55 or after > before * .65:
                continue
            peers = []
            for other in ordered(current):
                other_idx = other["CarIdx"]
                old, new = speed(prior, other_idx), speed(current, other_idx)
                if other_idx != idx and not pit(current, other_idx) and old is not None and new is not None and old >= 60:
                    peers.append(new / old)
            if not peers or median(peers) < .8:
                continue
            off_track = (idx < len(current.track_surface) and idx < len(prior.track_surface)
                         and prior.track_surface[idx] == 3 and current.track_surface[idx] == 0)
            score = (before - now) / before + .5 * off_track - (caution_time - current.session_time) * .005
            if best is None or score > best[0]:
                best = (score, {"snapshot": current, "car_idx": idx, "before": before, "speed": now,
                                "off_track": off_track, "start": prior.session_time - 8})
    return best[1] if best else None


def build_recap(race, grid, finish, events):
    """Use final classifications and recorded race statistics for the closing slate."""
    import math
    if finish is None:
        return {}
    final = race[-1]
    results = []
    fastest, led = [], {}
    for row in ordered(final):
        idx = row["CarIdx"]
        start = grid.get(idx, {}).get("position")
        results.append(dict(driver(final, idx), position=row["position"], started=start,
                            change=start - row["position"] if start else None))
    for snapshot in race:
        for row in snapshot.results:
            idx = row.get("CarIdx")
            for key in ("FastestTime", "BestLapTime", "FastestLapTime", "BestTime"):
                try:
                    value = float(row.get(key, 0))
                except (TypeError, ValueError):
                    continue
                if math.isfinite(value) and 0 < value < 10000:
                    fastest.append((value, idx))
                    break
            for key in ("LapsLed", "LedLaps", "LeaderLaps"):
                if row.get(key) is not None:
                    led[idx] = max(led.get(idx, 0), number(row[key]))
    observed_led = False
    if not led or max(led.values(), default=0) == 0:
        observed_led = True
        led = {}
        previous = None
        for snapshot in race:
            if snapshot.session_time > finish.session_time:
                break
            rows = ordered(snapshot)
            if not rows:
                continue
            completed = max(number(row.get("LapsComplete")) for row in rows)
            if previous and 0 < snapshot.session_time - previous[0] <= 2 and completed == previous[1] + 1:
                idx = rows[0]["CarIdx"]
                led[idx] = led.get(idx, 0) + 1
            previous = (snapshot.session_time, completed)
    stats = []
    if fastest:
        value, idx = min(fastest, key=lambda item: item[0])
        minutes, seconds = divmod(value, 60)
        stats.append({"label": "Fastest lap", "driver": driver(final, idx)["driver_name"],
                      "value": f"{int(minutes)}:{seconds:06.3f}"})
    else:
        stats.append({"label": "Fastest lap", "driver": "", "value": "Not recorded"})
    changes = [row for row in results if row["change"] is not None]
    for label, candidates, choose in (("Biggest mover", [r for r in changes if r["change"] > 0], max),
                                       ("Biggest loser", [r for r in changes if r["change"] < 0], min)):
        if candidates:
            change = choose(row["change"] for row in candidates)
            names = ", ".join(row["driver_name"] for row in candidates if row["change"] == change)
            stats.append({"label": label, "driver": names, "value": f"{change:+d} places"})
        else:
            stats.append({"label": label, "driver": "", "value": "No change" if changes else "Not recorded"})
    stats.append({"label": "Cautions", "driver": "", "value": str(sum(e["kind"] == "caution" for e in events))})
    if led and max(led.values()) > 0:
        count = max(led.values())
        stats.append({"label": "Most laps led", "driver": ", ".join(driver(final, idx)["driver_name"] for idx, value in led.items() if value == count), "value": str(count) + (" observed" if observed_led else "")})
    else:
        stats.append({"label": "Most laps led", "driver": "", "value": "Not recorded"})
    order = {"Fastest lap": 0, "Biggest mover": 1, "Cautions": 2, "Most laps led": 3, "Biggest loser": 4}
    stats.sort(key=lambda stat: order[stat["label"]])
    return {"results": results, "podium": [row for row in results if row["position"] <= 3], "stats": stats}


def group_highlight_events(events):
    """Keep each clip on one subject instead of chaining overlapping windows."""
    clips = []
    passes = {"overtake", "lead_change"}
    incidents = {"incident", "incident_marker"}
    for event in sorted(events, key=lambda e: (e["kind"] == "finish", e["start"])):
        clip = clips[-1] if clips else None
        merge = False
        if clip and len(clip["events"]) == 1 and event["start"] <= clip["end"] + 2:
            prior = clip["events"][0]
            span = max(clip["end"], event["end"]) - clip["start"]
            merge_passes = (prior["kind"] in passes and event["kind"] in passes
                            and abs(prior["time"] - event["time"]) <= 20
                            and abs(prior["lap"] - event["lap"]) <= 1 and span <= 55)
            incident_and_yellow = ((prior["kind"] in incidents and event["kind"] == "caution") or
                                   (event["kind"] in incidents and prior["kind"] == "caution"))
            merge_caution = (incident_and_yellow and prior.get("car_idx") == event.get("car_idx")
                             and abs(prior["time"] - event["time"]) <= 25 and span <= 60)
            merge = merge_passes or merge_caution
        if merge:
            clip["end"] = max(clip["end"], event["end"])
            clip["events"].append(event)
            if event["kind"] in incidents:
                clip["car_idx"] = event["car_idx"]
        else:
            clips.append({"start": event["start"], "end": event["end"], "car_idx": event["car_idx"], "events": [event]})
    return clips


def read_highlight_snapshots(capture):
    """Stream the capture; retain action samples instead of the full 10 Hz race."""
    kept, qualifying, last = [], {}, None
    previous_by_session = {}
    last_incidents = {}
    for snapshot in ReplayReader(capture).iter_snapshots():
        kind = snapshot.session_type.strip().lower()
        if "qual" in kind:
            qualifying[snapshot.session_num] = snapshot
            continue
        if kind != "race":
            continue
        last = snapshot
        previous = previous_by_session.get(snapshot.session_num)
        counts = tuple((row.get("CarIdx"), row.get("Incidents")) for row in snapshot.results if "Incidents" in row)
        changed = counts != last_incidents.get(snapshot.session_num)
        if previous is None or snapshot.session_time - previous.session_time >= .4 or snapshot.session_time < previous.session_time or snapshot.session_flags != previous.session_flags or snapshot.session_state != previous.session_state or changed:
            kept.append(snapshot)
            previous_by_session[snapshot.session_num] = snapshot
            last_incidents[snapshot.session_num] = counts
    if last is not None and (not kept or kept[-1] is not last):
        kept.append(last)
    return list(qualifying.values()) + kept


def build_plan(snapshots, source="", markers=None, caution_assignments=None):
    races = {}
    for snapshot in snapshots:
        if snapshot.session_type.strip().lower() == "race":
            races.setdefault(snapshot.session_num, []).append(snapshot)
    if not races:
        raise ValueError("This capture contains no race session.")
    tracks = {str(s.track_info.get("track_name", "")).casefold() for group in races.values() for s in group if s.track_info.get("track_name")}
    sessions = {str(s.weekend_info["SubSessionID"]) for group in races.values() for s in group if s.weekend_info.get("SubSessionID")}
    if len(tracks) > 1 or len(sessions) > 1:
        raise ValueError("This capture combines different races. Choose a capture containing one race.")
    race = max(races.values(), key=len)
    race = sorted(race, key=lambda snapshot: snapshot.session_time)
    # Collapse duplicated replay timestamps rather than counting seeks as action.
    race = list({round(s.session_time, 3): s for s in race}.values())
    first, last = race[0], race[-1]
    warnings = []
    finish = next((s for s in race if s.session_flags & 1 or s.session_state >= 5 or
                   s.total_laps > 0 and any(number(row.get("LapsComplete")) >= s.total_laps for row in s.results)), None)
    partial = race_lap(first) > 1 or finish is None
    if partial:
        warnings.append("Capture does not cover a confirmed complete race; recap is limited to recorded action.")
    if len(races) > 1:
        warnings.append("Multiple race sessions found; using the race session with the most recorded samples.")
    grid = {}
    for s in race:
        for row in s.results:
            start = number(row.get("StartingPosition"))
            if start > 0:
                grid[row["CarIdx"]] = dict(driver(s, row["CarIdx"]), position=start)
    qualifying = [s for s in snapshots if "qual" in s.session_type.lower() and s.session_num < first.session_num]
    grid_rows = qualifying[-1].results if qualifying else []
    if not grid_rows and (first.starting_grid_source == "qualifying" or race_lap(first) <= 1 and first.session_state in (1, 2, 3)):
        grid_rows = first.starting_grid
    base = int(any(number(row.get("Position"), -1) == 0 for row in grid_rows))
    for row in grid_rows:
        idx = row.get("CarIdx")
        position = number(row.get("Position"), -1) + base
        if idx is not None and position > 0:
            grid.setdefault(idx, dict(driver(first, idx), position=position))
    lineup = sorted(grid.values(), key=lambda row: row["position"])
    if not lineup:
        warnings.append("Verified starting grid unavailable; starting-lineup pages will be omitted.")

    events, previous, incidents, last_called, recent_pits = [], None, {}, {}, {}
    pit_groups = {}
    leader, proposed, proposed_at = None, None, 0
    saw_incidents = False

    def add(kind, s, facts, idx=None, before=8, after=14):
        event = {"kind": kind, "lap": race_lap(s), "time": s.session_time,
                 "start": max(first.session_time, s.session_time - before),
                 "end": min(last.session_time, s.session_time + after),
                 "car_idx": idx, "facts": facts}
        events.append(event)
        return event

    if race_lap(first) <= 1:
        start = next((s for s in race if race_lap(s) > 0 and s.session_state == 4 and not s.session_flags & CAUTION), first)
        add("start", start, "The race gets underway. Describe the start without inventing contact or an overtake.", (ordered(start)[0]["CarIdx"] if ordered(start) else None), before=2, after=18)
    sampled = []
    for s in race:
        if sampled and s.session_time - sampled[-1].session_time < 0.4:
            continue
        sampled.append(s)
        rows = ordered(s)
        if not rows:
            continue
        # Post-race result refreshes publish totals, not newly timed incidents.
        # Cars returning to the garage are no longer making racing pit stops.
        if finish is not None and s.session_time >= finish.session_time:
            previous = s
            continue
        by_idx = {r["CarIdx"]: r for r in rows}
        for row in rows:
            idx = row["CarIdx"]
            if pit(s, idx):
                recent_pits[idx] = s.session_time
            if "Incidents" in row and row["Incidents"] is not None:
                saw_incidents = True
                count = number(row["Incidents"])
                old = incidents.get(idx)
                if old is not None and 0 < s.session_time - old[1] <= 2 and count - old[0] >= 2:
                    delta = count - old[0]
                    uncertainty = " The telemetry gap prevents establishing the exact incident time." if s.session_time - old[1] > 2 else ""
                    add("incident", s, f"Lap {race_lap(s)}: {driver(s, idx)['driver_name']}'s recorded incident total increased by {delta}. This is an incident candidate, not proof of a particular collision, fault, or one {delta}x event.{uncertainty}", idx)
                incidents[idx] = (count, s.session_time)
            reason = str(row.get("ReasonOutStr") or row.get("Status") or "").strip()
            if reason.lower() in {"accident", "damage", "too much damage"} and ("damage", idx) not in last_called:
                last_called["damage", idx] = s.session_time
                add("retirement", s, f"Lap {race_lap(s)}: {driver(s, idx)['driver_name']} is listed out with the recorded reason: {reason}.", idx)
        if previous:
            was_yellow, yellow = bool(previous.session_flags & CAUTION), bool(s.session_flags & CAUTION)
            if yellow and not was_yellow:
                add("caution", s, f"The caution is displayed on lap {race_lap(s)}. The telemetry does not establish its cause.", rows[0]["CarIdx"], before=12, after=8)
            elif was_yellow and not yellow and s.session_state == 4:
                add("restart", s, f"Green-flag racing resumes on lap {race_lap(s)}.", rows[0]["CarIdx"], before=8, after=35)
            pitters = [idx for idx in by_idx if pit(s, idx) and not pit(previous, idx)]
            if pitters:
                phase = "caution" if yellow else "green-flag"
                group = pit_groups.setdefault((race_lap(s), phase), [])
                known = {arrival[1] for arrival in group}
                group.extend((s, idx) for idx in pitters if idx not in known)
        current_leader = rows[0]["CarIdx"]
        if leader is None:
            leader = current_leader
        elif current_leader != leader:
            if proposed != current_leader:
                proposed, proposed_at = current_leader, s.session_time
            elif s.session_time - proposed_at >= 1:
                green = not s.session_flags & CAUTION and s.session_state == 4
                on_track = green and all(s.session_time - recent_pits.get(idx, -100) > 45 for idx in (leader, current_leader))
                ahead = driver(s, current_leader)["driver_name"]
                behind = driver(s, leader)["driver_name"]
                add("lead_change", s, f"Lap {race_lap(s)}: {ahead} takes over the recorded race lead from {behind}. " + ("Both cars are outside the recent pit-stop window; describe the observed lead change without inventing a lane or contact." if on_track else "This may be a pit-cycle or caution-order change; do not call it an on-track pass."), current_leader, before=25, after=0)
                leader, proposed = current_leader, None
        else:
            proposed = None
        if previous and not s.session_flags & CAUTION and s.session_state == 4:
            old_order = ordered(previous)
            old_by = {r["CarIdx"]: r for r in old_order}
            for row in rows:
                idx = row["CarIdx"]
                old = old_by.get(idx)
                if not old or row["position"] <= 1 or old["position"] != row["position"] + 1:
                    continue
                rival = next((r for r in old_order if r["position"] == row["position"]), None)
                if not rival or rival["CarIdx"] not in by_idx:
                    continue
                other = rival["CarIdx"]
                if by_idx[other]["position"] != old["position"]:
                    continue
                if any(s.session_time - recent_pits.get(i, -100) < 45 for i in (idx, other)):
                    continue
                try:
                    close = abs(previous.lap_dist_pct[idx] - previous.lap_dist_pct[other]) < 0.015
                    same_lap = previous.lap_completed[idx] == previous.lap_completed[other]
                except (IndexError, TypeError):
                    continue
                key = tuple(sorted((idx, other)))
                if close and same_lap and s.session_time - last_called.get(key, -100) > 45:
                    last_called[key] = s.session_time
                    name, rival_name = driver(s, idx)["driver_name"], driver(s, other)["driver_name"]
                    start = grid.get(idx, {}).get("position")
                    context = f" Started {start}; currently position {row['position']}." if start else ""
                    event = add("overtake", s, f"Lap {race_lap(s)}: {name} moves ahead of {rival_name} in the recorded order for position {row['position']}, after running close together on the same lap.{context} Do not invent the passing lane or contact.", idx, before=25, after=0)
                    event["rival_idx"] = other
        previous = s
    for (lap, phase), arrivals in pit_groups.items():
        first_stop, first_idx = arrivals[0]
        names = ", ".join(driver(snapshot, idx)["driver_name"] for snapshot, idx in arrivals)
        event = add("pit_cycle", first_stop,
                    f"Lap {lap}: {phase} pit stops, with {names} entering pit road on this lap. "
                    "Mention each listed driver once in this grouped pit report. Do not guess tire service or fuel quantities.",
                    first_idx, before=8, after=13)
        event["pit_entrants"] = [idx for _, idx in arrivals]
        event["end"] = min(last.session_time, arrivals[-1][0].session_time + 13)
    confirmed = []
    for event in events:
        if event["kind"] == "overtake":
            following = next((s for s in sampled if event["time"] + 1 <= s.session_time <= event["time"] + 3), None)
            future = {r["CarIdx"]: r["position"] for r in ordered(following)} if following else {}
            idx, rival = event["car_idx"], event["rival_idx"]
            if idx not in future or rival not in future or future[idx] >= future[rival]:
                continue
        confirmed.append(event)
    events = confirmed
    for marker in markers or []:
        at = float(marker["time"])
        if not first.session_time <= at <= (finish.session_time if finish is not None else last.session_time):
            continue
        if finish is not None and at >= finish.session_time:
            continue
        s = min(sampled, key=lambda snapshot: abs(snapshot.session_time - at))
        idx = marker.get("car_idx")
        if any(e["kind"] == "incident" and e["car_idx"] == idx and abs(e["time"] - at) < 12 for e in events):
            continue
        name = driver(s, idx)["driver_name"]
        event = {"kind": "incident_marker", "lap": race_lap(s), "time": at,
                 "start": max(first.session_time, at - 10), "end": min(last.session_time, at + 14),
                 "car_idx": idx, "facts": f"Lap {race_lap(s)}: the iRacing replay incident camera selected {name}. Review this incident sequence. The incident-point amount, collision type, fault, and any retirement are unconfirmed; do not invent them."}
        events.append(event)
    if markers:
        warnings.append("Replay incident markers include unclassified events; a marker does not prove a 2x/4x or a caution cause.")
    warnings.append("Incident coverage depends on the recorded telemetry and available replay markers; it is not a guarantee of every 2x or 4x.")
    if not saw_incidents:
        warnings.append("Per-driver incident counts were unavailable; not every 2x or 4x can be identified from this capture.")
    if finish is not None:
        final = ordered(last)
        if final:
            name = driver(last, final[0]["CarIdx"])["driver_name"]
            podium = "; ".join(f"position {row['position']}: {driver(last, row['CarIdx'])['driver_name']}" for row in final[:3])
            add("finish", finish, f"The captured finish lists {name} in first place. Podium classification: {podium}. Describe the recorded finish without inventing the winning margin.", final[0]["CarIdx"], before=20, after=8)
    # Look back from each yellow for a captured incident candidate and follow it.
    for caution_number, caution in enumerate([event for event in events if event["kind"] == "caution"], 1):
        caution["caution_id"] = f"{first.session_num}:caution:{caution_number}"
        assigned = (caution_assignments or {}).get(caution["caution_id"])
        if assigned is not None and any(row.get("CarIdx") == assigned for s in race for row in s.results):
            caution["car_idx"] = assigned
            caution["start"] = max(first.session_time, caution["time"] - 20)
            caution["facts"] = (f"Caution on lap {caution['lap']}. The producer selected "
                                  f"{driver(last, assigned)['driver_name']} for this caution review. "
                                  "Introduce the replay of this driver before the yellow. Do not invent fault or contact.")
            # A producer selection replaces an uncertain automatic candidate in this review.
            events = [event for event in events if not (event["kind"] in ("incident", "incident_marker")
                      and 0 <= caution["time"] - event["time"] <= 25)]
            continue
        candidates = [event for event in events if event["kind"] in ("incident", "incident_marker")
                      and 0 <= caution["time"] - event["time"] <= 25]
        if not candidates:
            review = caution_slowdown_candidate(sampled, caution["time"])
            if review:
                s, idx = review["snapshot"], review["car_idx"]
                surface = " The car also moved from the racing surface to off-track." if review["off_track"] else ""
                event = add("incident", s,
                            f"Before the lap {caution['lap']} caution, {driver(s, idx)['driver_name']} slowed sharply "
                            f"from about {review['before']:.0f} to {review['speed']:.0f} mph while other cars maintained speed.{surface} "
                            "Review this car as a possible contributor to the caution. Do not claim wheelspin, a collision, fault, or a definite caution cause.", idx)
                event["start"] = max(first.session_time, review["start"])
                event["evidence"] = "isolated_pre_caution_slowdown"
                candidates.append(event)
        if candidates:
            candidate = min(candidates, key=lambda event: abs(caution["time"] - event["time"]))
            caution["car_idx"] = candidate["car_idx"]
            caution["start"] = min(caution["start"], candidate["start"])
    clips = group_highlight_events(events)
    segments = [{"kind": "intro", "title": "Race Highlights", "start": first.session_time, "end": first.session_time,
                 "facts": f"Race highlights from {first.track_info.get('track_name') or 'this race'}. Scheduled distance {first.total_laps} laps. " + ("This is a partial capture." if partial else "Introduce the recap briefly.")}]
    for start in range(0, len(lineup), 10):
        entries = lineup[start:start + 10]
        for entry in entries:
            segments.append({"kind": "lineup", "title": "Starting Lineup", "entries": entries,
                             "active_position": entry["position"],
                             "start": first.session_time, "end": first.session_time,
                             "facts": f"Starting lineup: position {entry['position']}, {entry['driver_name']}, car number {entry['car_number']}. Announce only this driver briefly."})
    for clip in clips:
        if clip["end"] - clip["start"] < 1:
            continue
        caution = next((e for e in clip["events"] if e["kind"] == "caution"), None)
        incident = next((e for e in clip["events"] if e["kind"] in ("incident", "incident_marker")), None)
        facts = " ".join(e["facts"] for e in clip["events"])
        if caution and incident and 0 <= caution["time"] - incident["time"] <= 15:
            facts += f" The incident may have contributed to the lap {caution['lap']} caution; causation is unconfirmed."
        segments.append(dict(clip, kind="clip", title=f"Lap {clip['events'][0]['lap']} · {('incident review' if clip['events'][0]['kind'] == 'incident_marker' else clip['events'][0]['kind'].replace('_', ' ')).title()}", facts=facts))
    finish_facts = next((event["facts"] for event in events if event["kind"] == "finish"), "")
    recap = build_recap(race, grid, finish, events)
    recap_facts = " ".join(f"{stat['label']}: {stat['driver']} {stat['value']}." for stat in recap.get("stats", []) if stat["value"] != "Not recorded")
    segments.append({"kind": "outro", "title": "Race Recap Complete", "start": last.session_time, "end": last.session_time,
                     "facts": "Give a race recap with the podium and these recorded statistics. " + recap_facts + " " + (finish_facts + " Thank viewers for watching RGC AI Broadcast Studio."
                               if finish_facts else "Only the recorded portion was covered; the race result is unconfirmed.")})
    drivers = {}
    for snapshot in race:
        for row in snapshot.results:
            if row.get("CarIdx") is not None:
                drivers[row["CarIdx"]] = driver(snapshot, row["CarIdx"])
    cautions = [{"id": event["caution_id"], "lap": event["lap"], "time": event["time"]}
                for event in events if event["kind"] == "caution"]
    return {"schema_version": 1, "source": str(Path(source).resolve()) if source else "", "session_num": first.session_num,
            "track": first.track_info.get("track_name", ""), "subsession_id": first.weekend_info.get("SubSessionID"), "partial": partial, "warnings": warnings,
            "segments": segments, "recap": recap, "status": "planned", "drivers": list(drivers.values()), "cautions": cautions}


def save_job(path, job):
    path = Path(path)
    path.parent.mkdir(parents=True, exist_ok=True)
    temp = path.with_suffix(".tmp")
    temp.write_text(json.dumps(job, indent=2), encoding="utf-8")
    for attempt in range(10):
        try:
            temp.replace(path)
            break
        except PermissionError:
            if attempt == 9:
                raise
            # A GUI read or antivirus scan can briefly hold the destination on Windows.
            time.sleep(.05)


def generate_narration(client, model, prompt, segment, checkpoint):
    """Retry token-limited responses before sending any text to the voice service."""
    segment["narration_attempts"] = []
    for budget in (1200, 2400, 4800):
        response = client.responses.create(model=model, input=prompt, max_output_tokens=budget)
        text = (getattr(response, "output_text", "") or "").strip()
        status = getattr(response, "status", "completed")
        details = getattr(response, "incomplete_details", None)
        reason = details.get("reason") if isinstance(details, dict) else getattr(details, "reason", None)
        segment["narration_attempts"].append({"budget": budget, "status": status,
                                               "reason": reason, "text": text})
        checkpoint()
        if text and status == "completed" and not reason:
            return text if text[-1] in '.!?"”’' else text + "."
        if status not in ("completed", "incomplete") or reason not in (None, "max_output_tokens"):
            break
    raise RuntimeError("OpenAI could not finish this narration after automatic retries. "
                       "Response details were saved; completed segments are retained. Retry preparation.")


def prepare_highlights(capture, job_path, options=None):
    """Generate and cache narration before Streamlabs recording begins."""
    from config import ELEVENLABS_API_KEY, LEAD_VOICE_ID, OPENAI_API_KEY, OPENAI_MODEL
    from openai import OpenAI
    from elevenlabs.client import ElevenLabs
    from production.audio_bed import OneShotAudioPlayer
    if not OPENAI_API_KEY or not ELEVENLABS_API_KEY or not LEAD_VOICE_ID:
        raise ValueError("Set OpenAI, ElevenLabs, and the Lead voice ID in Studio before preparing highlights.")
    capture, job_path = Path(capture).resolve(), Path(job_path).resolve()
    if capture.name.endswith(".events.jsonl"):
        raise ValueError("Select the main telemetry capture, not its commentary events file.")
    previous_job = {}
    if job_path.exists():
        try:
            previous_job = json.loads(job_path.read_text(encoding="utf-8"))
        except (OSError, ValueError):
            pass
    snapshots = read_highlight_snapshots(capture)
    job = build_plan(snapshots, capture)
    from production.caution_assignments import CautionAssignments
    caution_plan = CautionAssignments(job)
    if (options or {}).get("scan_incidents"):
        from broadcaster.telemetry import IRacingTelemetry
        controller = IRacingTelemetry()
        if not controller.startup():
            raise RuntimeError("Load the matching saved replay before scanning incident markers.")
        actual = str(controller.get_track_info().get("track_name", "")).strip().casefold()
        if actual != str(job["track"]).strip().casefold():
            raise RuntimeError("The replay track does not match the selected capture.")
        captured_id, actual_id = job.get("subsession_id"), controller.get_weekend_info().get("SubSessionID")
        if captured_id and actual_id and str(captured_id) != str(actual_id):
            raise RuntimeError("The replay is from a different race session.")
        race = [snapshot for snapshot in snapshots if snapshot.session_num == job["session_num"] and snapshot.session_type.lower() == "race"]
        progress_job = previous_job if previous_job.get("source") == str(capture) else job
        progress_job.update(status="preparing", progress="Scanning saved replay incidents — fast jumps are expected; do not record yet.")
        save_job(job_path, progress_job)
        def report(count):
            progress_job["progress"] = f"Scanning replay incidents: {count} marker(s) found — fast jumps are expected; do not record yet."
            save_job(job_path, progress_job)
        markers = scan_incident_markers(controller, job["session_num"], min(s.session_time for s in race), max(s.session_time for s in race), report)
        job = build_plan(snapshots, capture, markers, caution_plan.assignments)
        if not markers:
            job["warnings"].append("No usable replay incident markers were found in the captured race interval.")
    elif caution_plan.assignments:
        job = build_plan(snapshots, capture, caution_assignments=caution_plan.assignments)
    job["source_size"] = capture.stat().st_size
    job["source_mtime_ns"] = capture.stat().st_mtime_ns
    job["options"] = dict(options or {})
    try:
        metadata = json.loads(capture.with_suffix(".capture.json").read_text(encoding="utf-8"))
        event = metadata.get("event") or {}
        labels = [str(event.get(key) or "").strip() for key in ("title", "series")]
        labels = [label for label in labels if label and label != "RGC AI Broadcast"]
        if labels:
            job["segments"][0]["facts"] += " Event identification: " + "; ".join(labels) + "."
    except (OSError, ValueError, TypeError):
        pass
    if job["options"].get("sponsor"):
        job["segments"][0]["facts"] += " This recap is presented by " + job["options"]["sponsor"] + "."

    job["voice_id"] = LEAD_VOICE_ID
    job["narration_revision"] = 2
    if (previous_job.get("voice_id") == LEAD_VOICE_ID and previous_job.get("source") == str(capture)
            and previous_job.get("narration_revision") == job["narration_revision"]):
        cached = {segment.get("facts"): segment for segment in previous_job.get("segments", [])}
        for segment in job["segments"]:
            old = cached.get(segment["facts"], {})
            if segment["kind"] == "clip" and any(old.get(key) != segment.get(key) for key in ("start", "end")):
                continue
            audio = (job_path.parent / old.get("audio", "")).resolve()
            if old.get("audio_seconds", 0) > 0 and audio.is_relative_to(job_path.parent) and audio.is_file() and old.get("narration"):
                segment.update({key: old[key] for key in ("audio", "audio_seconds", "narration")})
    job["status"] = "preparing"
    save_job(job_path, job)
    client, voices = OpenAI(api_key=OPENAI_API_KEY), ElevenLabs(api_key=ELEVENLABS_API_KEY)
    audio_dir = job_path.parent / "audio"
    audio_dir.mkdir(exist_ok=True)
    probe = OneShotAudioPlayer(alias="rgc_highlights_probe")
    try:
        for index, segment in enumerate(job["segments"]):
            job["progress"] = f"Preparing narration {index + 1} of {len(job['segments'])}"
            save_job(job_path, job)
            if segment.get("audio") and segment.get("audio_seconds", 0) > 0:
                continue
            words = (18 if segment["kind"] == "lineup" else
                     max(30, min(100, round((segment["end"] - segment["start"]) * 2))) if segment["kind"] == "clip" else 65)
            entrants = sum(len(event.get("pit_entrants", [])) for event in segment.get("events", []))
            if entrants:
                words = max(words, 20 + entrants * 8)
            if segment["kind"] == "outro" and job.get("recap"):
                words = 140
            prompt = ("Write natural motorsports recap narration, spoken text only. Use only these facts. "
                      "This is a retrospective highlight video: introduce each recorded moment rather than pretending it is live. "
                      "Do not mention telemetry, markers, data, software, or editorial instructions to viewers. "
                      "Do not say unconfirmed or not confirmed; omit unsupported details instead. "
                      "Use varied, engaging introductions and restrained excitement for verified overtakes. "
                      "Name the lap for action. Incident points do not establish fault or collision type. "
                      "Never turn a pit-cycle lead change into an on-track pass. Do not claim to see anything beyond the facts. "
                      f"Keep to about {words} words.\n" + segment["facts"])
            text = generate_narration(client, OPENAI_MODEL, prompt, segment, lambda: save_job(job_path, job))
            digest = hashlib.sha256((text + LEAD_VOICE_ID).encode()).hexdigest()[:20]
            audio_path = audio_dir / (digest + ".mp3")
            if not audio_path.exists():
                chunks = voices.text_to_speech.convert(voice_id=LEAD_VOICE_ID, model_id="eleven_multilingual_v2",
                                                       output_format="mp3_44100_128", text=text)
                temporary = audio_path.with_suffix(".tmp")
                with temporary.open("wb") as file:
                    for chunk in chunks:
                        file.write(chunk)
                if temporary.stat().st_size == 0:
                    raise RuntimeError("ElevenLabs returned empty audio.")
                temporary.replace(audio_path)
            # Probe duration without playing the voice into the user's speakers.
            duration = audio_duration(probe, audio_path)
            segment.update(narration=text, audio=str(audio_path.relative_to(job_path.parent)), audio_seconds=duration)
            save_job(job_path, job)
    finally:
        probe.stop()
    job["status"], job["progress"] = "ready", "Ready: start recording in Streamlabs, then Play Highlights."
    save_job(job_path, job)
    return job


def request_highlight_seek(controller, session_num, seconds):
    requester = getattr(controller, "request_replay_session_time", None)
    if not callable(requester):
        requester = controller.seek_replay_session_time
    return bool(requester(session_num, seconds))


def wait_for_highlight_seek(controller, session_num, seconds, clock=None, sleep=None, timeout=12):
    """Keep seek packets isolated and retry when a busy replay ignores one."""
    clock, sleep = clock or time.monotonic, sleep or time.sleep
    if not request_highlight_seek(controller, session_num, seconds):
        return False
    deadline, retry_at, confirmed = clock() + timeout, clock() + 2, 0
    while clock() < deadline:
        aligned = (controller.get_replay_session_num() == session_num and
                   abs(controller.get_replay_session_time() - seconds) < .3)
        confirmed = confirmed + 1 if aligned else 0
        if confirmed >= 2:
            return True
        if not aligned and clock() >= retry_at:
            request_highlight_seek(controller, session_num, seconds)
            retry_at = clock() + 2
        sleep(.1)
    return False


def scan_incident_markers(controller, session_num, start, end, progress=None, clock=None, sleep=None):
    """Visit SDK markers without inferring point values or blame from them."""
    clock, sleep = clock or time.monotonic, sleep or time.sleep
    original = (controller.get_replay_session_num(), controller.get_replay_session_time())
    original_speed = controller.get_replay_play_speed()
    groups = controller.get_camera_groups() or []
    tv = next((g for g in groups if "tv" in str(g.get("GroupName", "")).lower()), None)
    if not tv:
        raise RuntimeError("The replay does not expose a TV camera for incident review.")
    markers, seen = [], set()
    try:
        controller.pause_replay()
        sleep(.15)
        # At the opening boundary iRacing can still report practice/qualifying.
        # Enter the race before scanning its incident markers.
        scan_start = min(end, max(2.0, start))
        if not wait_for_highlight_seek(controller, session_num, scan_start, clock, sleep):
            raise RuntimeError(f"Replay seek was not confirmed: requested session {session_num} at {scan_start:.3f}s; reached session {controller.get_replay_session_num()} at {controller.get_replay_session_time():.3f}s.")
        for _ in range(1000):
            before = (controller.get_replay_session_num(), controller.get_replay_session_time())
            if not controller.seek_next_incident_marker():
                break
            deadline = clock() + 8
            while clock() < deadline:
                point = (controller.get_replay_session_num(), controller.get_replay_session_time())
                if point[0] != before[0] or abs(point[1] - before[1]) > .05:
                    break
                sleep(.1)
            else:
                break
            session, at = point
            key = (session, round(at, 2))
            if key in seen or session != session_num or at > end or at < start:
                break
            seen.add(key)
            if controller.switch_camera_to_incident(int(tv["GroupNum"])):
                sleep(.2)
                idx = controller.safe_read("CamCarIdx")
                if idx is not None and int(idx) >= 0:
                    markers.append({"time": float(at), "car_idx": int(idx)})
                    if progress:
                        progress(len(markers))
        else:
            raise RuntimeError("Incident scan exceeded its safety limit; preparation stopped rather than silently omitting markers.")
    finally:
        restored = wait_for_highlight_seek(controller, *original, clock=clock, sleep=sleep)
        sleep(.1)
        if restored:
            controller.set_replay_speed(original_speed if original_speed is not None else 0)
        else:
            controller.pause_replay()
            raise RuntimeError(f"The incident scan could not restore the original replay position ({original[1]:.3f}s). The replay is paused; retry preparation.")
    return markers


def audio_duration(player, path):
    # The same Windows MCI backend already used by broadcast voice playback.
    with player.lock:
        player.close_locked()
        resolved = str(Path(path).resolve())
        if not player.send(f'open "{resolved}" type mpegvideo alias {player.alias}'):
            raise RuntimeError("Could not open prepared narration audio.")
        try:
            seconds = player.query_length_seconds()
            if seconds <= 0:
                raise RuntimeError("Could not measure narration duration.")
            return seconds
        finally:
            player.close_locked()
