import time

from broadcaster.telemetry import IRacingTelemetry
from broadcaster.race_brain import RaceBrain
from broadcaster.producer import Producer
from broadcaster.event_queue import EventQueue
from broadcaster.race_director import RaceDirector, RacePhase

from production.broadcast_producer import BroadcastProducer
from production.editorial_producer import EditorialProducer
from production.pit_strategy_detector import PitStrategyDetector
from production.incident_detector import IncidentDetector

from broadcast.commentator import Commentator
from broadcast.booth import BroadcastBooth
from broadcast.broadcast_queue import BroadcastQueue

from commentary.jeff import Jeff
from voice.voice_director import VoiceDirector


telemetry = IRacingTelemetry()
race_brain = RaceBrain()
producer = Producer()
event_queue = EventQueue()
race_director = RaceDirector()
broadcast_producer = BroadcastProducer()
editorial_producer = EditorialProducer()
pit_strategy_detector = PitStrategyDetector()
incident_detector = IncidentDetector()

commentator = Commentator()
jeff = Jeff()
voice_director = VoiceDirector()

booth = BroadcastBooth()
broadcast_queue = BroadcastQueue()


print("=" * 60)
print("RGC AI Broadcast Studio - v0.17 Trouble Detector")
print("=" * 60)


while True:
    if telemetry.startup():
        print("\nConnected to iRacing!")

        while telemetry.is_connected():
            results = telemetry.get_results()
            driver_lookup = telemetry.get_driver_lookup()
            current_lap = telemetry.get_lap()
            pit_road_status = telemetry.get_car_idx_on_pit_road()

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

                broadcast_queue.add(
                    incident_event.message,
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

                broadcast_queue.add(
                    pit_event.message,
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
                    commentary = commentator.speak(event)

                    broadcast_queue.add(
                        commentary,
                        priority=event.importance,
                        category="race_commentary",
                        protected=False,
                        speaker="lead",
                    )

                    voice_director.mark_lead_spoke()

                    if voice_director.should_add_jeff(event):
                        jeff_commentary = jeff.analyze(event)

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
                booth.broadcast(next_item.message, speaker=next_item.speaker)

            time.sleep(1)

    else:
        print("Waiting for iRacing...")
        time.sleep(5)