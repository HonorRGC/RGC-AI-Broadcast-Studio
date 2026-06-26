import time

from broadcaster.telemetry import IRacingTelemetry
from broadcaster.race_brain import RaceBrain
from broadcaster.producer import Producer
from broadcaster.event_queue import EventQueue
from broadcast.commentator import Commentator
from broadcast.booth import BroadcastBooth


telemetry = IRacingTelemetry()
race_brain = RaceBrain()
producer = Producer()
queue = EventQueue()
commentator = Commentator()
booth = BroadcastBooth()

print("=" * 60)
print("RGC AI Broadcast Studio - v0.5 Broadcast Booth")
print("=" * 60)

while True:
    if telemetry.startup():
        print("\nConnected to iRacing!")

        while telemetry.is_connected():
            results = telemetry.get_results()
            events = race_brain.analyze(results)

            for event in events:
                queue.add(event)

            event = producer.choose_event(queue)

            if event:
                commentary = commentator.speak(event)
                booth.broadcast(commentary)

            time.sleep(2)

    else:
        print("Waiting for iRacing...")
        time.sleep(5)