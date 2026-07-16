import argparse
import time
from pathlib import Path

from config import (
    CRANK_IT_UP_ICON_GRAPHIC,
    CRANK_IT_UP_SPONSOR_GRAPHIC,
    OVERLAY_BRAND_GRAPHICS,
    OVERLAY_RACE_SPONSOR,
    SPONSOR_READ_CAUSE,
    SPONSOR_READ_NAME,
    STUDIO_VOLUME,
)
from broadcast.booth import BroadcastBooth
from broadcast.engine import BroadcastEngine
from broadcaster.telemetry import IRacingTelemetry
from production.camera_director import CameraDirector
from production.audio_bed import AudioBedPlayer
from production.anthem_director import NationalAnthemDirector
from production.caution_presentation import CautionPresentationDirector
from production.non_race_presentation import (
    PracticePresentationDirector,
    QualifyingCameraDirector,
)
from production.live_broadcast_validator import LiveBroadcastValidator
from production.overlay import OverlayServer
from production.car_paint_preview import ensure_preview_file
from production.replay_director import ReplayDirector

DEFAULT_CRANK_IT_UP_SECONDS = 50.0


def parse_args():
    parser = argparse.ArgumentParser(description="RGC AI Broadcast Studio")
    parser.add_argument("--replay", help="Path to a JSONL telemetry recording")
    parser.add_argument("--no-voice", action="store_true", help="Disable ElevenLabs playback")
    parser.add_argument(
        "--voice-test",
        action="store_true",
        help="Play one Lead voice sample and exit without connecting to iRacing",
    )
    parser.add_argument(
        "--crank-it-up-test",
        action="store_true",
        help="Preview the sponsored Crank It Up voice call and overlay without connecting to iRacing",
    )
    parser.add_argument(
        "--crank-it-up-test-seconds",
        type=float,
        default=DEFAULT_CRANK_IT_UP_SECONDS,
        help="Seconds to keep the Crank It Up overlay visible during --crank-it-up-test",
    )
    parser.add_argument("--tick-seconds", type=float, default=1.0)
    parser.add_argument(
        "--camera-mode",
        choices=CameraDirector.MODES,
        default="auto",
        help="Camera direction: off, observe suggestions, or auto-switch iRacing",
    )
    parser.add_argument(
        "--camera-group",
        default="TV1",
        help="iRacing camera group for story targets (default: TV1)",
    )
    parser.add_argument(
        "--camera-home-group",
        default="TV Mixed",
        help="iRacing camera group for the leader/home shot (default: TV Mixed)",
    )
    parser.add_argument(
        "--camera-return-seconds",
        type=float,
        default=14.0,
        help="Seconds before returning from a story target to the leader",
    )
    parser.add_argument(
        "--incident-replay",
        choices=ReplayDirector.MODES,
        default="auto",
        help="Incident replay: off, observe decisions, or control iRacing replay",
    )
    parser.add_argument(
        "--replay-angle-seconds",
        type=float,
        default=30.0,
        help="Seconds to show each incident replay angle",
    )
    parser.add_argument(
        "--incident-marker-preroll-seconds",
        type=float,
        default=25.0,
        help=(
            "Seconds to back up before iRacing's incident marker when the "
            "broadcast cannot identify a specific incident car"
        ),
    )
    parser.add_argument(
        "--incident-debug",
        action="store_true",
        help="Print caution incident-detection diagnostics when no replay is queued",
    )
    parser.add_argument(
        "--overlay",
        action="store_true",
        default=True,
        help="Start the local browser-source race overlay",
    )
    parser.add_argument(
        "--no-overlay",
        action="store_false",
        dest="overlay",
        help="Do not start the local browser-source race overlay",
    )
    parser.add_argument(
        "--overlay-host",
        default="127.0.0.1",
        help="Host for the browser-source overlay server",
    )
    parser.add_argument(
        "--overlay-port",
        type=int,
        default=8765,
        help="Port for the browser-source overlay server",
    )
    return parser.parse_args()


