import time

from broadcaster.telemetry import IRacingTelemetry
from broadcaster.race_brain import RaceBrain
from broadcaster.producer import Producer
from broadcaster.event_queue import EventQueue
from broadcaster.race_director import RaceDirector, RacePhase

from production.broadcast_producer import BroadcastProducer

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

commentator = Commentator()
jeff = Jeff()
voice_director = VoiceDirector()

booth = BroadcastBooth()
broadcast_queue = BroadcastQueue()


print("=" * 60)
print("RGC AI Broadcast Studio - v0.14 Voice Director")
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

            if race_director.phase in [
                RacePhase.CAUTION,
                RacePhase.ONE_TO_GREEN,
                RacePhase.CHECKERED,
            ]:
                event_queue.clear()

            if race_director.phase == RacePhase.GREEN:
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