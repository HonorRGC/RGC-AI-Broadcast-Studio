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
            report_replay_decision(
                replay_director.handle_item(item, source, camera_director)
            )
            if should_switch_camera_after_voice_starts(item):
                booth.broadcast(item.message, speaker=item.speaker)
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
                booth.broadcast(item.message, speaker=item.speaker)

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
            overlay_server,
            caution_audio_bed,
            args.tick_seconds,
        )
        print("Disconnected from iRacing. Resetting broadcast session.")
        engine.reset()


if __name__ == "__main__":
    main()
