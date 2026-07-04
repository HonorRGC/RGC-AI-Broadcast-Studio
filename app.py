import argparse
import time

from broadcast.booth import BroadcastBooth
from broadcast.engine import BroadcastEngine
from broadcaster.telemetry import IRacingTelemetry
from production.camera_director import CameraDirector
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
        default="off",
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
        default="off",
        help="Incident replay: off, observe decisions, or control iRacing replay",
    )
    parser.add_argument(
        "--replay-angle-seconds",
        type=float,
        default=10.0,
        help="Seconds to show each incident replay angle",
    )
    parser.add_argument(
        "--incident-marker-preroll-seconds",
        type=float,
        default=20.0,
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
        help="Start the local browser-source race overlay",
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
    overlay_server,
    tick_seconds,
):
    while source.is_connected():
        if overlay_server:
            overlay_server.update_from_telemetry(source)
        report_replay_decision(replay_director.update(source, camera_director))
        report_camera_decision(camera_director.update(source))
        item = engine.tick(source)
        if item:
            report_replay_decision(
                replay_director.handle_item(item, source, camera_director)
            )
            report_camera_decision(camera_director.follow(item, source))
            booth.broadcast(item.message, speaker=item.speaker)

        if hasattr(source, "next_snapshot"):
            source.next_snapshot()

        if tick_seconds > 0:
            time.sleep(tick_seconds)


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


def report_camera_decision(decision):
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
    booth = BroadcastBooth(enable_voice=not args.no_voice)
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
    )
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
            overlay_server,
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
        run_source(
            source,
            engine,
            booth,
            camera_director,
            replay_director,
            overlay_server,
            args.tick_seconds,
        )
        print("Disconnected from iRacing. Resetting broadcast session.")
        engine.reset()


if __name__ == "__main__":
    main()
