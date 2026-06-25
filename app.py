import time

from broadcaster.telemetry import IRacingTelemetry
from broadcaster.race_brain import RaceBrain


telemetry = IRacingTelemetry()
race_brain = RaceBrain()

print("=" * 60)
print("RGC AI Broadcast Studio - v0.2")
print("=" * 60)

while True:
    if telemetry.startup():
        print("\nConnected to iRacing!")

        while telemetry.is_connected():
            results = telemetry.get_results()
            events = race_brain.analyze(results)

            for event in events:
                print(
                    f"{event.event_type}: {event.message} "
                    f"| Importance {event.importance}/10"
                )

            time.sleep(2)

    else:
        print("Waiting for iRacing...")
        time.sleep(5)