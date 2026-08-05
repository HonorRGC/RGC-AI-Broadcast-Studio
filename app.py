import argparse
import time
from pathlib import Path
from types import SimpleNamespace

from config import (
    CRANK_IT_UP_ICON_GRAPHIC,
    CRANK_IT_UP_SPONSOR_NAME,
    CRANK_IT_UP_SPONSOR_GRAPHIC,
    OVERLAY_BRAND_GRAPHICS,
    OVERLAY_HOST,
    OVERLAY_RACE_SPONSOR,
    RACE_ADMIN_MODE,
    RACE_SPONSOR_GRAPHICS,
    RACE_SPONSOR_NAMES,
    RACE_SPONSOR_VIDEOS,
    SPONSOR_READ_CAUSE_NAME,
    SPONSOR_READ_CAUSE_LOGO,
    SPONSOR_READ_NAME,
    SPONSOR_READ_NAME_2,
    SPONSOR_READ_NAME_3,
    STUDIO_VOLUME,
    USE_IRACING_RENDERED_CAR_IMAGES,
)
from broadcast.booth import BroadcastBooth
from broadcast.engine import BroadcastEngine
from broadcaster.telemetry import IRacingTelemetry
from production.camera_director import CameraDirector
from production.audio_bed import AudioBedPlayer, percent_to_mci_volume
from production.anthem_director import NationalAnthemDirector
from production.caution_presentation import CautionPresentationDirector
from production.discord_reporter import DiscordRaceReporter
from production.non_race_presentation import (
    PracticePresentationDirector,
    QualifyingCameraDirector,
)
from production.live_broadcast_validator import LiveBroadcastValidator
from production.overlay import OverlayServer
from production.multiclass import build_multiclass_context
from production.car_paint_preview import ensure_preview_file
from production.iracing_render_cache import build_iracing_render_image_url
from production.sim_racing_apps import build_sim_racing_apps_car_render_info
from production.replay_director import ReplayDirector
from production.race_control import RaceControlService

DEFAULT_CRANK_IT_UP_SECONDS = 50.0
MANUAL_SPONSOR_INDEX = 0
_FEATURED_DRIVER_RENDER_INFO_CACHE = {}

COUNTRY_ALIASES = {
    "arg": "Argentina",
    "ar": "Argentina",
    "aus": "Australia",
    "au": "Australia",
    "bel": "Belgium",
    "be": "Belgium",
    "bra": "Brazil",
    "br": "Brazil",
    "can": "Canada",
    "ca": "Canada",
    "den": "Denmark",
    "dk": "Denmark",
    "england": "United Kingdom",
    "fin": "Finland",
    "fi": "Finland",
    "fra": "France",
    "fr": "France",
    "ger": "Germany",
    "de": "Germany",
    "gbr": "United Kingdom",
    "gb": "United Kingdom",
    "ire": "Ireland",
    "ie": "Ireland",
    "ita": "Italy",
    "it": "Italy",
    "jpn": "Japan",
    "jp": "Japan",
    "mex": "Mexico",
    "mx": "Mexico",
    "nld": "Netherlands",
    "nl": "Netherlands",
    "nor": "Norway",
    "no": "Norway",
    "nzl": "New Zealand",
    "nz": "New Zealand",
    "sco": "United Kingdom",
    "scotland": "United Kingdom",
    "spa": "Spain",
    "esp": "Spain",
    "es": "Spain",
    "swe": "Sweden",
    "se": "Sweden",
    "uk": "United Kingdom",
    "united states of america": "United States",
    "usa": "United States",
    "us": "United States",
    "wales": "United Kingdom",
}

US_STATE_NAMES = {
    "alabama",
    "alaska",
    "arizona",
    "arkansas",
    "california",
    "colorado",
    "connecticut",
    "delaware",
    "florida",
    "georgia",
    "hawaii",
    "idaho",
    "illinois",
    "indiana",
    "iowa",
    "kansas",
    "kentucky",
    "louisiana",
    "maine",
    "maryland",
    "massachusetts",
    "michigan",
    "minnesota",
    "mississippi",
    "missouri",
    "montana",
    "nebraska",
    "nevada",
    "new hampshire",
    "new jersey",
    "new mexico",
    "new york",
    "north carolina",
    "north dakota",
    "ohio",
    "oklahoma",
    "oregon",
    "pennsylvania",
    "rhode island",
    "south carolina",
    "south dakota",
    "tennessee",
    "texas",
    "utah",
    "vermont",
    "virginia",
    "washington",
    "west virginia",
    "wisconsin",
    "wyoming",
}

