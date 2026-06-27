import time

from broadcaster.telemetry import IRacingTelemetry
from broadcaster.race_brain import RaceBrain
from broadcaster.producer import Producer
from broadcaster.event_queue import EventQueue
from broadcaster.race_director import RaceDirector

from production.broadcast_producer import BroadcastProducer

from broadcast.commentator import Commentator
from broadcast.booth import BroadcastBooth
from broadcast.broadcast_queue import BroadcastQueue


telemetry = IRacingTelemetry()
race_brain = RaceBrain()
producer = Producer()
event_queue = EventQueue()
race_director = RaceDirector()
broadcast_producer = BroadcastProducer()

commentator = Commentator()
booth = BroadcastBooth()
broadcast_queue = BroadcastQueue()


print("=" * 60)
print("RGC AI Broadcast Studio - v0.12 Race Finish Control")
print("=" * 60)


while True:
    if telemetry.startup():
        print("\nConnected to iRacing!")

        while telemetry.is_connected():
            results = telemetry.get_results()
            driver_lookup = telemetry.get_driver_lookup()

            race_director.update(
                telemetry=telemetry,
                results=results,
                driver_lookup=driver_lookup,
                scheduler=broadcast_queue,
            )

            if not race_director.is_race_over():
                events = race_brain.analyze(results, driver_lookup)

                for event in events:
                    directed_event = race_director.package_event(event)

                    if directed_event:
                        produced_event = broadcast_producer.review_event(directed_event)

                        if produced_event:
                            event_queue.add(produced_event)

                event = producer.choose_event(event_queue)

                if event:
                    commentary = commentator.speak(event)

                    broadcast_queue.add(
                        commentary,
                        priority=event.importance,
                        category="race_commentary",
                        protected=False,
                    )

            next_commentary = broadcast_queue.next_commentary()

            if next_commentary:
                booth.broadcast(next_commentary)

            time.sleep(1)

    else:
        print("Waiting for iRacing...")
        time.sleep(5)