def run_source(
    source,
    engine,
    booth,
    camera_director,
    replay_director,
    anthem_director,
    practice_presentation_director,
    caution_presentation_director,
    qualifying_camera_director,
    live_broadcast_validator,
    overlay_server,
    caution_audio_bed,
    tick_seconds,
):
    while source.is_connected():
        if overlay_server:
            overlay_server.update_from_telemetry(source)
            process_producer_commands(
                overlay_server,
                source,
                engine,
                booth,
                camera_director,
                replay_director,
            )
        report_practice_presentation(
            practice_presentation_director.update(
                source.get_session_type(),
                overlay_server,
            ),
            overlay_server,
        )
        report_anthem_decision(
            anthem_director.update(source.get_session_type(), overlay_server),
            overlay_server,
        )
        report_replay_decision(replay_director.update(source, camera_director), overlay_server)
        report_camera_decision(camera_director.update(source), overlay_server)
        non_race_camera_decision = qualifying_camera_director.update(
            source, camera_director
        )
        report_camera_decision(non_race_camera_decision, overlay_server)
        if overlay_server:
            update_overlay_focused_driver(
                overlay_server,
                source,
                non_race_camera_decision,
                duration=9.0,
            )
        item = engine.tick(source)
        report_caution_presentation(
            caution_presentation_director.update(
                engine.race_director.phase,
                overlay_server,
                caution_audio_bed,
            ),
            overlay_server,
        )
        if item:
            validation = live_broadcast_validator.validate(item, source)
            if not validation.valid:
                report_producer_skip(validation.reason, overlay_server)
                if hasattr(source, "next_snapshot"):
                    source.next_snapshot()
                if tick_seconds > 0:
                    time.sleep(tick_seconds)
                continue
            if overlay_server:
                show_overlay_feature(item, overlay_server, source, engine)
            report_replay_decision(
                replay_director.handle_item(item, source, camera_director),
                overlay_server,
            )
            if should_switch_camera_after_voice_starts(item):
                if not getattr(item, "silent", False):
                    prefade_music_before_restart_call(item, caution_audio_bed)
                    booth.broadcast(item.message, speaker=item.speaker)
                else:
                    report_silent_feature(item, overlay_server)
                camera_decision = camera_director.follow(item, source)
                report_camera_decision(camera_decision, overlay_server)
                if overlay_server:
                    update_overlay_featured_driver(
                        overlay_server,
                        item,
                        source,
                        camera_decision,
                    )
            else:
                camera_decision = camera_director.follow(item, source)
                report_camera_decision(camera_decision, overlay_server)
                if overlay_server:
                    update_overlay_featured_driver(
                        overlay_server,
                        item,
                        source,
                        camera_decision,
                    )
                if not getattr(item, "silent", False):
                    prefade_music_before_restart_call(item, caution_audio_bed)
                    booth.broadcast(item.message, speaker=item.speaker)
                else:
                    report_silent_feature(item, overlay_server)

        if hasattr(source, "next_snapshot"):
            source.next_snapshot()

        if tick_seconds > 0:
            time.sleep(tick_seconds)


def cleanup_live_broadcast_session(
    source,
    replay_director=None,
    anthem_director=None,
    practice_presentation_director=None,
    caution_audio_bed=None,
):
    if replay_director:
        replay_director.stop_replay_audio()

    for controller, method_name in (
        (anthem_director, "stop_audio"),
        (practice_presentation_director, "stop_music"),
        (caution_audio_bed, "stop"),
    ):
        method = getattr(controller, method_name, None)
        if method:
            try:
                method()
            except Exception:
                pass

    return_live = getattr(source, "return_to_live", None)
    if return_live:
        try:
            returned = bool(return_live())
            if returned:
                print("REPLAY: live edge synced.")
            return returned
        except Exception:
            return False
    return False


def prefade_music_before_restart_call(item, caution_audio_bed):
    if not is_one_to_green_restart_call(item) or not caution_audio_bed:
        return False

    fader = getattr(caution_audio_bed, "fade_out_and_wait", None)
    if fader:
        return bool(fader(duration_seconds=0.7, steps=6))

    fader = getattr(caution_audio_bed, "fade_out", None)
    if fader:
        faded = bool(fader(duration_seconds=0.7, steps=6))
        if faded:
            time.sleep(0.8)
        return faded

    stopper = getattr(caution_audio_bed, "stop", None)
    if stopper:
        stopper()
        return True
    return False


def is_one_to_green_restart_call(item):
    key = str(getattr(item, "dedupe_key", "") or "")
    return key.startswith("race_control:one_to_green")


def publish_producer_event(overlay_server, kind="info", title="", message="", speaker=""):
    if not overlay_server:
        return
    publisher = getattr(overlay_server, "add_producer_event", None)
    if publisher:
        publisher(kind=kind, title=title, message=message, speaker=speaker)


