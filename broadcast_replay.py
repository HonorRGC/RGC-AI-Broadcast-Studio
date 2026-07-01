import os
import sys
import time

PROJECT_ROOT = os.path.dirname(os.path.abspath(__file__))

if PROJECT_ROOT not in sys.path:
    sys.path.insert(0, PROJECT_ROOT)

from broadcaster.telemetry import IRacingTelemetry

from production.editorial_producer import EditorialProducer, EditorialDecisionType
from production.pit_strategy_detector import PitStrategyDetector
from production.incident_detector import IncidentDetector
from production.race_intelligence import RaceIntelligence
from production.opening_director import OpeningDirector
from production.commentary_cleaner import CommentaryCleaner
from production.openai_director import OpenAIDirector

from broadcast.booth import BroadcastBooth
from broadcast.broadcast_queue import BroadcastQueue


TICK_SECONDS = 0.5
ENABLE_INCIDENT_DETECTION_AFTER_LAP = 2


def safe_sdk_read(telemetry, key):
    try:
        return telemetry.ir[key]
    except Exception:
        return None


def should_skip_message(message, current_lap):
    if not message:
        return True

    text = message.strip().lower()

    if text.startswith("we pick up this race") and current_lap <= 1:
        return True

    if text.startswith("tonight we are racing at"):
        return True

    if text.startswith("here is the current running order through the top twenty"):
        return True

    if text.startswith("checkered flag is out"):
        return True

    return False


def main():
    telemetry = IRacingTelemetry()

    editorial_producer = EditorialProducer()
    pit_strategy_detector = PitStrategyDetector()
    incident_detector = IncidentDetector()
    race_intelligence = RaceIntelligence()
    opening_director = OpeningDirector()
    commentary_cleaner = CommentaryCleaner()
    openai_director = OpenAIDirector()

    booth = BroadcastBooth()
    broadcast_queue = BroadcastQueue()

    print("=" * 60)
    print("RGC AI Broadcast Studio - iRacing Replay Broadcast")
    print("=" * 60)
    print("Open an iRacing replay, press play, then run this.")
    print(f"OpenAI: {'ON' if openai_director.is_enabled() else 'OFF'}")
    print("=" * 60)

    print("Connecting to iRacing SDK...")

    while not telemetry.startup():
        print("Waiting for iRacing...")
        time.sleep(2)

    print("Connected.")
    print("Waiting for replay playback...")
    print("=" * 60)

    try:
        while telemetry.is_connected():
            is_replay_playing = bool(safe_sdk_read(telemetry, "IsReplayPlaying"))

            if not is_replay_playing:
                print("Replay is not playing. Press play in iRacing...")
                time.sleep(2)
                continue

            results = telemetry.get_results()
            driver_lookup = telemetry.get_driver_lookup()
            current_lap = telemetry.get_lap()
            total_laps = telemetry.get_total_laps()
            session_flags = telemetry.get_session_flags()
            pit_road_status = telemetry.get_car_idx_on_pit_road()

            race_knowledge = race_intelligence.update(
                results=results,
                driver_lookup=driver_lookup,
                current_lap=current_lap,
                total_laps=total_laps,
                session_flags=session_flags,
                pit_road_status=pit_road_status,
            )

            race_state = race_intelligence.get_race_state()

            opening_segments = opening_director.update(
                telemetry=telemetry,
                results=results,
                driver_lookup=driver_lookup,
                current_lap=current_lap,
            )

            for segment in opening_segments:
                broadcast_queue.add(
                    segment.message,
                    priority=segment.priority,
                    category=segment.category,
                    protected=True,
                    speaker=segment.speaker,
                )

            can_call_race = (
                opening_director.is_complete()
                and race_state.can_call_race()
            )

            if can_call_race:
                editorial_producer.submit_race_knowledge(race_knowledge)

                editorial_decision = editorial_producer.choose_next_item(
                    race_state=race_state
                )

                if (
                    editorial_decision.decision_type == EditorialDecisionType.AIR_NOW
                    and editorial_decision.item
                ):
                    item = editorial_decision.item
                    fallback_summary = commentary_cleaner.clean(item.summary)

                    if item.speaker == "lead":
                        final_summary = openai_director.generate_commentary(
                            speaker="lead",
                            assignment=item,
                            race_state=race_state,
                            race_knowledge=race_knowledge,
                            fallback_text=fallback_summary,
                        )
                    else:
                        final_summary = fallback_summary

                    final_summary = commentary_cleaner.clean(final_summary)

                    broadcast_queue.add(
                        final_summary,
                        priority=item.priority,
                        category=item.category,
                        protected=False,
                        speaker=item.speaker,
                    )

                if current_lap >= ENABLE_INCIDENT_DETECTION_AFTER_LAP:
                    incident_events = incident_detector.analyze(
                        results=results,
                        driver_lookup=driver_lookup,
                        current_lap=current_lap,
                        track_surface_status=telemetry.get_car_idx_track_surface(),
                        track_surface_material_status=telemetry.get_car_idx_track_surface_material(),
                        lap_dist_pct_status=telemetry.get_car_idx_lap_dist_pct(),
                        est_time_status=telemetry.get_car_idx_est_time(),
                        pit_road_status=pit_road_status,
                    )

                    for incident_event in incident_events:
                        cleaned_message = commentary_cleaner.clean(
                            incident_event.message
                        )

                        broadcast_queue.add(
                            cleaned_message,
                            priority=incident_event.importance,
                            category="incident",
                            protected=True,
                            speaker="lead",
                        )

                pit_events = pit_strategy_detector.analyze(
                    results=results,
                    driver_lookup=driver_lookup,
                    pit_road_status=pit_road_status,
                    current_lap=current_lap,
                    under_caution=race_state.is_caution,
                )

                for pit_event in pit_events:
                    editorial_producer.submit_pit_event(pit_event)

                    cleaned_message = commentary_cleaner.clean(
                        pit_event.message
                    )

                    broadcast_queue.add(
                        cleaned_message,
                        priority=pit_event.importance,
                        category="pit_strategy",
                        protected=True,
                        speaker="sarah",
                    )

            next_item = broadcast_queue.next_item()

            if next_item:
                message = commentary_cleaner.clean(next_item.message or "")

                if not should_skip_message(message, current_lap):
                    booth.broadcast(message, speaker=next_item.speaker)

            time.sleep(TICK_SECONDS)

    except KeyboardInterrupt:
        print()
        print("Replay broadcast stopped.")

    print("=" * 60)
    print("Replay broadcast complete.")
    print("=" * 60)


if __name__ == "__main__":
    main()