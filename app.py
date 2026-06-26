import time

from broadcaster.telemetry import IRacingTelemetry
from broadcaster.race_brain import RaceBrain
from broadcaster.producer import Producer
from broadcaster.event_queue import EventQueue
from broadcast.commentator import Commentator
from broadcast.booth import BroadcastBooth
from broadcast.broadcast_queue import BroadcastQueue


telemetry = IRacingTelemetry()
race_brain = RaceBrain()
producer = Producer()
event_queue = EventQueue()
commentator = Commentator()
booth = BroadcastBooth()
broadcast_queue = BroadcastQueue()

print("=" * 60)
print("RGC AI Broadcast Studio - v0.8 Broadcast Queue")
print("=" * 60)

while True:
    if telemetry.startup():
        print("\nConnected to iRacing!")

        while telemetry.is_connected():
            results = telemetry.get_results()
            driver_lookup = telemetry.get_driver_lookup()

            events = race_brain.analyze(results, driver_lookup)

            for event in events:
                event_queue.add(event)

            event = producer.choose_event(event_queue)

            if event:
                commentary = commentator.speak(event)
                broadcast_queue.add(commentary)

            next_commentary = broadcast_queue.next_commentary()

            if next_commentary:
                booth.broadcast(next_commentary)

            time.sleep(1)

    else:
        print("Waiting for iRacing...")
        time.sleep(5)