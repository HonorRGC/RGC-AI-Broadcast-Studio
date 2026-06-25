import random


class CommentaryGenerator:
    def generate(self, event):
        if event.event_type == "PASS":
            templates = [
                f"{event.driver_name} is on the move, climbing into P{event.new_position}. {event.message}",
                f"Big move there! {event.driver_name} takes over P{event.new_position}. {event.message}",
                f"{event.driver_name} continues forward and now runs P{event.new_position}. {event.message}",
                f"That pass puts {event.driver_name} into P{event.new_position}. {event.message}",
            ]

            return random.choice(templates)

        return event.message