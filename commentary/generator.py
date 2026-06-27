import random

from helpers.position_formatter import PositionFormatter


class CommentaryGenerator:
    def generate(self, event):
        if event.event_type == "PASS":
            old_position = PositionFormatter.ordinal(event.old_position)
            new_position = PositionFormatter.ordinal(event.new_position)

            templates = [
                (
                    f"{event.driver_name} is going forward, climbing from "
                    f"{old_position} to {new_position} with a clean position gain."
                ),
                (
                    f"Put {event.driver_name} up into {new_position}. "
                    f"That move keeps the momentum building."
                ),
                (
                    f"{event.driver_name} picks up another spot and moves into "
                    f"{new_position}."
                ),
                (
                    f"{event.driver_name} continues the charge, now running "
                    f"{new_position}."
                ),
            ]

            if event.importance >= 10:
                templates.extend([
                    (
                        f"New leader! {event.driver_name} takes over the top spot. "
                        f"That is a major moment in this race."
                    ),
                    (
                        f"{event.driver_name} goes to the race lead. "
                        f"That move changes everything at the front."
                    ),
                ])

            elif event.importance >= 8:
                templates.extend([
                    (
                        f"Big move inside the top five. "
                        f"{event.driver_name} advances to {new_position}."
                    ),
                    (
                        f"{event.driver_name} breaks into the sharp end of the field, "
                        f"now running {new_position}."
                    ),
                ])

            return random.choice(templates)

        return event.message