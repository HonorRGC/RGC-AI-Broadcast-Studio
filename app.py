import time

from broadcaster.telemetry import IRacingTelemetry
from broadcaster.race_brain import RaceBrain
from broadcaster.producer import Producer
from broadcaster.event_queue import EventQueue
from broadcaster.race_status import RaceStatus

from broadcast.commentator import Commentator
from broadcast.booth import BroadcastBooth
from broadcast.broadcast_queue import BroadcastQueue
from broadcast.race_director import RaceDirector


telemetry = IRacingTelemetry()
race_brain = RaceBrain()
producer = Producer()
event_queue = EventQueue()

race_status = RaceStatus()
race_director = RaceDirector()

commentator = Commentator()
booth = BroadcastBooth()
broadcast_queue = BroadcastQueue()

print("=" * 60)
print("      RGC AI Broadcast Studio")
print("      Version 1.2 - Broadcast Scheduler")
print("=" * 60)

while True:
    if telemetry.startup():
        print("\nConnected to iRacing!")

        while telemetry.is_connected():
            session_flags = telemetry.get_session_flags()
            results = telemetry.get_results()

            race_status.update_from_flags(session_flags)
            race_director.update(race_status, results)

            if race_director.phase_changed():
                print(f"\nRace Director Phase -> {race_director.describe_phase()}")

                task = race_director.get_next_task()

                while task:
                    print(f"Director Task: {task.name}")

                    if task.name == "Announce yellow flag":
                        event_queue.clear()
                        broadcast_queue.clear()

                        broadcast_queue.add(
                            "Caution is out! Yellow flag waves over the speedway.",
                            priority=100,
                            category="urgent",
                        )

                    elif task.name == "Announce green flag":
                        broadcast_queue.clear_normal_items()

                        broadcast_queue.add(
                            "Green flag is back in the air! We are racing once again.",
                            priority=95,
                            category="urgent",
                        )

                    task = race_director.get_next_task()

            if race_director.should_hold_pass_calls():
                next_commentary = broadcast_queue.next_commentary()

                if next_commentary:
                    booth.broadcast(next_commentary)

                time.sleep(1)
                continue

            driver_lookup = telemetry.get_driver_lookup()
            events = race_brain.analyze(results, driver_lookup)

            for event in events:
                event_queue.add(event)

            event = producer.choose_event(event_queue)

            if event and race_director.should_allow_pass_calls():
                commentary = commentator.speak(event, event.driver)

                broadcast_queue.add(
                    commentary,
                    priority=event.importance,
                    category="normal",
                )

            next_commentary = broadcast_queue.next_commentary()

            if next_commentary:
                booth.broadcast(next_commentary)

            time.sleep(1)

    else:
        print("Waiting for iRacing...")
        time.sleep(5)