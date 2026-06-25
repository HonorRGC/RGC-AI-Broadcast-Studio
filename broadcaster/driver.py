from dataclasses import dataclass


@dataclass
class Driver:
    car_idx: int

    name: str = "Unknown"
    number: str = "?"

    current_position: int = 0
    previous_position: int = 0

    starting_position: int = 0

    highest_position: int = 999
    lowest_position: int = 0

    laps_completed: int = 0

    fastest_lap: float = 9999.0
    last_lap: float = 0.0

    passes_made: int = 0
    passes_lost: int = 0

    incidents: int = 0

    in_pits: bool = False

    retired: bool = False

    story: str = ""