def sync_producer_control_state(overlay_server, engine, booth, camera_director):
    if not overlay_server:
        return
    overlay_server.set_control_state(
        auto_camera=getattr(camera_director, "mode", "") == "auto",
        openai=engine.openai_director.is_enabled(),
        elevenlabs=booth.voice_status()[0],
    )


def process_producer_commands(
    overlay_server,
    source,
    engine,
    booth,
    camera_director,
    replay_director=None,
):
    commands = overlay_server.drain_commands()
    if not commands:
        sync_producer_control_state(overlay_server, engine, booth, camera_director)
        return

    for item in commands:
        command = str(item.get("command", "") or "")
        payload = item.get("payload", {}) or {}
        handle_producer_command(
            command,
            payload,
            overlay_server,
            source,
            engine,
            booth,
            camera_director,
            replay_director,
        )

    sync_producer_control_state(overlay_server, engine, booth, camera_director)


def handle_producer_command(
    command,
    payload,
    overlay_server,
    source,
    engine,
    booth,
    camera_director,
    replay_director=None,
):
    if command == "auto_camera_on":
        camera_director.mode = "auto"
        publish_producer_event(overlay_server, "info", "Producer Control", "Auto camera enabled.")
        return

    if command == "auto_camera_off":
        camera_director.mode = "off"
        publish_producer_event(
            overlay_server,
            "warning",
            "Producer Control",
            "Auto camera disabled. Manual camera buttons still work.",
        )
        return

    if command == "openai_on":
        engine.openai_director.set_enabled(True)
        message = (
            "OpenAI commentary enabled."
            if engine.openai_director.is_enabled()
            else "OpenAI was requested, but it is not configured."
        )
        publish_producer_event(overlay_server, "info", "Producer Control", message)
        return

    if command == "openai_off":
        engine.openai_director.set_enabled(False)
        publish_producer_event(
            overlay_server,
            "warning",
            "Producer Control",
            "OpenAI commentary disabled. Broadcast will use rule-based/helper text.",
        )
        return

    if command == "elevenlabs_on":
        booth.set_voice_enabled(True)
        ready, reason = booth.voice_status()
        message = "ElevenLabs voice playback enabled." if ready else f"ElevenLabs unavailable: {reason}."
        publish_producer_event(overlay_server, "info", "Producer Control", message)
        return

    if command == "elevenlabs_off":
        booth.set_voice_enabled(False)
        publish_producer_event(
            overlay_server,
            "warning",
            "Producer Control",
            "ElevenLabs voice playback disabled. Text will still appear in Producer Assist.",
        )
        return

    if command == "camera_follow_driver":
        car_idx = safe_int(payload.get("car_idx"), default=None)
        if car_idx is None:
            publish_producer_event(overlay_server, "warning", "Camera", "No driver was selected.")
            return
        decision = camera_director.manual_focus_car(
            car_idx,
            str(payload.get("group_name", "") or camera_director.preferred_group),
            source,
        )
        report_camera_decision(decision, overlay_server)
        return

    if command == "camera_follow_leader":
        decision = camera_director.manual_focus_home(source)
        report_camera_decision(decision, overlay_server)
        return

    if command == "replay_return_live":
        returned = bool(getattr(source, "return_to_live", lambda: False)())
        if replay_director:
            replay_director.reset()
        camera_director.replay_active = False
        message = "Returned to live racing." if returned else "Return-to-live command was not accepted."
        publish_producer_event(
            overlay_server,
            "replay" if returned else "warning",
            "Replay Control",
            message,
        )
        return

    if command in ("replay_pause", "replay_play"):
        method_name = "pause_replay" if command == "replay_pause" else "play_replay"
        accepted = bool(getattr(source, method_name, lambda: False)())
        label = "Pause replay" if command == "replay_pause" else "Play replay"
        publish_producer_event(
            overlay_server,
            "replay" if accepted else "warning",
            "Replay Control",
            f"{label} command sent." if accepted else f"{label} command was not accepted by iRacing.",
        )
        return

    if command in ("replay_rewind", "replay_fast_forward"):
        seconds = max(1, min(60, safe_int(payload.get("seconds"), default=10) or 10))
        frames = seconds * 60
        method_name = (
            "rewind_replay_frames"
            if command == "replay_rewind"
            else "fast_forward_replay_frames"
        )
        moved = bool(getattr(source, method_name, lambda *_: False)(frames))
        direction = "Rewind" if command == "replay_rewind" else "Fast forward"
        message = (
            f"{direction} {seconds} seconds."
            if moved
            else f"{direction} command was not accepted by iRacing."
        )
        publish_producer_event(
            overlay_server,
            "replay" if moved else "warning",
            "Replay Control",
            message,
        )
        return

    publish_producer_event(
        overlay_server,
        "warning",
        "Producer Control",
        f"Unknown command: {command}",
    )


