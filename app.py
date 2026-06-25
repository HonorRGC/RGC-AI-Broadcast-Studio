import time

from broadcaster.telemetry import IRacingTelemetry
from broadcaster.race_brain import RaceBrain
from broadcaster.producer import Producer
from broadcaster.event_queue import EventQueue
from commentary.generator import CommentaryGenerator


telemetry = IRacingTelemetry()
race_brain = RaceBrain()
producer = Producer()
queue = EventQueue()
commentary = CommentaryGenerator()

print("=" * 60)
print("RGC AI Broadcast Studio - v0.4")
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
                line = commentary.generate(event)

                print()
                print("🎙 AI COMMENTARY")
                print("-" * 60)
                print(line)
                print("-" * 60)

            time.sleep(2)

    else:
        print("Waiting for iRacing...")
        time.sleep(5)