CANADIAN_PROVINCES = {
    "alberta",
    "british columbia",
    "manitoba",
    "new brunswick",
    "newfoundland",
    "newfoundland and labrador",
    "nova scotia",
    "ontario",
    "prince edward island",
    "quebec",
    "saskatchewan",
}


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
        default=OVERLAY_HOST,
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
    race_control_service=None,
    discord_reporter=None,
):
    while source.is_connected():
        if overlay_server:
            overlay_server.update_from_telemetry(source)
            overlay_server.set_director_suggestions(
                build_director_suggestions(overlay_server.current_state_dict())
            )
            process_producer_commands(
                overlay_server,
                source,
                engine,
                booth,
                camera_director,
                replay_director,
                race_control_service,
                caution_audio_bed,
                practice_presentation_director,
                anthem_director,
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
        camera_update_decision = camera_director.update(source)
        report_camera_decision(camera_update_decision, overlay_server)
        if overlay_server and should_update_overlay_for_camera_update(
            camera_update_decision
        ):
            update_overlay_focused_driver(
                overlay_server,
                source,
                camera_update_decision,
                duration=9.0,
                opening_intro=getattr(camera_update_decision, "role", "") == "lineup",
            )
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
        if overlay_server:
            overlay_server.set_pit_road_rows(
                build_producer_pit_road_rows(source, engine)
            )
        report_caution_presentation(
            caution_presentation_director.update(
                engine.race_director.phase,
                overlay_server,
                caution_audio_bed,
            ),
            overlay_server,
        )
        report_discord_race_report(
            discord_reporter,
            source,
            engine,
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
                    broadcast_with_actual_timing(booth, engine, item)
                    show_sponsor_commercial_if_available(item, overlay_server)
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
                    log_race_event_for_item(
                        item,
                        overlay_server,
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
                    log_race_event_for_item(
                        item,
                        overlay_server,
                        source,
                        camera_decision,
                    )
                if not getattr(item, "silent", False):
                    prefade_music_before_restart_call(item, caution_audio_bed)
                    broadcast_with_actual_timing(booth, engine, item)
                    show_sponsor_commercial_if_available(item, overlay_server)
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

    stopper = getattr(caution_audio_bed, "stop", None)
    if stopper:
        stopper()
        return True
    return False


def broadcast_with_actual_timing(booth, engine, item):
    playback_seconds = booth.broadcast(item.message, speaker=item.speaker)
    if playback_seconds:
        engine.broadcast_queue.mark_actual_playback_started(
            item,
            playback_seconds,
        )


def is_one_to_green_restart_call(item):
    key = str(getattr(item, "dedupe_key", "") or "")
    return key.startswith("race_control:one_to_green")


def publish_producer_event(overlay_server, kind="info", title="", message="", speaker=""):
    if not overlay_server:
        return
    publisher = getattr(overlay_server, "add_producer_event", None)
    if publisher:
        publisher(kind=kind, title=title, message=message, speaker=speaker)


def report_discord_race_report(discord_reporter, source, engine, overlay_server=None):
    if not discord_reporter or getattr(discord_reporter, "posted", False):
        return
    race_director = getattr(engine, "race_director", None)
    if not getattr(race_director, "post_race_results_queued", False):
        return

    race_state_reader = getattr(getattr(engine, "race_intelligence", None), "get_race_state", None)
    race_state = race_state_reader() if race_state_reader else None
    ok, message = discord_reporter.post_once(
        results=source.get_results(),
        driver_lookup=source.get_driver_lookup(),
        track_info=source.get_track_info(),
        total_laps=source.get_total_laps(),
        race_state=race_state,
        openai_director=getattr(engine, "openai_director", None),
    )
    publish_producer_event(
        overlay_server,
        "info" if ok else "warning",
        "Discord Race Report",
        message,
    )


def queue_race_control_admin_announcement(engine, result, payload=None):
    if not engine or not getattr(result, "ok", False):
        return False

    message = race_control_admin_announcement(result, payload or {})
    if not message:
        return False

    queue = getattr(engine, "broadcast_queue", None)
    adder = getattr(queue, "add", None)
    if not adder:
        return False

    adder(
        message,
        priority=13,
        category="race_control",
        protected=True,
        speaker="lead",
        expires_after=30,
        dedupe_key=f"race_control:admin_action:{getattr(result, 'action', '')}:{getattr(result, 'command', '')}",
    )
    return True


def race_control_admin_announcement(result, payload):
    action = str(getattr(result, "action", "") or "").strip().lower()
    driver = race_control_driver_label(payload)
    seconds = safe_int((payload or {}).get("seconds"), 15)

    if action == "extend_caution":
        return "Race control is extending this caution one more lap to get the field lined up."
    if action == "one_to_green":
        return "Race control has shortened this caution. It will be one lap to green this time."
    if action == "drive_through" and driver:
        return f"Race control has issued a drive-through penalty to {driver}."
    if action == "timed_black" and driver:
        return f"Race control has issued a {seconds}-second penalty to {driver}."
    if action == "eol" and driver:
        return f"Race control is sending {driver} to the end of the longest line."
    if action == "clear_penalty" and driver:
        return f"Race control has cleared the penalty for {driver}."
    if action == "waveby" and driver:
        return f"Race control is giving {driver} the wave around."
    if action == "dq" and driver:
        return f"Race control has disqualified {driver} from tonight's race."
    if action == "remove" and driver:
        return f"Race control has removed {driver} from the session."
    if action == "clear_all":
        return "Race control has cleared all outstanding penalties."
    return ""


def race_control_driver_label(payload):
    payload = payload or {}
    name = str(payload.get("driver_name", "") or "").strip()
    number = str(payload.get("car_number", "") or "").strip()
    if number and name:
        return f"the {number} of {name}"
    if name:
        return name
    if number:
        return f"the {number}"
    token = str(payload.get("driver_token", "") or "").strip()
    return token


def build_director_suggestions(state):
    leaderboard = list((state or {}).get("leaderboard") or [])
    pit_road = list((state or {}).get("pit_road") or [])
    suggestions = []

    if leaderboard:
        leader = leaderboard[0]
        suggestions.append(
            {
                "kind": "suggestion",
                "title": "Leader Story",
                "message": director_driver_story(
                    leader,
                    "Leader camera first. Build the story around pace, gap, and control of the race.",
                ),
                "car_idx": leader.get("car_idx", 0),
                "car_number": leader.get("car_number", ""),
                "driver_name": leader.get("driver_name", ""),
            }
        )

    closest = closest_battle_suggestion(leaderboard)
    if closest:
        suggestions.append(closest)

    movers = sorted(
        [
            driver
            for driver in leaderboard
            if abs(safe_int(driver.get("position_delta"))) >= 4
        ],
        key=lambda driver: abs(safe_int(driver.get("position_delta"))),
        reverse=True,
    )
    if movers:
        driver = movers[0]
        delta = safe_int(driver.get("position_delta"))
        direction = "up" if delta > 0 else "down"
        suggestions.append(
            {
                "kind": "suggestion",
                "title": "Big Mover",
                "message": director_driver_story(
                    driver,
                    f"Big mover: {direction} {abs(delta)} spots from the start. Good reset/update candidate.",
                ),
                "car_idx": driver.get("car_idx", 0),
                "car_number": driver.get("car_number", ""),
                "driver_name": driver.get("driver_name", ""),
            }
        )

    pitting = [
        row
        for row in pit_road
        if str(row.get("status", "")).lower() == "on pit road"
    ]
    if pitting:
        row = pitting[0]
        suggestions.append(
            {
                "kind": "suggestion",
                "title": "Pit Road",
                "message": (
                    f"Sarah may want pit-road attention: #{row.get('car_number', '--')} "
                    f"{row.get('driver_name', 'Unknown Driver')} is on pit road."
                ),
                "car_idx": row.get("car_idx", 0),
                "car_number": row.get("car_number", ""),
                "driver_name": row.get("driver_name", ""),
            }
        )

    return suggestions[:5]


def director_driver_story(driver, lead):
    pieces = [
        lead,
        f"#{driver.get('car_number', '--')} {driver.get('driver_name', 'Unknown Driver')}.",
    ]
    position = safe_int(driver.get("position"), 0)
    if position > 0:
        pieces.append(f"Running {ordinal(position)}.")
    start = safe_int(driver.get("starting_position"), 0)
    delta = safe_int(driver.get("position_delta"), 0)
    if start > 0:
        movement = "even from the start"
        if delta > 0:
            movement = f"up {delta}"
        elif delta < 0:
            movement = f"down {abs(delta)}"
        pieces.append(f"Started {ordinal(start)}, {movement}.")
    interval = str(driver.get("interval", "") or "").strip()
    if interval:
        pieces.append(f"Interval: {interval}.")
    laps_led = safe_int(driver.get("laps_led"), 0)
    if laps_led > 0:
        pieces.append(f"Laps led: {laps_led}.")
    fastest = str(driver.get("fastest_lap", "") or "").strip()
    if fastest:
        pieces.append(f"Best lap: {fastest}.")
    last_pit = safe_int(driver.get("last_pit_lap"), 0)
    if last_pit > 0:
        pieces.append(f"Last pit lap {last_pit}.")
    return " ".join(pieces)


def closest_battle_suggestion(leaderboard):
    candidates = []
    for driver in leaderboard[1:]:
        interval = parse_interval_seconds(driver.get("interval"))
        if interval is None or interval <= 0 or interval > 1.0:
            continue
        candidates.append((interval, driver))
    if not candidates:
        return None
    interval, driver = min(candidates, key=lambda item: item[0])
    return {
        "kind": "suggestion",
        "title": "Closest Battle",
        "message": director_driver_story(
            driver,
            (
                f"Closest visible battle around {ordinal(driver.get('position'))}: "
                f"{interval:.2f}s to the car ahead. Good live action target."
            ),
        ),
        "car_idx": driver.get("car_idx", 0),
        "car_number": driver.get("car_number", ""),
        "driver_name": driver.get("driver_name", ""),
    }


def parse_interval_seconds(value):
    text = str(value or "").strip().lower()
    if not text or text in ("leader", "--"):
        return None
    if "lap" in text:
        return None
    text = text.replace("+", "").replace("s", "").strip()
    try:
        return float(text)
    except ValueError:
        return None


def clamp_percent(value, default=65):
    try:
        number = int(float(value))
    except (TypeError, ValueError):
        number = int(default)
    return max(0, min(100, number))


def sync_producer_control_state(
    overlay_server,
    engine,
    booth,
    camera_director,
    race_control_service=None,
    music_volume=None,
):
    if not overlay_server:
        return
    current_leaderboard_style = getattr(
        overlay_server,
        "current_leaderboard_style",
        lambda: "side",
    )
    overlay_server.set_control_state(
        auto_camera=getattr(camera_director, "mode", "") == "auto",
        openai=engine.openai_director.is_enabled(),
        elevenlabs=booth.voice_status()[0],
        leaderboard_style=current_leaderboard_style(),
        race_admin=bool(getattr(race_control_service, "enabled", False)),
        broadcaster_volume=clamp_percent(getattr(booth, "studio_volume", STUDIO_VOLUME)),
        music_volume=clamp_percent(music_volume if music_volume is not None else STUDIO_VOLUME),
    )


def producer_music_volume(caution_audio_bed=None, practice_presentation_director=None):
    if caution_audio_bed is not None:
        return round(max(0, min(1000, int(getattr(caution_audio_bed, "normal_volume", STUDIO_VOLUME * 10)))) / 10)
    if practice_presentation_director is not None:
        return getattr(practice_presentation_director, "music_volume", STUDIO_VOLUME)
    return STUDIO_VOLUME


def process_producer_commands(
    overlay_server,
    source,
    engine,
    booth,
    camera_director,
    replay_director=None,
    race_control_service=None,
    caution_audio_bed=None,
    practice_presentation_director=None,
    anthem_director=None,
):
    commands = overlay_server.drain_commands()
    if not commands:
        sync_producer_control_state(
            overlay_server,
            engine,
            booth,
            camera_director,
            race_control_service,
            music_volume=producer_music_volume(caution_audio_bed, practice_presentation_director),
        )
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
            race_control_service,
            caution_audio_bed,
            practice_presentation_director,
            anthem_director,
        )

    sync_producer_control_state(
        overlay_server,
        engine,
        booth,
        camera_director,
        race_control_service,
        music_volume=producer_music_volume(caution_audio_bed, practice_presentation_director),
    )


def handle_producer_command(
    command,
    payload,
    overlay_server,
    source,
    engine,
    booth,
    camera_director,
    replay_director=None,
    race_control_service=None,
    caution_audio_bed=None,
    practice_presentation_director=None,
    anthem_director=None,
):
    if command == "camera_claim":
        claimer = getattr(overlay_server, "claim_camera_control", None)
        ok, message = (
            claimer(payload.get("client_id"), payload.get("producer_name", "Producer"))
            if claimer
            else (True, "Camera control claimed.")
        )
        auto_was_on = getattr(camera_director, "mode", "") == "auto"
        if ok:
            begin_producer_camera_takeover(camera_director, replay_director)
            if auto_was_on:
                publish_producer_event(
                    overlay_server,
                    "warning",
                    "Producer Control",
                    "Auto camera disabled for manual producer control.",
                )
        publish_producer_event(
            overlay_server,
            "info" if ok else "warning",
            "Camera Control",
            message,
        )
        return

    if command == "set_audio_volume":
        target = str(payload.get("target", "") or "").strip().lower()
        volume = clamp_percent(payload.get("volume"), STUDIO_VOLUME)
        if target == "broadcaster":
            setter = getattr(booth, "set_studio_volume", None)
            if setter:
                setter(volume)
            publish_producer_event(
                overlay_server,
                "info",
                "Audio",
                f"Broadcaster volume set to {volume}%.",
            )
            return
        if target == "music":
            player_volume = percent_to_mci_volume(volume)
            for controller in (caution_audio_bed, practice_presentation_director, anthem_director):
                if controller is None:
                    continue
                setter = getattr(controller, "set_music_volume", None)
                if setter:
                    setter(volume)
                    continue
                direct_setter = getattr(controller, "set_volume", None)
                if direct_setter:
                    direct_setter(player_volume)
            publish_producer_event(
                overlay_server,
                "info",
                "Audio",
                f"Music volume set to {volume}%.",
            )
            return

    if command == "camera_release":
        releaser = getattr(overlay_server, "release_camera_control", None)
        ok, message = (
            releaser(payload.get("client_id"))
            if releaser
            else (True, "Camera control released.")
        )
        publish_producer_event(
            overlay_server,
            "info" if ok else "warning",
            "Camera Control",
            message,
        )
        return

    if command == "race_admin_on":
        if race_control_service:
            race_control_service.set_enabled(True)
        publish_producer_event(
            overlay_server,
            "warning",
            "Race Control",
            "Race Admin Mode enabled. Producer buttons can now send hosted-session admin commands.",
        )
        return

    if command == "race_admin_off":
        if race_control_service:
            race_control_service.set_enabled(False)
        publish_producer_event(
            overlay_server,
            "info",
            "Race Control",
            "Race Admin Mode disabled.",
        )
        return

    if command == "race_control":
        if not race_control_service:
            publish_producer_event(
                overlay_server,
                "warning",
                "Race Control",
                "Race Control is not available in this broadcast session.",
            )
            return
        result = race_control_service.execute(payload.get("action"), payload, source)
        if result.ok and result.action == "throw_yellow":
            race_director = getattr(engine, "race_director", None)
            marker = getattr(race_director, "mark_admin_caution_pending", None)
            if marker:
                marker()
        elif result.ok:
            queue_race_control_admin_announcement(engine, result, payload)
        if hasattr(overlay_server, "add_race_control_audit"):
            overlay_server.add_race_control_audit(
                result.message,
                {**dict(payload or {}), "ok": result.ok},
            )
        publish_producer_event(
            overlay_server,
            "warning" if (result.dangerous or not result.ok) else "info",
            "Race Control",
            result.message,
        )
        return

    if command == "producer_crank_it_up":
        if not engine:
            publish_producer_event(
                overlay_server,
                "warning",
                "Crank It Up",
                "Broadcast engine is not available.",
            )
            return
        results = source.get_results() if source else []
        sponsor_name = str(payload.get("sponsor_name", "") or "").strip()
        if not sponsor_name:
            sponsor_name = configured_crank_it_up_sponsor_name()
        queued = engine.queue_manual_crank_it_up(results, sponsor_name=sponsor_name)
        publish_producer_event(
            overlay_server,
            "info" if queued else "warning",
            "Crank It Up",
            (
                f"Queued Crank It Up presented by {sponsor_name}."
                if queued
                else "Could not queue Crank It Up because no running cars were available."
            ),
        )
        return

    if command == "producer_sponsor_commercial":
        if not engine:
            publish_producer_event(
                overlay_server,
                "warning",
                "Sponsor",
                "Broadcast engine is not available.",
            )
            return
        sponsor_name = next_manual_sponsor_name()
        if not sponsor_name:
            publish_producer_event(
                overlay_server,
                "warning",
                "Sponsor",
                "No race sponsors are configured yet.",
            )
            return
        engine.broadcast_queue.add(
            f"Let's step aside for a quick word from {sponsor_name}.",
            priority=11,
            category="sponsor_read",
            protected=False,
            speaker="lead",
            expires_after=30,
            dedupe_key=f"sponsor:manual:{time.time()}",
        )
        has_video = bool(sponsor_video_for_mention(sponsor_name))
        publish_producer_event(
            overlay_server,
            "info",
            "Sponsor",
            (
                f"Queued sponsor commercial for {sponsor_name}."
                if has_video
                else f"Queued sponsor read and logo pop for {sponsor_name}."
            ),
        )
        return

    if command == "producer_note_add":
        message = str(payload.get("message", "") or "").strip()
        if message and hasattr(overlay_server, "add_producer_note"):
            overlay_server.add_producer_note(message, payload)
            publish_producer_event(overlay_server, "info", "Producer Note", message)
        return

    if command == "producer_note_mark":
        marker = getattr(overlay_server, "update_control_room_item_status", None)
        if marker:
            marker("producer_notes", payload.get("item_id"), payload.get("status", "done"))
        return

    if command == "incident_review_add":
        message = str(payload.get("message", "") or "").strip()
        if not message:
            driver_name = str(payload.get("driver_name", "") or "selected driver")
            message = f"Review possible incident involving {driver_name}."
        if hasattr(overlay_server, "add_incident_review"):
            overlay_server.add_incident_review(message, payload)
            publish_producer_event(overlay_server, "warning", "Incident Review", message)
        return

    if command == "incident_review_mark":
        marker = getattr(overlay_server, "update_control_room_item_status", None)
        if marker:
            marker(
                "incident_reviews",
                payload.get("item_id"),
                payload.get("status", "reviewed"),
            )
        return

    if command == "race_event_note":
        updater = getattr(overlay_server, "update_race_event_log_item", None)
        item = (
            updater(
                payload.get("item_id"),
                status=payload.get("status", "needs review"),
                note=payload.get("note", ""),
                producer_name=payload.get("producer_name", ""),
            )
            if updater
            else None
        )
        message = (
            f"Marked event for review: {item.title}."
            if item
            else "Race event could not be marked for review."
        )
        publish_producer_event(
            overlay_server,
            "warning" if item else "info",
            "Race Event Log",
            message,
        )
        return

    if command == "interview_queue_add":
        if hasattr(overlay_server, "add_interview_queue_item"):
            item = overlay_server.add_interview_queue_item(payload)
            publish_producer_event(
                overlay_server,
                "info",
                "Interview Queue",
                f"Queued {item.driver_name or 'driver'} for interview.",
            )
        return

    if command == "interview_mark":
        marker = getattr(overlay_server, "update_control_room_item_status", None)
        if marker:
            marker(
                "interview_queue",
                payload.get("item_id"),
                payload.get("status", "interviewed"),
            )
        return

    if command in ("leaderboard_side", "leaderboard_ticker", "leaderboard_flo"):
        style = {
            "leaderboard_ticker": "ticker",
            "leaderboard_flo": "flo",
        }.get(command, "side")
        setter = getattr(overlay_server, "set_leaderboard_style", None)
        selected = setter(style) if setter else style
        publish_producer_event(
            overlay_server,
            "info",
            "Overlay",
            f"Leaderboard style set to {selected}.",
        )
        return

    if command == "auto_camera_on":
        if replay_director:
            replay_director.end_manual_control()
        if hasattr(camera_director, "end_manual_control"):
            camera_director.end_manual_control()
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
        if not ensure_camera_control(overlay_server, payload):
            return
        auto_was_on = getattr(camera_director, "mode", "") == "auto"
        begin_producer_camera_takeover(camera_director, replay_director)
        if auto_was_on:
            publish_producer_event(
                overlay_server,
                "warning",
                "Producer Control",
                "Auto camera disabled for manual driver focus.",
            )
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

    if command == "race_event_review":
        if not ensure_camera_control(overlay_server, payload):
            return
        begin_producer_camera_takeover(camera_director, replay_director)
        session_num = safe_int(payload.get("replay_session_num"), default=None)
        session_time = safe_float(payload.get("replay_session_time"), default=None)
        if session_num is None or session_time is None:
            publish_producer_event(
                overlay_server,
                "warning",
                "Event Review",
                "This event does not have a replay time marker yet.",
            )
            return

        pre_roll_seconds = max(
            0,
            min(45, safe_int(payload.get("pre_roll_seconds"), default=15) or 15),
        )
        review_time = max(0.0, float(session_time) - float(pre_roll_seconds))
        seeker = getattr(source, "seek_replay_session_time", None)
        accepted = bool(seeker(session_num, review_time)) if seeker else False
        method = "session-time marker"
        if accepted and replay_seek_appears_live(source):
            accepted = False
        if not accepted:
            fallback = fallback_rewind_to_event_review(source, review_time)
            accepted = fallback["accepted"]
            method = fallback["method"]
        paused = False
        if accepted:
            paused = bool(getattr(source, "pause_replay", lambda: False)())
            set_producer_replay_speed(source, 0)

        lap = safe_int(payload.get("session_lap"), default=0)
        lap_text = f" lap {lap}" if lap > 0 else ""
        message = (
            f"Loaded review{lap_text}, {pre_roll_seconds} seconds before the event. "
            f"Method: {method}. Use Play/Rewind/Fast Forward and camera buttons to inspect it."
            if accepted
            else "Event review seek was not accepted by iRacing using session-time or frame-rewind fallback."
        )
        if accepted and not paused:
            message += " Pause was not accepted, so replay may be playing."
        publish_producer_event(
            overlay_server,
            "replay" if accepted else "warning",
            "Event Review",
            message,
        )
        return

    if command == "camera_follow_leader":
        if not ensure_camera_control(overlay_server, payload):
            return
        auto_was_on = getattr(camera_director, "mode", "") == "auto"
        begin_producer_camera_takeover(camera_director, replay_director)
        if auto_was_on:
            publish_producer_event(
                overlay_server,
                "warning",
                "Producer Control",
                "Auto camera disabled for manual leader focus.",
            )
        decision = camera_director.manual_focus_home(source)
        report_camera_decision(decision, overlay_server)
        return

    if command == "replay_return_live":
        returned = bool(getattr(source, "return_to_live", lambda: False)())
        if replay_director:
            replay_director.reset()
            replay_director.end_manual_control()
        if hasattr(camera_director, "end_manual_control"):
            camera_director.end_manual_control()
        camera_director.replay_active = False
        camera_director.mode = "auto"
        try:
            camera_decision = camera_director.manual_focus_home(source, lock_manual=False)
        except TypeError:
            camera_decision = camera_director.manual_focus_home(source)
        report_camera_decision(camera_decision, overlay_server)
        message = "Returned to live racing." if returned else "Return-to-live command was not accepted."
        publish_producer_event(
            overlay_server,
            "replay" if returned else "warning",
            "Replay Control",
            message,
        )
        return

    if command in ("replay_pause", "replay_play"):
        if not ensure_camera_control(overlay_server, payload):
            return
        begin_producer_camera_takeover(camera_director, replay_director)
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

    if command in (
        "replay_reverse",
        "replay_slow_motion",
        "replay_normal_speed",
        "replay_fast_play",
    ):
        if not ensure_camera_control(overlay_server, payload):
            return
        begin_producer_camera_takeover(camera_director, replay_director)
        label_by_command = {
            "replay_reverse": "Reverse replay",
            "replay_slow_motion": "Slow motion",
            "replay_normal_speed": "Normal replay speed",
            "replay_fast_play": "Fast-forward playback",
        }
        if command == "replay_reverse":
            speed = next_replay_speed(source, direction="reverse")
        elif command == "replay_fast_play":
            speed = next_replay_speed(source, direction="fast")
        else:
            speed = 1
        slow_motion = command == "replay_slow_motion"
        if command == "replay_normal_speed":
            set_producer_replay_speed(source, 1)
        setter = getattr(source, "set_replay_speed", None)
        if setter:
            try:
                accepted = bool(setter(speed, slow_motion))
            except TypeError:
                accepted = bool(setter(0.5 if slow_motion else speed))
        else:
            fallback = "play_replay" if speed == 1 else ""
            accepted = bool(getattr(source, fallback, lambda: False)())
        label = label_by_command[command]
        publish_producer_event(
            overlay_server,
            "replay" if accepted else "warning",
            "Replay Control",
            f"{label} command sent."
            if accepted
            else f"{label} command was not accepted by iRacing.",
        )
        return

    if command in ("replay_rewind", "replay_fast_forward"):
        if not ensure_camera_control(overlay_server, payload):
            return
        begin_producer_camera_takeover(camera_director, replay_director)
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


def ensure_camera_control(overlay_server, payload):
    payload = payload or {}
    client_id = str(payload.get("client_id", "") or "")
    checker = getattr(overlay_server, "camera_control_allows", None)
    if checker and not checker(client_id):
        holder = getattr(overlay_server, "camera_control_holder_name", lambda: "another producer")()
        publish_producer_event(
            overlay_server,
            "warning",
            "Camera Control",
            f"Camera control is held by {holder}. Ask them to release it first.",
        )
        return False

    claimer = getattr(overlay_server, "claim_camera_control", None)
    if claimer:
        ok, message = claimer(client_id, payload.get("producer_name", "Producer"))
        if not ok:
            publish_producer_event(
                overlay_server,
                "warning",
                "Camera Control",
                message,
            )
            return False
    return True


def begin_producer_camera_takeover(camera_director, replay_director=None):
    """Give Producer Assist manual authority until Return Live/Auto Camera is used."""
    if camera_director:
        if hasattr(camera_director, "begin_manual_control"):
            camera_director.begin_manual_control()
        else:
            camera_director.mode = "off"
            camera_director.replay_active = False
            camera_director.return_home_at = None
            if hasattr(camera_director, "clear_sequence"):
                camera_director.clear_sequence()
    if replay_director and hasattr(replay_director, "begin_manual_control"):
        replay_director.begin_manual_control()


def set_producer_replay_speed(source, speed):
    try:
        setattr(source, "_producer_replay_speed", int(speed))
    except Exception:
        return


def replay_seek_appears_live(source):
    checker = getattr(source, "is_replay_at_live_edge", None)
    if not checker:
        return False
    try:
        return checker() is True
    except Exception:
        return False


def fallback_rewind_to_event_review(source, review_time):
    current_time_reader = getattr(source, "get_session_time", None)
    rewinder = getattr(source, "rewind_replay_frames", None)
    if not current_time_reader or not rewinder:
        return {"accepted": False, "method": "unavailable"}

    current_time = safe_float(current_time_reader(), default=0.0)
    delta_seconds = max(0.0, current_time - safe_float(review_time, default=0.0))
    if delta_seconds <= 0.0:
        return {"accepted": False, "method": "frame-rewind unavailable"}

    return_live = getattr(source, "return_to_live", None)
    if return_live:
        try:
            return_live()
        except Exception:
            pass

    frames = max(1, min(int(delta_seconds * 60), 60 * 60 * 10))
    try:
        accepted = bool(rewinder(frames))
    except Exception:
        accepted = False
    return {
        "accepted": accepted,
        "method": f"frame rewind ({delta_seconds:.1f}s)",
    }


def next_replay_speed(source, direction):
    current = safe_int(getattr(source, "_producer_replay_speed", 1), default=1)
    if direction == "reverse":
        speed = -1 if current >= 0 else max(current * 2, -4)
    else:
        speed = 2 if current <= 1 else min(current * 2, 8)
    set_producer_replay_speed(source, speed)
    return speed


def report_anthem_decision(decision, overlay_server=None):
    if decision.status == "ignored":
        return
    message = f"QUALIFYING: {decision.reason}"
    print(message)
    publish_producer_event(overlay_server, "info", "Qualifying Music", decision.reason)


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
            subtitle=f"Presented by {configured_crank_it_up_sponsor_name()}",
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

    if category == "race_recap":
        rows = build_race_recap_rows(source, engine)
        if rows:
            overlay_server.show_stat_panel(
                kind="race_recap",
                title="Race Recap",
                subtitle="Three-quarter reset",
                rows=rows,
                duration=24.0,
                dedupe_key="race_recap:three_quarter",
                minimum_interval=600.0,
            )
        return

    if category.startswith("race_stat:points_standings"):
        rows = build_points_standings_rows(source, engine)
        if rows:
            overlay_server.show_stat_panel(
                kind="points_standings",
                title="Championship Standings",
                subtitle="Top 20 entering tonight",
                rows=rows,
                duration=18.0,
                dedupe_key="points_standings",
                minimum_interval=900.0,
            )
        return

    if category in ("post_race_story", "post_race", "post_race_recap"):
        show_post_race_winner_card(overlay_server, source)
        rows = build_race_end_cap_rows(source, engine)
        if rows:
            overlay_server.show_stat_panel(
                kind="race_end_cap",
                title="Race Recap",
                subtitle="Unofficial finish and key race notes",
                rows=rows,
                duration=300.0,
                dedupe_key="race_end_cap:post_race",
                minimum_interval=9999.0,
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


def build_points_standings_rows(source=None, engine=None, limit=20):
    driver_lookup = {}
    if source and hasattr(source, "get_driver_lookup"):
        driver_lookup = source.get_driver_lookup() or {}
    if engine and getattr(engine, "league_context", None):
        driver_lookup = engine.league_context.enrich_driver_lookup(driver_lookup)

    standings = []
    seen = set()
    for driver in (driver_lookup or {}).values():
        stats = preferred_season_stats(driver)
        if not stats:
            continue
        points_position = safe_int((stats or {}).get("points_position"), 0)
        if points_position <= 0:
            continue
        name = str((driver or {}).get("name") or (stats or {}).get("name") or "").strip()
        number = str((driver or {}).get("number") or (stats or {}).get("car_number") or "").strip()
        key = (name.casefold(), number)
        if key in seen:
            continue
        seen.add(key)
        points_to_next = safe_int((stats or {}).get("points_to_next"), 0)
        wins = safe_int((stats or {}).get("wins"), 0)
        top_fives = safe_int((stats or {}).get("top_fives"), 0)
        detail_parts = []
        if points_to_next > 0:
            detail_parts.append(f"{points_to_next} pts to next")
        if wins > 0:
            detail_parts.append(f"{wins} win{'s' if wins != 1 else ''}")
        if top_fives > 0:
            detail_parts.append(f"{top_fives} top 5{'s' if top_fives != 1 else ''}")
        standings.append(
            {
                "points_position": points_position,
                "label": f"#{number} {name}".strip() if number else name,
                "value": ordinal(points_position),
                "detail": " | ".join(detail_parts) or "Championship contender",
            }
        )

    standings.sort(key=lambda row: row["points_position"])
    return [
        {
            "label": row["label"],
            "value": row["value"],
            "detail": row["detail"],
        }
        for row in standings[:limit]
    ]


def preferred_season_stats(driver):
    stats_by_scope = (driver or {}).get("league_stats_by_scope") or []
    if isinstance(stats_by_scope, dict):
        stats_by_scope = [stats_by_scope]
    for stats in stats_by_scope:
        if str((stats or {}).get("stats_scope") or "").strip().casefold() == "season":
            return stats
    stats = (driver or {}).get("league_stats") or {}
    if str((stats or {}).get("stats_scope") or "season").strip().casefold() in ("", "season"):
        return stats
    return {}


def log_race_event_for_item(item, overlay_server, source=None, camera_decision=None):
    if not overlay_server or not hasattr(overlay_server, "add_race_event_log"):
        return None

    details = race_event_log_details(item)
    if not details:
        return None

    car_idx = getattr(item, "camera_target_car_idx", None)
    if car_idx is None and camera_decision is not None:
        car_idx = getattr(camera_decision, "car_idx", None)

    driver = {}
    if car_idx is not None and source is not None:
        driver = (getattr(source, "get_driver_lookup", lambda: {})() or {}).get(car_idx, {})

    session_type = ""
    session_lap = 0
    live_session_num = None
    live_session_time = None
    if source is not None:
        session_type = str(getattr(source, "get_session_type", lambda: "")() or "")
        session_lap = safe_int(getattr(source, "get_lap", lambda: 0)(), 0)
        session_num_reader = getattr(source, "get_current_session_num", None)
        if session_num_reader:
            live_session_num = session_num_reader()
        session_time_reader = getattr(source, "get_session_time", None)
        if session_time_reader:
            live_session_time = session_time_reader()

    camera_group = (
        getattr(camera_decision, "group_name", "")
        or getattr(item, "camera_incident_group", "")
        or "TV1"
    )
    payload = {
        "car_idx": car_idx if car_idx is not None else -1,
        "car_number": driver.get("number", getattr(camera_decision, "car_number", "")),
        "driver_name": driver.get("name", ""),
        "session_type": session_type,
        "session_lap": session_lap,
        "camera_group": camera_group,
        "replay_session_num": (
            getattr(item, "replay_session_num", None)
            if getattr(item, "replay_session_num", None) is not None
            else live_session_num
        ),
        "replay_session_time": (
            getattr(item, "replay_session_time", None)
            if getattr(item, "replay_session_time", None) is not None
            else live_session_time
        ),
        "created_by": "RGC AI",
    }
    return overlay_server.add_race_event_log(
        details["title"],
        details["message"],
        payload,
        kind=details["kind"],
        status=details["status"],
    )


def race_event_log_details(item):
    category = str(getattr(item, "category", "") or "")
    message = str(getattr(item, "message", "") or "").strip()
    if not message:
        return None

    lower = message.lower()
    story_key = str(getattr(item, "dedupe_key", "") or "").split(":", 1)[0]
    skip_categories = {
        "sponsor_read",
        "booth_conversation",
        "race_story_follow_up",
        "crank_it_up",
        "crank_it_up_intro",
        "opening_welcome",
        "opening_track_info",
        "opening_race_outlook",
        "opening_pit_report",
        "opening_hype",
    }
    if category in skip_categories or category.startswith("opening_field_rundown"):
        return None

    if category == "incident":
        return {
            "kind": "incident",
            "title": "Incident",
            "message": message,
            "status": "needs review",
        }
    if category in ("pit_strategy", "green_pit_cycle_update", "caution_pit_summary"):
        return {
            "kind": "pit",
            "title": "Pit Road",
            "message": message,
            "status": "logged",
        }
    if category == "penalty":
        return {
            "kind": "penalty",
            "title": "Penalty",
            "message": message,
            "status": "logged",
        }
    if category == "race_control":
        return {
            "kind": "race_control",
            "title": "Race Control",
            "message": message,
            "status": "logged",
        }
    if category == "fastest_lap":
        return {
            "kind": "race_event",
            "title": "Fastest Lap",
            "message": message,
            "status": "logged",
        }
    if category in (
        "race_recap",
        "post_race",
        "post_race_recap",
        "post_race_interviews",
        "post_race_signoff",
    ):
        return {
            "kind": "race_event",
            "title": "Race Recap",
            "message": message,
            "status": "logged",
        }
    if category == "restart_launch":
        return {
            "kind": "race_event",
            "title": "Restart",
            "message": message,
            "status": "logged",
        }
    if category == "stage_end":
        return {
            "kind": "race_event",
            "title": "Stage",
            "message": message,
            "status": "logged",
        }
    if category == "race_story":
        if story_key == "lead_change" or "lead" in lower and "leader" not in lower:
            title = "Lead Change"
            kind = "lead_change"
        elif story_key in ("pass", "top_five_pass") or any(
            word in lower for word in ("pass", "passes", "move", "moved", "takes")
        ):
            title = "Pass / Position"
            kind = "pass"
        elif "battle" in lower or "side by side" in lower or "three wide" in lower:
            title = "Battle"
            kind = "race_event"
        else:
            title = "Race Story"
            kind = "race_event"
        return {
            "kind": kind,
            "title": title,
            "message": message,
            "status": "logged",
        }
    if category.startswith("race_stat") or category.startswith("race_insight"):
        return {
            "kind": "race_event",
            "title": "Race Insight",
            "message": message,
            "status": "logged",
        }
    if category in ("final_laps_battle", "late_caution_note", "lucky_dog", "race_progress"):
        return {
            "kind": "race_event",
            "title": "Race Event",
            "message": message,
            "status": "logged",
        }
    return None


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


def show_sponsor_commercial_if_available(item, overlay_server):
    if not overlay_server:
        return False
    if str(getattr(item, "category", "") or "") != "sponsor_read":
        return False
    mentions = sponsor_mentions_for_message(getattr(item, "message", ""))
    if not mentions:
        return False
    video_url = sponsor_video_for_mentions(mentions)
    if not video_url:
        return False
    graphics = sponsor_graphics_for_mentions(mentions)
    overlay_server.show_special_presentation(
        kind="sponsor_commercial",
        title=" / ".join(mentions),
        subtitle="Commercial Break",
        duration=60.0,
        graphics=graphics,
        video_url=video_url,
    )
    print(f"SPONSOR: playing commercial for {' / '.join(mentions)}.")
    publish_producer_event(
        overlay_server,
        "info",
        "Sponsor commercial",
        f"Playing commercial for {' / '.join(mentions)}.",
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
        *RACE_SPONSOR_NAMES,
        SPONSOR_READ_NAME,
        SPONSOR_READ_NAME_2,
        SPONSOR_READ_NAME_3,
        OVERLAY_RACE_SPONSOR,
        SPONSOR_READ_CAUSE_NAME,
        "RGC Motorsports",
        "Autism Awareness",
    ):
        for name in split_sponsor_names(raw):
            if name and name not in names:
                names.append(name)
    return names


def first_configured_sponsor_name():
    names = configured_sponsor_names()
    return names[0] if names else "RGC Motorsports"


def configured_crank_it_up_sponsor_name():
    return str(CRANK_IT_UP_SPONSOR_NAME or "").strip() or first_configured_sponsor_name()


def next_manual_sponsor_name():
    global MANUAL_SPONSOR_INDEX
    names = configured_sponsor_names()
    if not names:
        return ""
    sponsor_name = names[MANUAL_SPONSOR_INDEX % len(names)]
    MANUAL_SPONSOR_INDEX += 1
    return sponsor_name


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
    for sponsor_name, graphic in RACE_SPONSOR_GRAPHICS.items():
        if sponsor_name_matches_text(sponsor_name, mention.lower()):
            return graphic
    graphic = find_brand_graphic_for_name(mention)
    if graphic:
        return graphic
    if "autism" in mention_text:
        if SPONSOR_READ_CAUSE_LOGO:
            return SPONSOR_READ_CAUSE_LOGO
        return find_brand_graphic(("autism",), "/assets/autism_awareness.png")
    if "rgc" in mention_text:
        return find_brand_graphic(("rgc", "motor"), "/assets/rgc_motorsports.png")
    return OVERLAY_BRAND_GRAPHICS[0] if OVERLAY_BRAND_GRAPHICS else ""


def sponsor_video_for_mentions(mentions):
    for mention in mentions:
        video = sponsor_video_for_mention(mention)
        if video:
            return video
    return ""


def sponsor_video_for_mention(mention):
    for sponsor_name, video in RACE_SPONSOR_VIDEOS.items():
        if sponsor_name_matches_text(sponsor_name, str(mention or "").lower()):
            return video
    return ""


def find_brand_graphic_for_name(name):
    name_tokens = sponsor_tokens(name)
    if not name_tokens:
        return ""
    for sponsor_name, graphic in RACE_SPONSOR_GRAPHICS.items():
        if sponsor_name_matches_text(sponsor_name, str(name or "").lower()):
            return graphic
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
    sponsor_name = configured_crank_it_up_sponsor_name()
    intro = f"It is time to Crank It Up. Crank It Up is presented by {sponsor_name}."
    feature_seconds = max(1.0, float(duration_seconds or DEFAULT_CRANK_IT_UP_SECONDS))

    if overlay_server:
        overlay_server.show_special_presentation(
            kind="crank_it_up",
            title="Crank It Up",
            subtitle=f"Presented by {sponsor_name}",
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
    sponsor_graphic = (
        CRANK_IT_UP_SPONSOR_GRAPHIC
        or sponsor_graphic_for_mention(configured_crank_it_up_sponsor_name())
    )
    return [
        graphic
        for graphic in (sponsor_graphic, CRANK_IT_UP_ICON_GRAPHIC)
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


def build_race_recap_rows(source, engine):
    if not engine:
        return []
    race_state = getattr(engine.race_intelligence, "get_race_state", lambda: None)()
    current_lap = safe_int(getattr(race_state, "current_lap", 0), 0)
    total_laps = safe_int(getattr(race_state, "total_laps", 0), 0)
    rows = []
    if current_lap and total_laps:
        rows.append(
            {
                "label": "Distance",
                "value": f"Lap {current_lap}/{total_laps}",
                "detail": "Three-quarter reset",
            }
        )

    caution_count = safe_int(getattr(race_state, "caution_count", 0), 0)
    rows.append(
        {
            "label": "Cautions",
            "value": str(caution_count),
            "detail": "Caution-free" if caution_count == 0 else "Yellow flags so far",
        }
    )

    lead_changes = safe_int(getattr(engine, "lead_change_count", 0), 0)
    rows.append(
        {
            "label": "Lead Changes",
            "value": str(lead_changes),
            "detail": "Tracked at the front",
        }
    )

    fastest_lap_tracker = getattr(engine, "fastest_lap_tracker", None)
    fastest_idx = getattr(fastest_lap_tracker, "fastest_car_idx", None)
    fastest_time = getattr(fastest_lap_tracker, "fastest_time", None)
    if fastest_idx is not None and fastest_time:
        drivers = source.get_driver_lookup() if source else {}
        driver = drivers.get(fastest_idx, {})
        rows.append(
            {
                "label": "Fastest Lap",
                "value": fastest_lap_tracker.format_lap_time(fastest_time),
                "detail": (
                    f"#{driver.get('number', '?')} "
                    f"{driver.get('name', f'Car {fastest_idx}')}"
                ),
            }
        )

    movers = getattr(engine.race_intelligence, "get_biggest_movers", lambda *_: [])(1)
    if movers and getattr(movers[0], "positions_gained", 0) > 0:
        mover = movers[0]
        rows.append(
            {
                "label": "Biggest Mover",
                "value": f"+{mover.positions_gained}",
                "detail": f"#{mover.car_number} {mover.driver_name}",
            }
        )

    fading = getattr(engine.race_intelligence, "get_fading_drivers", lambda *_: [])(1)
    if fading and getattr(fading[0], "positions_lost", 0) > 0:
        driver = fading[0]
        rows.append(
            {
                "label": "Biggest Drop",
                "value": f"-{driver.positions_lost}",
                "detail": f"#{driver.car_number} {driver.driver_name}",
            }
        )
    return rows


def build_race_end_cap_rows(source, engine):
    results = source.get_results() if source else []
    drivers = source.get_driver_lookup() if source else {}
    ordered = sorted_results_by_position(results)
    rows = []

    if ordered:
        winner = ordered[0]
        winner_driver = drivers.get(winner.get("CarIdx"), {})
        rows.append(
            {
                "label": "Winner",
                "value": f"#{winner_driver.get('number', '?')}",
                "detail": winner_driver.get("name", f"Car {winner.get('CarIdx')}"),
            }
        )

    podium = []
    for car in ordered[:3]:
        car_idx = car.get("CarIdx")
        driver = drivers.get(car.get("CarIdx"), {})
        position = normalized_result_position(car, results)
        driver_name = driver.get("name", f"Car {car_idx}")
        podium.append(
            f"{ordinal(position)} #{driver.get('number', '?')} "
            f"{driver_name}"
        )
    if podium:
        rows.append(
            {
                "label": "Podium",
                "value": str(len(podium)),
                "detail": " | ".join(podium),
            }
        )

    race_state = (
        getattr(engine.race_intelligence, "get_race_state", lambda: None)()
        if engine
        else None
    )
    caution_count = safe_int(getattr(race_state, "caution_count", 0), 0)
    lead_changes = safe_int(getattr(engine, "lead_change_count", 0), 0) if engine else 0
    rows.append(
        {
            "label": "Race Story",
            "value": f"{caution_count}Y / {lead_changes}L",
            "detail": (
                "Caution-free finish"
                if caution_count == 0
                else f"{caution_count} caution{'s' if caution_count != 1 else ''}; "
                f"{lead_changes} tracked lead change{'s' if lead_changes != 1 else ''}"
            ),
        }
    )

    most_led = race_end_most_laps_led_row(results, drivers, engine)
    if most_led:
        rows.append(most_led)

    lead_lap = race_end_lead_lap_row(results)
    if lead_lap:
        rows.append(lead_lap)

    fastest_lap_tracker = getattr(engine, "fastest_lap_tracker", None) if engine else None
    fastest_idx = getattr(fastest_lap_tracker, "fastest_car_idx", None)
    fastest_time = getattr(fastest_lap_tracker, "fastest_time", None)
    if fastest_idx is not None and fastest_time:
        driver = drivers.get(fastest_idx, {})
        rows.append(
            {
                "label": "Fastest Lap",
                "value": fastest_lap_tracker.format_lap_time(fastest_time),
                "detail": (
                    f"#{driver.get('number', '?')} "
                    f"{driver.get('name', f'Car {fastest_idx}')}"
                ),
            }
        )

    movers = (
        getattr(engine.race_intelligence, "get_biggest_movers", lambda *_: [])(1)
        if engine
        else []
    )
    if movers and getattr(movers[0], "positions_gained", 0) > 0:
        mover = movers[0]
        rows.append(
            {
                "label": "Biggest Mover",
                "value": f"+{mover.positions_gained}",
                "detail": f"#{mover.car_number} {mover.driver_name}",
            }
        )

    return rows[:7]


def race_end_most_laps_led_row(results, drivers, engine):
    best_car_idx = None
    best_laps = 0
    for car in results or []:
        laps_led = max(
            safe_int(car.get("LapsLed", 0), 0),
            safe_int(car.get("LedLaps", 0), 0),
            safe_int(car.get("LeaderLaps", 0), 0),
        )
        if laps_led > best_laps:
            best_laps = laps_led
            best_car_idx = car.get("CarIdx")

    if best_laps <= 0 and engine:
        led_counts = getattr(engine, "leader_laps_led", {}) or {}
        if led_counts:
            best_car_idx, best_laps = max(
                led_counts.items(),
                key=lambda item: safe_int(item[1], 0),
            )

    if best_car_idx is None or best_laps <= 0:
        return None

    driver = drivers.get(best_car_idx, {})
    return {
        "label": "Most Laps Led",
        "value": str(best_laps),
        "detail": f"#{driver.get('number', '?')} {driver.get('name', f'Car {best_car_idx}')}",
    }


def race_end_lead_lap_row(results):
    ordered = sorted_results_by_position(results)
    if not ordered:
        return None

    starters = len([car for car in results or [] if car.get("CarIdx") is not None])
    laps_behind_available = any(
        key in car
        for car in ordered
        for key in ("LapsBehind", "ClassLapsBehind")
    )
    leader_laps = max(
        safe_int(ordered[0].get("LapsComplete", 0), 0),
        safe_int(ordered[0].get("Lap", 0), 0),
    )
    if leader_laps <= 0:
        leader_laps = max(
            max(
                safe_int(car.get("LapsComplete", 0), 0),
                safe_int(car.get("Lap", 0), 0),
            )
            for car in ordered
        )

    lead_lap_finishers = 0
    for car in ordered:
        car_laps = max(
            safe_int(car.get("LapsComplete", 0), 0),
            safe_int(car.get("Lap", 0), 0),
        )
        laps_behind_values = [
            safe_int(car.get(key), 0)
            for key in ("LapsBehind", "ClassLapsBehind")
            if key in car
        ]
        if laps_behind_available:
            if laps_behind_values and max(laps_behind_values) == 0:
                lead_lap_finishers += 1
            continue
        if leader_laps > 0 and car_laps >= leader_laps:
            lead_lap_finishers += 1

    if starters <= 0:
        return None
    return {
        "label": "Lead Lap Finishers",
        "value": f"{lead_lap_finishers}/{starters}",
        "detail": "Drivers who finished on the lead lap",
    }


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


def build_producer_pit_road_rows(source, engine, limit=12):
    if not source or not engine:
        return []
    current_lap = best_current_lap(source)
    current_positions = build_current_position_lookup(source.get_results())
    states = list(getattr(engine.pit_strategy_detector, "driver_states", {}).values())
    states = [
        state
        for state in states
        if getattr(state, "on_pit_road", False)
        or safe_int(getattr(state, "last_pit_lap", 0), 0) > 0
    ]
    states.sort(
        key=lambda state: (
            0 if getattr(state, "on_pit_road", False) else 1,
            -safe_int(getattr(state, "last_pit_lap", 0), 0),
            str(getattr(state, "driver_name", "")),
        )
    )
    rows = []
    for state in states[:limit]:
        last_pit_lap = safe_int(getattr(state, "last_pit_lap", 0), 0)
        on_pit_road = bool(getattr(state, "on_pit_road", False))
        pit_lane_seconds = (
            float(getattr(state, "current_pit_lane_seconds", 0.0) or 0.0)
            if on_pit_road
            else float(getattr(state, "last_pit_lane_seconds", 0.0) or 0.0)
        )
        pit_stop_seconds = (
            float(getattr(state, "current_pit_stop_seconds", 0.0) or 0.0)
            if on_pit_road
            else float(getattr(state, "last_pit_stop_seconds", 0.0) or 0.0)
        )
        laps_since_pit = (
            max(0, current_lap - last_pit_lap)
            if last_pit_lap > 0 and current_lap > 0 and not on_pit_road
            else 0
        )
        rows.append(
            {
                "car_idx": safe_int(getattr(state, "car_idx", 0), 0),
                "car_number": str(getattr(state, "car_number", "") or ""),
                "driver_name": str(getattr(state, "driver_name", "") or ""),
                "status": "On pit road" if on_pit_road else "Last stop",
                "last_pit_lap": last_pit_lap,
                "laps_since_pit": laps_since_pit,
                "pit_lane_seconds": pit_lane_seconds,
                "pit_stop_seconds": pit_stop_seconds,
                "service_guess": pit_service_guess(state, on_pit_road),
                "position_summary": pit_position_summary(
                    state,
                    current_positions.get(getattr(state, "car_idx", None), 0),
                ),
            }
        )
    return rows


def pit_service_guess(state, on_pit_road=False):
    if on_pit_road:
        return "On pit road now — service still developing."
    lane_seconds = float(getattr(state, "last_pit_lane_seconds", 0.0) or 0.0)
    stop_seconds = float(getattr(state, "last_pit_stop_seconds", 0.0) or 0.0)
    gain = safe_int(getattr(state, "last_pit_position_gain", 0), 0)
    if stop_seconds >= 25.0 or lane_seconds >= 65.0:
        return "Possible damage repair / extended service"
    if stop_seconds >= 12.0:
        return "Likely full service"
    if stop_seconds >= 8.0:
        return "Likely normal service"
    if stop_seconds > 0 and gain >= 2:
        return "Possible two-tire or fuel-only track-position stop"
    if stop_seconds > 0 and stop_seconds < 4.0:
        return "Possible fuel-only, drive-through, or quick adjustment"
    if stop_seconds > 0:
        return "Short stop / service call"
    if lane_seconds > 0:
        return "Pit lane trip, service unclear"
    return "Service unknown"


def pit_position_summary(state, current_position=0):
    parts = []
    entry_position = safe_int(getattr(state, "pit_entry_position", 0), 0)
    exit_position = safe_int(getattr(state, "pit_exit_position", 0), 0)
    gain = safe_int(getattr(state, "last_pit_position_gain", 0), 0)
    if entry_position > 0:
        parts.append(f"in P{entry_position}")
    if exit_position > 0:
        parts.append(f"out P{exit_position}")
    elif current_position > 0:
        parts.append(f"now P{current_position}")
    if gain > 0:
        parts.append(f"+{gain} on pit road")
    return " / ".join(parts)


def best_current_lap(source):
    laps = [safe_int(getattr(source, "get_lap", lambda: 0)(), 0)]
    for car in getattr(source, "get_results", lambda: [])() or []:
        laps.append(safe_int(car.get("LapsComplete", car.get("Lap", 0)), 0))
        laps.append(safe_int(car.get("Lap", car.get("LapsComplete", 0)), 0))
    return max(laps, default=0)


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


def safe_float(value, default=0.0):
    try:
        return float(value)
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

    category = str(getattr(item, "category", "") or "")
    opening_intro = category.startswith("opening_field_rundown")
    rundown_number_only = category.startswith(
        (
            "opening_field_rundown",
            "quarter_field_rundown",
            "three_quarter_field_rundown",
            "long_green_field_rundown",
        )
    )

    update_overlay_focused_driver(
        overlay_server,
        source,
        camera_decision,
        opening_intro=opening_intro,
        number_only_card=rundown_number_only,
    )


def show_post_race_winner_card(overlay_server, source):
    results = sorted_results_by_position(source.get_results() if source else [])
    if not results:
        return
    winner = results[0]
    car_idx = winner.get("CarIdx")
    if car_idx is None:
        return
    driver = (source.get_driver_lookup() if source else {}).get(car_idx, {})
    camera_decision = SimpleNamespace(
        status="held",
        car_idx=car_idx,
        car_number=str(driver.get("number", "") or ""),
        role="post_race_winner",
    )
    update_overlay_focused_driver(
        overlay_server,
        source,
        camera_decision,
        duration=300.0,
    )


def should_update_overlay_for_camera_update(camera_decision):
    return getattr(camera_decision, "role", "") == "lineup"


def update_overlay_focused_driver(
    overlay_server,
    source,
    camera_decision,
    duration=12.0,
    opening_intro=False,
    number_only_card=False,
):
    if camera_decision is None:
        return
    allowed_statuses = ("suggested", "switched", "held")
    if opening_intro:
        allowed_statuses = (*allowed_statuses, "failed")
    if camera_decision.status not in allowed_statuses:
        return
    car_idx = camera_decision.car_idx
    if car_idx is None:
        return

    driver = dict(source.get_driver_lookup().get(car_idx, {}) or {})
    driver["car_idx"] = car_idx
    driver.setdefault("CarIdx", car_idx)
    driver_name = driver.get("name", "")
    car_number = driver.get("number", camera_decision.car_number)
    if not driver_name and not car_number:
        return

    country = build_featured_driver_country(driver)
    story = build_featured_driver_profile(driver)
    car_render_info = build_featured_driver_render_info(
        driver,
        require_live_render_match=opening_intro,
    )
    car_image_url = car_render_info.get("image_url", "")
    if opening_intro or number_only_card:
        car_image_url = ""
    results = featured_driver_results(source, opening_intro=opening_intro)
    position_info = featured_driver_position_info(
        car_idx,
        results,
        driver_lookup=source.get_driver_lookup(),
        use_position_as_start=opening_intro,
        include_interval=not opening_intro,
    )
    overlay_server.show_featured_driver(
        car_number=car_number,
        driver_name=driver_name,
        car_idx=car_idx,
        story=story,
        country=country,
        duration=duration,
        car_image_url=car_image_url,
        number_style=car_render_info.get("number_style", {}),
        position=position_info["position"],
        class_name=position_info["class_name"],
        class_position=position_info["class_position"],
        class_size=position_info["class_size"],
        starting_position=position_info["starting_position"],
        position_delta=position_info["position_delta"],
        interval=position_info["interval"],
        speed="",
    )


def featured_driver_results(source, opening_intro=False):
    if opening_intro:
        grid_reader = getattr(source, "get_starting_grid", None)
        if callable(grid_reader):
            try:
                grid = grid_reader() or []
                if grid:
                    return grid
            except Exception:
                pass
    return source.get_results()


def featured_driver_position_info(
    car_idx,
    results,
    driver_lookup=None,
    use_position_as_start=False,
    include_interval=True,
):
    ordered_results = sorted_results_by_position(results)
    multiclass = build_multiclass_context(results, driver_lookup or {})
    for car in ordered_results:
        if car.get("CarIdx") != car_idx:
            continue
        position = normalized_result_position(car, results)
        class_position = multiclass.positions.get(car_idx)
        starting_position = safe_int(
            car.get("StartingPosition")
            or car.get("StartPosition")
            or car.get("QualifyingPosition"),
            0,
        )
        if use_position_as_start and starting_position <= 0:
            starting_position = position
        return {
            "position": position,
            "class_name": getattr(class_position, "class_name", ""),
            "class_position": getattr(class_position, "class_position", 0),
            "class_size": getattr(class_position, "class_size", 0),
            "starting_position": starting_position,
            "position_delta": (
                starting_position - position
                if starting_position > 0 and position > 0
                else 0
            ),
            "interval": (
                featured_driver_interval(car, ordered_results, results)
                if include_interval
                else ""
            ),
            "speed": "",
        }
    return {
        "position": 0,
        "class_name": "",
        "class_position": 0,
        "class_size": 0,
        "starting_position": 0,
        "position_delta": 0,
        "interval": "",
        "speed": "",
    }


def sorted_results_by_position(results):
    return sorted(
        list(results or []),
        key=lambda car: normalized_result_position(car, results) or 999,
    )


def normalized_result_position(car, results):
    zero_based = any(safe_int(row.get("Position"), 999) == 0 for row in results or [])
    raw_position = safe_int(car.get("Position"), 0)
    return raw_position + 1 if zero_based and raw_position >= 0 else raw_position


def featured_driver_interval(car, ordered_results, all_results):
    position = normalized_result_position(car, all_results)
    if position <= 1:
        return "Leader"

    car_gap = safe_float(car.get("Time", car.get("Gap", 0.0)), 0.0)
    car_ahead = None
    for candidate in ordered_results:
        if normalized_result_position(candidate, all_results) == position - 1:
            car_ahead = candidate
            break
    if car_ahead:
        ahead_gap = safe_float(car_ahead.get("Time", car_ahead.get("Gap", 0.0)), 0.0)
        if car_gap > 0 and car_gap >= ahead_gap:
            return f"+{car_gap - ahead_gap:.2f} to next"

    for key in ("Interval", "interval"):
        value = str(car.get(key, "") or "").strip()
        if value:
            return f"{value} to next" if value.startswith("+") else value
    return ""


def normalize_country_value(value):
    text = " ".join(str(value or "").replace("_", " ").strip().split())
    if not text:
        return ""
    lookup = text.lower().replace(".", "")
    return COUNTRY_ALIASES.get(lookup, text)


def build_featured_driver_country(driver):
    for key in (
        "country",
        "Country",
        "country_name",
        "CountryName",
        "country_code",
        "CountryCode",
        "flair_name",
        "FlairName",
        "flair_country_code",
        "flairCountryCode",
        "flair",
        "Flair",
        "club_country",
        "ClubCountry",
    ):
        country = normalize_country_value(driver.get(key))
        if country:
            return country

    for key in ("club", "Club", "club_name", "ClubName"):
        club = normalize_country_value(driver.get(key))
        if not club:
            continue
        club_key = club.lower().replace(".", "")
        if club_key in US_STATE_NAMES:
            return f"{club}, United States"
        if club_key in CANADIAN_PROVINCES:
            return f"{club}, Canada"
        return club

    return ""


def build_featured_driver_profile(driver):
    details = []
    team_name = str(driver.get("team_name", "") or "").strip()
    hometown = str(driver.get("hometown", "") or driver.get("home_town", "") or "").strip()
    state = str(driver.get("state", "") or "").strip()

    if team_name:
        details.append(team_name)
    if hometown and state:
        details.append(f"{hometown}, {state}")
    elif hometown:
        details.append(hometown)

    return " • ".join(details)


def build_featured_driver_story(driver):
    league_keys = (
        "team_name",
        "driving_style",
        "hometown",
        "home_town",
        "league_notes",
        "notes",
        "league_profile",
    )
    has_league_details = any(driver.get(key) for key in league_keys)
    if not has_league_details:
        return build_featured_driver_country(driver) or "Featured driver"

    return build_featured_driver_profile(driver) or "Featured driver"


def build_featured_driver_image(driver):
    return build_featured_driver_render_info(driver).get("image_url", "")


def build_featured_driver_render_info(driver, require_live_render_match=False):
    cache_key = featured_driver_render_cache_key(driver)
    for key in ("car_image_url", "paint_image_url"):
        value = str(driver.get(key, "") or "").strip()
        if value.startswith(("http://", "https://", "/")):
            return {"image_url": value, "number_style": {}}

    manual_image = str(driver.get("car_image", "") or "").strip()
    if manual_image.startswith(("http://", "https://", "/assets/", "/paint-previews/")):
        return {"image_url": manual_image, "number_style": {}}
    if manual_image:
        image_path = Path(manual_image).expanduser()
        if not image_path.is_absolute():
            image_path = Path(__file__).resolve().parent / image_path
        preview_path = ensure_preview_file(image_path, driver)
        if preview_path:
            return {"image_url": f"/paint-previews/{preview_path.name}", "number_style": {}}
    if USE_IRACING_RENDERED_CAR_IMAGES:
        sim_racing_apps_info = build_sim_racing_apps_car_render_info(driver)
        if sim_racing_apps_info.get("image_url") or sim_racing_apps_info.get("number_style"):
            if (
                require_live_render_match
                and sim_racing_apps_info.get("image_url")
                and not is_driver_specific_render_image_url(
                    sim_racing_apps_info.get("image_url")
                )
            ):
                return {
                    "image_url": "",
                    "number_style": sim_racing_apps_info.get("number_style", {}),
                }
            return remember_featured_driver_render_info(cache_key, sim_racing_apps_info)
        if require_live_render_match:
            return {"image_url": "", "number_style": {}}
        cached = last_good_featured_driver_render_info(cache_key)
        if cached:
            return cached
        render_url = build_iracing_render_image_url(driver)
        if render_url:
            return {"image_url": render_url, "number_style": {}}
    return {"image_url": "", "number_style": {}}


def featured_driver_render_cache_key(driver):
    car_idx = safe_int(
        driver.get("car_idx")
        or driver.get("CarIdx")
        or driver.get("id")
        or driver.get("Id"),
        -1,
    )
    number = " ".join(
        str(driver.get("number") or driver.get("car_number") or driver.get("CarNumber") or "")
        .strip()
        .casefold()
        .split()
    )
    name = " ".join(
        str(driver.get("name") or driver.get("driver_name") or driver.get("UserName") or "")
        .strip()
        .casefold()
        .replace(".", "")
        .split()
    )
    if name or number:
        return (car_idx, number, name)
    if car_idx >= 0:
        return (car_idx, "", "")
    return None


def remember_featured_driver_render_info(cache_key, render_info):
    render_info = normalize_featured_driver_render_info(render_info)
    if cache_key and (render_info.get("image_url") or render_info.get("number_style")):
        _FEATURED_DRIVER_RENDER_INFO_CACHE[cache_key] = dict(render_info)
    return render_info


def last_good_featured_driver_render_info(cache_key):
    cached = _FEATURED_DRIVER_RENDER_INFO_CACHE.get(cache_key) if cache_key else None
    return dict(cached) if cached else {}


def normalize_featured_driver_render_info(render_info):
    if not isinstance(render_info, dict):
        return {}
    image_url = str(render_info.get("image_url") or "").strip()
    number_style = render_info.get("number_style")
    number_style = dict(number_style) if isinstance(number_style, dict) else {}
    if not image_url and not number_style:
        return {}
    return {
        "image_url": image_url,
        "number_style": number_style,
    }


def is_driver_specific_render_image_url(image_url):
    text = str(image_url or "").lower()
    return any(
        marker in text
        for marker in (
            "carcustpaint=",
            "car_num_",
            "car_",
            "cust_id=",
            "custid=",
        )
    )


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
    race_control_service = RaceControlService(enabled=RACE_ADMIN_MODE)
    discord_reporter = DiscordRaceReporter()
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
        sync_producer_control_state(
            overlay_server,
            engine,
            booth,
            camera_director,
            race_control_service,
            music_volume=producer_music_volume(caution_audio_bed, practice_presentation_director),
        )
        print(f"Overlay: ON ({overlay_url})")
        print(f"Producer Assist: {overlay_server.producer_url}")
        if overlay_server.producer_share_url != overlay_server.producer_url:
            print(f"Producer helper link: {overlay_server.producer_share_url}")
        overlay_server.add_producer_event(
            kind="info",
            title="Overlay",
            message=(
                f"Overlay: ON ({overlay_url}) | Producer: {overlay_server.producer_url} "
                f"| Helper: {overlay_server.producer_share_url}"
            ),
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
    print(f"Race Admin Mode: {'ON' if race_control_service.enabled else 'OFF'}")
    print(f"Discord Race Report: {'ON' if discord_reporter.ready() else 'OFF'}")
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
            race_control_service,
            discord_reporter,
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
        discord_reporter.reset()
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
            race_control_service,
            discord_reporter,
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