def report_anthem_decision(decision, overlay_server=None):
    if decision.status == "ignored":
        return
    message = f"CEREMONY: {decision.reason}"
    print(message)
    publish_producer_event(overlay_server, "info", "Ceremony", decision.reason)


def report_practice_presentation(message, overlay_server=None):
    if message:
        print(f"PRACTICE: {message}")
        publish_producer_event(overlay_server, "info", "Practice", message)


def report_caution_presentation(message, overlay_server=None):
    if message:
        print(f"CAUTION: {message}")
        publish_producer_event(overlay_server, "warning", "Caution Presentation", message)


def report_silent_feature(item, overlay_server=None):
    print(f"FEATURE: {item.message}")
    publish_producer_event(
        overlay_server,
        "info",
        "Feature",
        str(getattr(item, "message", "") or ""),
        speaker=str(getattr(item, "speaker", "") or ""),
    )


def report_producer_skip(reason, overlay_server=None):
    print(f"PRODUCER: skipped stale story ({reason}).")
    publish_producer_event(
        overlay_server,
        "warning",
        "Producer skipped stale story",
        str(reason or ""),
    )


def show_overlay_feature(item, overlay_server, source=None, engine=None):
    category = str(getattr(item, "category", "") or "")
    if category == "crank_it_up":
        overlay_server.show_special_presentation(
            kind="crank_it_up",
            title="Crank It Up",
            subtitle="No booth. Just race cars.",
            duration=(
                getattr(item, "feature_duration_seconds", DEFAULT_CRANK_IT_UP_SECONDS)
                or DEFAULT_CRANK_IT_UP_SECONDS
            ),
            graphics=crank_it_up_graphics(),
        )
        return

    show_sponsor_mention_bug(item, overlay_server)

    if category == "green_pit_cycle_update":
        rows = build_pit_update_rows(source, engine)
        if rows:
            overlay_server.show_stat_panel(
                kind="green_pit_cycle",
                title="Green Flag Pit Cycle",
                subtitle="Recent stops and estimated tire age",
                rows=rows,
                duration=13.0,
                dedupe_key=f"green_pit_cycle:{latest_pit_lap(engine)}",
                minimum_interval=30.0,
            )
        return

    if category in ("pit_strategy", "caution_pit_summary"):
        return

    if should_show_movers_graphic(item, engine):
        rows = build_biggest_movers_rows(engine)
        if rows:
            overlay_server.show_stat_panel(
                kind="biggest_movers",
                title="Biggest Movers",
                subtitle="Positions gained from the start",
                rows=rows,
                duration=11.0,
                dedupe_key="biggest_movers",
                minimum_interval=180.0,
            )


def show_sponsor_mention_bug(item, overlay_server):
    mentions = sponsor_mentions_for_message(getattr(item, "message", ""))
    if not mentions:
        return False

    graphics = sponsor_graphics_for_mentions(mentions)
    overlay_server.show_special_presentation(
        kind="sponsor_bug",
        title=" / ".join(mentions),
        subtitle="Broadcast Partner",
        duration=5.0,
        graphics=graphics,
    )
    print(f"SPONSOR: showing graphic for {' / '.join(mentions)}.")
    publish_producer_event(
        overlay_server,
        "info",
        "Sponsor graphic",
        f"Showing graphic for {' / '.join(mentions)}.",
    )
    return True


def sponsor_mentions_for_message(message):
    text = str(message or "").lower()
    mentions = []
    for name in configured_sponsor_names():
        if sponsor_name_matches_text(name, text):
            mentions.append(name)
    return mentions


def configured_sponsor_names():
    names = []
    for raw in (
        SPONSOR_READ_NAME,
        OVERLAY_RACE_SPONSOR,
        SPONSOR_READ_CAUSE,
        "RGC Motorsports",
        "Autism Awareness",
    ):
        for name in split_sponsor_names(raw):
            if name and name not in names:
                names.append(name)
    return names


def split_sponsor_names(value):
    text = str(value or "").strip()
    if not text:
        return []
    for separator in (";", "|", ","):
        text = text.replace(separator, "||")
    return [part.strip() for part in text.split("||") if part.strip()]


