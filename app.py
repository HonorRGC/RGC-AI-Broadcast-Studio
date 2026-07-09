import argparse
import time

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
from production.replay_director import ReplayDirector


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
        default=28.0,
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
        default=20.0,
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
        report_practice_presentation(
            practice_presentation_director.update(
                source.get_session_type(),
                overlay_server,
            )
        )
        report_anthem_decision(
            anthem_director.update(source.get_session_type(), overlay_server)
        )
        report_replay_decision(replay_director.update(source, camera_director))
        report_camera_decision(camera_director.update(source))
        report_camera_decision(
            qualifying_camera_director.update(source, camera_director)
        )
        item = engine.tick(source)
        report_caution_presentation(
            caution_presentation_director.update(
                engine.race_director.phase,
                overlay_server,
                caution_audio_bed,
            )
        )
        if item:
            validation = live_broadcast_validator.validate(item, source)
            if not validation.valid:
                report_producer_skip(validation.reason)
                if hasattr(source, "next_snapshot"):
                    source.next_snapshot()
                if tick_seconds > 0:
                    time.sleep(tick_seconds)
                continue
            if overlay_server:
                show_overlay_feature(item, overlay_server, source, engine)
            report_replay_decision(
                replay_director.handle_item(item, source, camera_director)
            )
            if should_switch_camera_after_voice_starts(item):
                if not getattr(item, "silent", False):
                    booth.broadcast(item.message, speaker=item.speaker)
                else:
                    report_silent_feature(item)
                camera_decision = camera_director.follow(item, source)
                report_camera_decision(camera_decision)
                if overlay_server:
                    update_overlay_featured_driver(
                        overlay_server,
                        item,
                        source,
                        camera_decision,
                    )
            else:
                camera_decision = camera_director.follow(item, source)
                report_camera_decision(camera_decision)
                if overlay_server:
                    update_overlay_featured_driver(
                        overlay_server,
                        item,
                        source,
                        camera_decision,
                    )
                if not getattr(item, "silent", False):
                    booth.broadcast(item.message, speaker=item.speaker)
                else:
                    report_silent_feature(item)

        if hasattr(source, "next_snapshot"):
            source.next_snapshot()

        if tick_seconds > 0:
            time.sleep(tick_seconds)


def report_anthem_decision(decision):
    if decision.status == "ignored":
        return
    print(f"CEREMONY: {decision.reason}")


def report_practice_presentation(message):
    if message:
        print(f"PRACTICE: {message}")


def report_caution_presentation(message):
    if message:
        print(f"CAUTION: {message}")


def report_silent_feature(item):
    print(f"FEATURE: {item.message}")


def report_producer_skip(reason):
    print(f"PRODUCER: skipped stale story ({reason}).")


def show_overlay_feature(item, overlay_server, source=None, engine=None):
    category = str(getattr(item, "category", "") or "")
    if category == "crank_it_up":
        overlay_server.show_special_presentation(
            kind="crank_it_up",
            title="Crank It Up",
            subtitle="No booth. Just race cars.",
            duration=getattr(item, "feature_duration_seconds", 28.0) or 28.0,
            graphics=[],
        )
        return

    if category in ("pit_strategy", "caution_pit_summary"):
        rows = build_pit_update_rows(source, engine)
        if rows:
            overlay_server.show_stat_panel(
                kind="pit_update",
                title="Pit Road Update",
                subtitle="Last stop information",
                rows=rows,
                duration=12.0,
                dedupe_key=f"pit_update:{latest_pit_lap(engine)}",
                minimum_interval=18.0,
            )
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
                dedupe_key=f"movers:{getattr(item, 'camera_target_car_idx', None)}",
                minimum_interval=35.0,
            )


