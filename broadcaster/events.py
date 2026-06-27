from dataclasses import dataclass


@dataclass
class RaceEvent:
    event_type: str
    driver_name: str
    old_position: int
    new_position: int
    importance: int
    message: str
    driver: object = None