def sponsor_name_matches_text(name, lower_text):
    normalized_name = normalize_sponsor_text(name)
    if not normalized_name:
        return False
    if normalized_name in normalize_sponsor_text(lower_text):
        return True
    if "autism" in normalized_name and "autism" in lower_text:
        return True
    return False


def sponsor_graphics_for_mentions(mentions):
    graphics = []
    for mention in mentions:
        graphic = sponsor_graphic_for_mention(mention)
        if graphic and graphic not in graphics:
            graphics.append(graphic)
    return graphics


def sponsor_graphic_for_mention(mention):
    mention_text = normalize_sponsor_text(mention)
    graphic = find_brand_graphic_for_name(mention)
    if graphic:
        return graphic
    if "autism" in mention_text:
        return find_brand_graphic(("autism",), "/assets/autism_awareness.png")
    if "rgc" in mention_text:
        return find_brand_graphic(("rgc", "motor"), "/assets/rgc_motorsports.png")
    return OVERLAY_BRAND_GRAPHICS[0] if OVERLAY_BRAND_GRAPHICS else ""


def find_brand_graphic_for_name(name):
    name_tokens = sponsor_tokens(name)
    if not name_tokens:
        return ""
    best_graphic = ""
    best_score = 0
    for graphic in OVERLAY_BRAND_GRAPHICS:
        graphic_tokens = sponsor_tokens(graphic)
        score = len(set(name_tokens) & set(graphic_tokens))
        if score > best_score:
            best_graphic = graphic
            best_score = score
    return best_graphic if best_score >= min(2, len(set(name_tokens))) else ""


def find_brand_graphic(required_terms, fallback):
    for graphic in OVERLAY_BRAND_GRAPHICS:
        text = str(graphic or "").lower()
        if all(term in text for term in required_terms):
            return graphic
    return fallback


def sponsor_tokens(value):
    ignored = {
        "a",
        "an",
        "and",
        "awareness",
        "broadcast",
        "cause",
        "logo",
        "motorsport",
        "motorsports",
        "of",
        "partner",
        "presented",
        "sponsor",
        "the",
    }
    return [
        token
        for token in normalize_sponsor_text(value).split()
        if token and token not in ignored
    ]


def normalize_sponsor_text(value):
    text = str(value or "").lower()
    cleaned = []
    for char in text:
        cleaned.append(char if char.isalnum() else " ")
    return " ".join("".join(cleaned).split())


def run_crank_it_up_test(booth, overlay_server, duration_seconds=DEFAULT_CRANK_IT_UP_SECONDS):
    intro = "It is time to Crank It Up. Crank It Up is presented by RGC Motorsports."
    feature_seconds = max(1.0, float(duration_seconds or DEFAULT_CRANK_IT_UP_SECONDS))

    if overlay_server:
        overlay_server.show_special_presentation(
            kind="crank_it_up",
            title="Crank It Up",
            subtitle="Presented by RGC Motorsports",
            duration=feature_seconds,
            graphics=crank_it_up_graphics(),
        )
        print(f"Crank It Up overlay preview is active for {feature_seconds:.0f} seconds.")
        print(f"Preview URL: {overlay_server.url}")
        booth.broadcast(intro, speaker="lead")
        time.sleep(feature_seconds)
        overlay_server.clear_special_presentation()
    else:
        booth.broadcast(intro, speaker="lead")
        print("Overlay is OFF, so only the voice preview was played.")


def crank_it_up_graphics():
    return [
        graphic
        for graphic in (CRANK_IT_UP_SPONSOR_GRAPHIC, CRANK_IT_UP_ICON_GRAPHIC)
        if graphic
    ]


def should_show_movers_graphic(item, engine):
    if not engine:
        return False
    category = str(getattr(item, "category", "") or "")
    if category not in ("race_story", "fastest_lap"):
        return False
    target = getattr(item, "camera_target_car_idx", None)
    if target is None:
        return False
    movers = getattr(engine.race_intelligence, "get_biggest_movers", lambda *_: [])(3)
    return any(
        mover.car_idx == target and getattr(mover, "positions_gained", 0) >= 5
        for mover in movers
    )