def run_crank_it_up_test(booth, overlay_server, duration_seconds=28.0):
    intro = "It is time to Crank It Up. Crank It Up is presented by RGC Motorsports."
    feature_seconds = max(1.0, float(duration_seconds or 28.0))

    booth.broadcast(intro, speaker="lead")

    if overlay_server:
        overlay_server.show_special_presentation(
            kind="crank_it_up",
            title="Crank It Up",
            subtitle="Presented by RGC Motorsports",
            duration=feature_seconds,
            graphics=[],
        )
        print(f"Crank It Up overlay preview is active for {feature_seconds:.0f} seconds.")
        print(f"Preview URL: {overlay_server.url}")
        time.sleep(feature_seconds)
        overlay_server.clear_special_presentation()
    else:
        print("Overlay is OFF, so only the voice preview was played.")


def should_show_movers_graphic(item, engine):
    if not engine:
        return False
    category = str(getattr(item, "category", "") or "")
    if category not in ("race_story", "fastest_lap"):
        return False
    message = str(getattr(item, "message", "") or "").lower()
    target = getattr(item, "camera_target_car_idx", None)
    movers = getattr(engine.race_intelligence, "get_biggest_movers", lambda *_: [])(5)
    if target is not None:
        for mover in movers:
            if mover.car_idx == target and getattr(mover, "positions_gained", 0) >= 3:
                return True
    return any(
        phrase in message
        for phrase in (
            "moved into",
            "gained",
            "from",
            "up to",
            "climbed",
            "biggest mover",
        )
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
                    format_seconds(lane_seconds)
                    if lane_seconds > 0
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


def report_replay_decision(decision):
    if decision.status in ("ignored", "held"):
        return
    if decision.status == "failed":
        print(f"REPLAY: {decision.reason}")
        return
    if decision.status == "live":
        print("REPLAY: returned to live racing.")
        return
    target = (
        f"car index {decision.car_idx}"
        if decision.car_idx is not None
        else "iRacing incident camera"
    )
    print(
        f"REPLAY: angle {decision.angle_number} of {decision.total_angles}, "
        f"{target} on {decision.angle_group}."
    )


def update_overlay_featured_driver(overlay_server, item, source, camera_decision):
    if camera_decision.status not in ("suggested", "switched", "held"):
        return
    car_idx = getattr(item, "camera_target_car_idx", None)
    if car_idx is None and str(getattr(item, "category", "")).startswith(
        "opening_field_rundown"
    ):
        car_idx = camera_decision.car_idx
    if car_idx is None or car_idx != camera_decision.car_idx:
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
        duration=12.0,
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
    for key in ("car_image_url", "car_image", "paint_image_url"):
        value = str(driver.get(key, "") or "").strip()
        if value.startswith(("http://", "https://", "/")):
            return value
    return ""


def report_camera_decision(decision):
    if decision is None:
        return
    if decision.status not in ("suggested", "switched", "failed", "live"):
        return

    if decision.status == "live":
        print("CAMERA: replay view returned to live racing.")
        return

    if decision.status == "failed":
        print(f"CAMERA: {decision.reason}")
        return

    action = "would follow" if decision.status == "suggested" else "following"
    print(
        f"CAMERA: {action} car #{decision.car_number} "
        f"on {decision.group_name} (CarIdx {decision.car_idx})."
    )


def main():
    args = parse_args()
    engine = BroadcastEngine(incident_debug=args.incident_debug)
    caution_audio_bed = AudioBedPlayer()
    booth = BroadcastBooth(enable_voice=not args.no_voice, audio_bed=caution_audio_bed)
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

    if args.incident_replay == "auto" and args.camera_mode != "auto":
        raise SystemExit(
            "--incident-replay auto requires --camera-mode auto."
        )
    if overlay_server:
        overlay_url = overlay_server.start()
        print(f"Overlay: ON ({overlay_url})")
    else:
        print("Overlay: OFF")

    print("=" * 60)
    print("RGC AI Broadcast Studio")
    print("=" * 60)
    print(f"OpenAI: {'ON' if engine.openai_director.is_enabled() else 'OFF'}")
    print(
        "League driver notes: "
        f"{'ON' if engine.league_context.is_configured() else 'OFF'} "
        f"({engine.league_context.drivers_csv_path})"
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
        print("Disconnected from iRacing. Resetting broadcast session.")
        engine.reset()


if __name__ == "__main__":
    main()
