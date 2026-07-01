import os
import sys
import time

PROJECT_ROOT = os.path.dirname(os.path.abspath(__file__))

if PROJECT_ROOT not in sys.path:
    sys.path.insert(0, PROJECT_ROOT)

from replay.replay_telemetry import ReplayTelemetry

from broadcaster.race_brain import RaceBrain
from broadcaster.producer import Producer
from broadcaster.event_queue import EventQueue
from broadcaster.race_director import RaceDirector, RacePhase

from production.broadcast_producer import BroadcastProducer
from production.editorial_producer import EditorialProducer, EditorialDecisionType
from production.pit_strategy_detector import PitStrategyDetector
from production.incident_detector import IncidentDetector
from production.race_intelligence import RaceIntelligence
from production.opening_director import OpeningDirector
from production.commentary_cleaner import CommentaryCleaner
from production.openai_director import OpenAIDirector

from broadcast.commentator import Commentator
from broadcast.booth import BroadcastBooth
from broadcast.broadcast_queue import BroadcastQueue

from commentary.jeff import Jeff
from voice.voice_director import VoiceDirector


REPLAY_TICK_SECONDS = 0.25
ENABLE_INCIDENT_DETECTION_AFTER_LAP = 2


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

    return False


def main():
    if len(sys.argv) < 2:
        print("Usage:")
        print("python replay_broadcast.py recordings/your_recording_file.jsonl")
        return

    recording_file = sys.argv[1]
    telemetry = ReplayTelemetry(recording_file)

    race_brain = RaceBrain()
    producer = Producer()
    event_queue = EventQueue()
    race_director = RaceDirector()
    broadcast_producer = BroadcastProducer()
    editorial_producer = EditorialProducer()
    pit_strategy_detector = PitStrategyDetector()
    incident_detector = IncidentDetector()
    race_intelligence = RaceIntelligence()
    opening_director = OpeningDirector()
    commentary_cleaner = CommentaryCleaner()
    openai_director = OpenAIDirector()

    commentator = Commentator()
    jeff = Jeff()
    voice_director = VoiceDirector()

    booth = BroadcastBooth()
    broadcast_queue = BroadcastQueue()

    print("=" * 60)
    print("RGC AI Broadcast Studio - Replay Broadcast")
    print("=" * 60)
    print(f"Recording: {recording_file}")
    print(f"Snapshots: {telemetry.snapshot_count()}")
    print(f"OpenAI    : {'ON' if openai_director.is_enabled() else 'OFF'}")
    print("=" * 60)

    if not telemetry.startup():
        print("Replay could not start.")
        return

    while telemetry.is_connected():
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
            race_director.update(
                telemetry=telemetry,
                results=results,
                driver_lookup=driver_lookup,
                scheduler=broadcast_queue,
            )

            if race_director.phase in [
                RacePhase.CAUTION,
                RacePhase.ONE_TO_GREEN,
                RacePhase.CHECKERED,
            ]:
                event_queue.clear()

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
                    event_queue.clear()
                    cleaned_message = commentary_cleaner.clean(incident_event.message)

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
                under_caution=race_director.phase in [
                    RacePhase.CAUTION,
                    RacePhase.ONE_TO_GREEN,
                ],
            )

            for pit_event in pit_events:
                editorial_producer.submit_pit_event(pit_event)
                cleaned_message = commentary_cleaner.clean(pit_event.message)

                broadcast_queue.add(
                    cleaned_message,
                    priority=pit_event.importance,
                    category="pit_strategy",
                    protected=True,
                    speaker="sarah",
                )

            if race_director.phase == RacePhase.GREEN:
                events = race_brain.analyze(results, driver_lookup)

                for event in events:
                    directed_event = race_director.package_event(event)

                    if directed_event:
                        produced_event = broadcast_producer.review_event(directed_event)

                        if produced_event:
                            editorial_producer.submit_story(
                                story_type=getattr(produced_event, "event_type", "race_event"),
                                headline=getattr(produced_event, "message", ""),
                                summary=getattr(produced_event, "story", ""),
                                priority=getattr(produced_event, "importance", 5),
                                source="broadcast_producer",
                                driver_name=getattr(produced_event, "driver_name", ""),
                                car_number=getattr(produced_event, "car_number", ""),
                            )

                            event_queue.add(produced_event)

                event = producer.choose_event(event_queue)

                if event:
                    fallback_commentary = commentary_cleaner.clean(commentator.speak(event))

                    openai_commentary = openai_director.generate_commentary(
                        speaker="lead",
                        assignment=event,
                        race_state=race_state,
                        race_knowledge=race_knowledge,
                        fallback_text=fallback_commentary,
                    )

                    commentary = commentary_cleaner.clean(openai_commentary)

                    broadcast_queue.add(
                        commentary,
                        priority=event.importance,
                        category="race_commentary",
                        protected=False,
                        speaker="lead",
                    )

                    voice_director.mark_lead_spoke()

                    if voice_director.should_add_jeff(event):
                        jeff_commentary = commentary_cleaner.clean(jeff.analyze(event))

                        if jeff_commentary:
                            broadcast_queue.add(
                                jeff_commentary,
                                priority=max(event.importance - 1, 1),
                                category="color_commentary",
                                protected=False,
                                speaker="jeff",
                                delay_seconds=voice_director.jeff_delay(),
                            )

                            voice_director.mark_jeff_spoke()

        next_item = broadcast_queue.next_item()

        if next_item:
            message = commentary_cleaner.clean(next_item.message or "")

            if not should_skip_message(message, current_lap):
                booth.broadcast(message, speaker=next_item.speaker)

        telemetry.next_snapshot()
        time.sleep(REPLAY_TICK_SECONDS)

    print("=" * 60)
    print("Replay broadcast complete.")
    print("=" * 60)


if __name__ == "__main__":
    main()