def build_biggest_movers_rows(engine, limit=5):
    if not engine:
        return []
    movers = getattr(engine.race_intelligence, "get_biggest_movers", lambda *_: [])(limit)
    rows = []
    for mover in movers:
        gained = int(getattr(mover, "positions_gained", 0) or 0)
        if gained <= 0:
            continue
        rows.append(
            {
                "label": f"P{mover.current_position}  #{mover.car_number} {mover.driver_name}",
                "value": f"+{gained}",
                "detail": f"Started {ordinal(mover.starting_position)}",
            }
        )
    return rows


def build_pit_update_rows(source, engine, limit=5):
    if not source or not engine:
        return []
    current_lap = safe_int(getattr(source, "get_lap", lambda: 0)(), 0)
    current_positions = build_current_position_lookup(source.get_results())
    states = list(getattr(engine.pit_strategy_detector, "driver_states", {}).values())
    states = [state for state in states if getattr(state, "last_pit_lap", 0) > 0]
    states.sort(key=lambda state: getattr(state, "last_pit_lap", 0), reverse=True)
    rows = []
    for state in states[:limit]:
        current_position = current_positions.get(state.car_idx, 0)
        detail_parts = [f"Last stop lap {state.last_pit_lap}"]
        if state.pit_entry_position:
            detail_parts.append(f"entered P{state.pit_entry_position}")
        if current_position:
            detail_parts.append(f"now P{current_position}")
        tire_age = max(0, current_lap - safe_int(getattr(state, "last_pit_lap", 0), 0))
        if tire_age > 0 and not state.on_pit_road:
            detail_parts.append(f"tires {tire_age} laps old")
        lane_seconds = (
            state.current_pit_lane_seconds
            if state.on_pit_road
            else state.last_pit_lane_seconds
        )
        stop_seconds = (
            state.current_pit_stop_seconds
            if state.on_pit_road
            else state.last_pit_stop_seconds
        )
        if lane_seconds > 0:
            detail_parts.append(f"pit lane {format_seconds(lane_seconds)}")
        if stop_seconds > 0:
            detail_parts.append(f"service {format_seconds(stop_seconds)}")
        rows.append(
            {
                "label": f"#{state.car_number} {state.driver_name}",
                "value": (
                    "Pitting"
                    if state.on_pit_road
                    else f"{tire_age} lap tires" if tire_age > 0
                    else f"Lap {state.last_pit_lap}"
                ),
                "detail": " | ".join(detail_parts),
            }
        )
    return rows


def build_current_position_lookup(results):
    valid = [car for car in results or [] if car.get("CarIdx") is not None]
    zero_based = any(safe_int(car.get("Position"), 999) == 0 for car in valid)
    positions = {}
    for car in valid:
        position = safe_int(car.get("Position"), 0)
        if zero_based:
            position += 1
        positions[car.get("CarIdx")] = position
    return positions


def latest_pit_lap(engine):
    if not engine:
        return 0
    states = getattr(engine.pit_strategy_detector, "driver_states", {}).values()
    return max((getattr(state, "last_pit_lap", 0) for state in states), default=0)


def ordinal(number):
    number = safe_int(number)
    if number <= 0:
        return "--"
    if 10 <= number % 100 <= 20:
        suffix = "th"
    else:
        suffix = {1: "st", 2: "nd", 3: "rd"}.get(number % 10, "th")
    return f"{number}{suffix}"


def format_seconds(seconds):
    seconds = max(float(seconds or 0.0), 0.0)
    return f"{seconds:.1f}s"


def safe_int(value, default=0):
    try:
        return int(value)
    except (TypeError, ValueError):
        return default


def should_switch_camera_after_voice_starts(item):
    category = str(getattr(item, "category", "") or "")
    return (
        category.startswith("opening_field_rundown")
        or getattr(item, "camera_target_car_idx", None) is not None
    )


def report_replay_decision(decision, overlay_server=None):
    if decision.status in ("ignored", "held"):
        return
    if decision.status == "failed":
        message = f"REPLAY: {decision.reason}"
        print(message)
        publish_producer_event(overlay_server, "replay", "Replay", decision.reason)
        return
    if decision.status == "live":
        message = "REPLAY: returned to live racing."
        print(message)
        publish_producer_event(overlay_server, "replay", "Replay", "Returned to live racing.")
        return
    target = (
        f"car index {decision.car_idx}"
        if decision.car_idx is not None
        else "iRacing incident camera"
    )
    message = (
        f"angle {decision.angle_number} of {decision.total_angles}, "
        f"{target} on {decision.angle_group}."
    )
    print(f"REPLAY: {message}")
    publish_producer_event(overlay_server, "replay", "Replay", message)


