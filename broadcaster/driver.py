from dataclasses import dataclass


@dataclass
class Driver:
    car_idx: int

    # Identity
    name: str = "Unknown"
    number: str = "?"
    team: str = ""
    car: str = ""
    irating: int = 0
    license: str = ""
    country: str = ""

    # Position tracking
    current_position: int = 0
    previous_position: int = 0
    starting_position: int = 0
    highest_position: int = 999
    lowest_position: int = 0

    # Lap data
    laps_completed: int = 0
    fastest_lap: float = 9999.0
    last_lap: float = 0.0
    average_lap: float = 0.0
    total_lap_time: float = 0.0
    laps_led: int = 0

    # Race activity
    passes_made: int = 0
    passes_lost: int = 0
    incidents: int = 0
    in_pits: bool = False
    retired: bool = False

    # Broadcast intelligence
    story: str = ""
    momentum: str = "Stable"
    last_mentioned_lap: int = 0
    mention_count: int = 0
    story_score: int = 0

    def positions_gained(self):
        if self.starting_position == 0 or self.current_position == 0:
            return 0

        return self.starting_position - self.current_position