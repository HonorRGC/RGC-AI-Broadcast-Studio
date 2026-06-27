from dataclasses import dataclass


@dataclass
class RaceEvent:
    event_type: str
    driver_name: str
    old_position: int
    new_position: int
    importance: int
    message: str

    car_number: str = "?"
    starting_position: int = 0
    positions_gained_from_start: int = 0
    passes_made: int = 0
    passes_lost: int = 0
    story: str = ""
    lap: int = 0