def update_overlay_featured_driver(overlay_server, item, source, camera_decision):
    if camera_decision is None:
        return
    if camera_decision.status not in ("suggested", "switched", "held"):
        return
    car_idx = getattr(item, "camera_target_car_idx", None)
    if car_idx is None and str(getattr(item, "category", "")).startswith(
        "opening_field_rundown"
    ):
        car_idx = camera_decision.car_idx
    if car_idx is None or car_idx != camera_decision.car_idx:
        return

    update_overlay_focused_driver(overlay_server, source, camera_decision)


def update_overlay_focused_driver(
    overlay_server,
    source,
    camera_decision,
    duration=12.0,
):
    if camera_decision is None:
        return
    if camera_decision.status not in ("suggested", "switched", "held"):
        return
    car_idx = camera_decision.car_idx
    if car_idx is None:
        return

    driver = source.get_driver_lookup().get(car_idx, {})
    driver_name = driver.get("name", "")
    car_number = driver.get("number", camera_decision.car_number)
    if not driver_name and not car_number:
        return

    story = build_featured_driver_story(driver)
    car_image_url = build_featured_driver_image(driver)
    overlay_server.show_featured_driver(
        car_number=car_number,
        driver_name=driver_name,
        story=story,
        duration=duration,
        car_image_url=car_image_url,
    )


def build_featured_driver_story(driver):
    details = []
    for key in ("team_name", "club", "country", "sponsor"):
        value = str(driver.get(key, "") or "").strip()
        if value and value not in details:
            details.append(value)
    return " | ".join(details[:3]) or "Featured driver"


def build_featured_driver_image(driver):
    for key in ("car_image_url", "paint_image_url"):
        value = str(driver.get(key, "") or "").strip()
        if value.startswith(("http://", "https://", "/")):
            return value

    manual_image = str(driver.get("car_image", "") or "").strip()
    if manual_image.startswith(("http://", "https://", "/assets/", "/paint-previews/")):
        return manual_image
    if manual_image:
        image_path = Path(manual_image).expanduser()
        if not image_path.is_absolute():
            image_path = Path(__file__).resolve().parent / image_path
        preview_path = ensure_preview_file(image_path, driver)
        if preview_path:
            return f"/paint-previews/{preview_path.name}"
    return ""


def report_camera_decision(decision, overlay_server=None):
    if decision is None:
        return
    if decision.status not in ("suggested", "switched", "failed", "live"):
        return

    if decision.status == "live":
        message = "replay view returned to live racing."
        print(f"CAMERA: {message}")
        publish_producer_event(overlay_server, "camera", "Camera", message)
        return

    if decision.status == "failed":
        print(f"CAMERA: {decision.reason}")
        publish_producer_event(overlay_server, "warning", "Camera", decision.reason)
        return

    action = "would follow" if decision.status == "suggested" else "following"
    message = (
        f"{action} car #{decision.car_number} "
        f"on {decision.group_name} (CarIdx {decision.car_idx})."
    )
    print(f"CAMERA: {message}")
    publish_producer_event(overlay_server, "camera", "Camera", message)


def main():
    args = parse_args()
    engine = BroadcastEngine(incident_debug=args.incident_debug)
    caution_audio_bed = AudioBedPlayer(
        normal_volume=STUDIO_VOLUME * 10,
        ducked_volume=max(0, min(1000, STUDIO_VOLUME * 2)),
    )
    booth = BroadcastBooth(
        enable_voice=not args.no_voice,
        audio_bed=caution_audio_bed,
        studio_volume=STUDIO_VOLUME,
    )
    camera_director = CameraDirector(
        mode=args.camera_mode,
        preferred_group=args.camera_group,
        home_group=args.camera_home_group,
        return_after_seconds=args.camera_return_seconds,
    )
    replay_director = ReplayDirector(
        mode=args.incident_replay,
        angle_seconds=args.replay_angle_seconds,
        incident_marker_pre_roll_frames=round(
            max(0.0, args.incident_marker_preroll_seconds) * 60
        ),
        audio_player=caution_audio_bed,
    )
    anthem_director = NationalAnthemDirector()
    practice_presentation_director = PracticePresentationDirector()
    caution_presentation_director = CautionPresentationDirector()
    qualifying_camera_director = QualifyingCameraDirector()
    live_broadcast_validator = LiveBroadcastValidator()
    overlay_server = OverlayServer(
        host=args.overlay_host,
        port=args.overlay_port,
    ) if args.overlay else None
    if overlay_server:
        booth.producer_sink = overlay_server.add_producer_event

    if args.incident_replay == "auto" and args.camera_mode != "auto":
        raise SystemExit(
            "--incident-replay auto requires --camera-mode auto."
        )
    if overlay_server:
        overlay_url = overlay_server.start()
        sync_producer_control_state(overlay_server, engine, booth, camera_director)
        print(f"Overlay: ON ({overlay_url})")
        overlay_server.add_producer_event(
            kind="info",
            title="Overlay",
            message=f"Overlay: ON ({overlay_url}) | Producer: {overlay_server.producer_url}",
        )
    else:
        print("Overlay: OFF")

    print("=" * 60)
    print("RGC AI Broadcast Studio")
    print("=" * 60)
    print(f"OpenAI: {'ON' if engine.openai_director.is_enabled() else 'OFF'}")
    print(
        "League context: "
        f"{'ON' if engine.league_context.is_configured() else 'OFF'} "
        f"(drivers={engine.league_context.drivers_csv_path}, "
        f"season={engine.league_context.season_stats_csv_path}, "
        f"career={engine.league_context.career_stats_csv_path})"
    )
    voice_ready, voice_reason = booth.voice_status()
    voice_ids = booth.voice_id_status()
    print(f"ElevenLabs: {'ON' if voice_ready else 'OFF'} ({voice_reason})")
    print(
        "Voice IDs: "
        f"Lead={'SET' if voice_ids['lead'] else 'MISSING'} | "
        f"Jeff={'SET' if voice_ids['jeff'] else 'MISSING'} | "
        f"Sarah={'SET' if voice_ids['sarah'] else 'MISSING'}"
    )
    print(f"Incident replay: {args.incident_replay.upper()}")
    if args.incident_debug:
        print("Incident debug: ON")
    print(
        f"Camera: {args.camera_mode.upper()} "
        f"(stories: {args.camera_group} | home: {args.camera_home_group})"
    )
    print("=" * 60)

    if args.voice_test:
        if not voice_ready:
            print("Voice test cannot run until the ElevenLabs status above is ON.")
            return
        booth.broadcast(
            "RGC AI Broadcast Studio voice test. The lead announcer is ready.",
            speaker="lead",
        )
        print("Voice test requested. Check your Windows audio output and media player.")
        return

    if args.crank_it_up_test:
        if not voice_ready:
            print("Voice preview skipped because the ElevenLabs status above is OFF.")
        run_crank_it_up_test(
            booth,
            overlay_server,
            duration_seconds=args.crank_it_up_test_seconds,
        )
        return

    if args.replay:
        from replay.replay_telemetry import ReplayTelemetry

        source = ReplayTelemetry(args.replay)
        if not source.startup():
            raise RuntimeError("Replay contains no telemetry snapshots.")
        run_source(
            source,
            engine,
            booth,
            camera_director,
            replay_director,
            anthem_director,
            practice_presentation_director,
            caution_presentation_director,
            qualifying_camera_director,
            live_broadcast_validator,
            overlay_server,
            caution_audio_bed,
            args.tick_seconds,
        )
        return

    source = IRacingTelemetry()
    while True:
        if not source.startup():
            print("Waiting for iRacing...")
            time.sleep(5)
            continue

        print("\nConnected to iRacing!")
        cleanup_live_broadcast_session(
            source,
            replay_director,
            anthem_director,
            practice_presentation_director,
            caution_audio_bed,
        )
        engine.reset()
        camera_director.reset()
        replay_director.reset()
        anthem_director = NationalAnthemDirector()
        practice_presentation_director = PracticePresentationDirector()
        caution_presentation_director = CautionPresentationDirector()
        qualifying_camera_director = QualifyingCameraDirector()
        live_broadcast_validator = LiveBroadcastValidator()
        run_source(
            source,
            engine,
            booth,
            camera_director,
            replay_director,
            anthem_director,
            practice_presentation_director,
            caution_presentation_director,
            qualifying_camera_director,
            live_broadcast_validator,
            overlay_server,
            caution_audio_bed,
            args.tick_seconds,
        )
        cleanup_live_broadcast_session(
            source,
            replay_director,
            anthem_director,
            practice_presentation_director,
            caution_audio_bed,
        )
        print("Disconnected from iRacing. Resetting broadcast session.")
        engine.reset()


if __name__ == "__main__":
    main()
