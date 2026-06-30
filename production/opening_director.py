from dataclasses import dataclass
from enum import Enum


class OpeningStage(Enum):
    NOT_STARTED = "NOT_STARTED"
    WELCOME = "WELCOME"
    TRACK_INFO = "TRACK_INFO"
    FIELD_RUNDOWN = "FIELD_RUNDOWN"
    READY_FOR_GREEN = "READY_FOR_GREEN"
    COMPLETE = "COMPLETE"


@dataclass
class OpeningSegment:
    message: str
    priority: int = 10
    speaker: str = "lead"
    category: str = "opening"


class OpeningDirector:
    def __init__(self):
        self.stage = OpeningStage.NOT_STARTED
        self.completed = False

        self.welcome_done = False
        self.track_info_done = False
        self.field_rundown_done = False
        self.ready_for_green_done = False

    def update(self, telemetry, results, driver_lookup, current_lap=0):
        segments = []

        if self.completed:
            return segments

        track_info = telemetry.get_track_info()

        if not self.welcome_done:
            segments.append(self.build_welcome(track_info))
            self.welcome_done = True
            self.stage = OpeningStage.WELCOME
            return segments

        if not self.track_info_done:
            segments.append(self.build_track_info(track_info))
            self.track_info_done = True
            self.stage = OpeningStage.TRACK_INFO
            return segments

        if not self.field_rundown_done:
            if self.has_valid_lineup(results):
                segments.append(self.build_field_rundown(results, driver_lookup))
                self.field_rundown_done = True
                self.stage = OpeningStage.FIELD_RUNDOWN
                return segments

            return segments

        if not self.ready_for_green_done:
            segments.append(
                OpeningSegment(
                    message="The field is getting set. We are just about ready to go green.",
                    priority=10,
                    speaker="lead",
                    category="opening_ready",
                )
            )
            self.ready_for_green_done = True
            self.stage = OpeningStage.READY_FOR_GREEN
            return segments

        self.completed = True
        self.stage = OpeningStage.COMPLETE
        return segments

    def has_valid_lineup(self, results):
        if not results:
            return False

        valid = 0

        for car in results:
            position = self.safe_int(car.get("Position", 0))
            car_idx = car.get("CarIdx")

            if car_idx is not None and position > 0:
                valid += 1

        return valid >= 5

    def is_complete(self):
        return self.completed

    def should_hold_race_chatter(self):
        return not self.completed

    def build_welcome(self, track_info):
        track_name = track_info.get("track_name", "the speedway")
        city = track_info.get("track_city", "")
        state = track_info.get("track_state", "")
        country = track_info.get("track_country", "")

        location = self.format_location(city, state, country)

        message = (
            f"Welcome to {track_name}{location}. "
            f"The field is getting ready for tonight's race."
        )

        return OpeningSegment(message=message, priority=10, speaker="lead", category="opening_welcome")

    def build_track_info(self, track_info):
        track_name = track_info.get("track_name", "the speedway")
        track_type = track_info.get("track_type", "")
        track_length = self.format_track_length(track_info.get("track_length"))
        weather = track_info.get("weather", "unknown")
        skies = track_info.get("skies", "unknown")
        air_temp = self.format_temperature(track_info.get("air_temp"))
        track_temp = self.format_temperature(track_info.get("track_temp"))

        parts = []

        if track_length and track_type:
            parts.append(f"{track_name} is a {track_length} {track_type}.")
        elif track_length:
            parts.append(f"{track_name} measures {track_length}.")
        else:
            parts.append(f"{track_name} should give these drivers plenty to think about tonight.")

        if air_temp:
            parts.append(f"Air temperature is {air_temp}.")

        if track_temp:
            parts.append(f"Track temperature is {track_temp}.")

        if weather != "unknown" or skies != "unknown":
            parts.append(f"Weather is {weather}, with {skies} skies.")

        parts.append(self.track_note(track_name))

        return OpeningSegment(
            message=" ".join(parts),
            priority=10,
            speaker="lead",
            category="opening_track_info",
        )

    def build_field_rundown(self, results, driver_lookup, max_cars=20):
        sorted_results = sorted(
            results,
            key=lambda car: self.safe_int(car.get("Position", 999)),
        )

        lines = ["Here is your starting lineup through the top twenty."]

        for car in sorted_results[:max_cars]:
            car_idx = car.get("CarIdx")
            position = self.safe_int(car.get("Position", 0))

            if position <= 0:
                continue

            driver_info = driver_lookup.get(car_idx, {})
            name = driver_info.get("name", f"Car {car_idx}")
            number = driver_info.get("number", "?")

            lines.append(f"{self.ordinal(position)}, the {number} of {name}.")

        return OpeningSegment(
            message=" ".join(lines),
            priority=10,
            speaker="lead",
            category="opening_field_rundown",
        )

    def format_location(self, city, state, country):
        if city and state:
            return f" in {city}, {state}"
        if city and country:
            return f" in {city}, {country}"
        if city:
            return f" in {city}"
        return ""

    def format_track_length(self, value):
        if not value:
            return ""

        text = str(value).strip()

        try:
            number = float(text.split()[0])

            if "km" in text.lower():
                miles = number * 0.621371
                return f"{miles:.2f}-mile"

            if "mi" in text.lower():
                return f"{number:.2f}-mile"

        except Exception:
            return text

        return text

    def format_temperature(self, value):
        if value is None:
            return None

        try:
            fahrenheit = (float(value) * 9 / 5) + 32
            return f"{round(fahrenheit)} degrees Fahrenheit"
        except Exception:
            return None

    def track_note(self, track_name):
        name = str(track_name).lower()

        if "daytona" in name:
            return "Daytona is all about drafting help, timing, and deciding when to make the move."

        if "talladega" in name:
            return "Talladega is one of the biggest drafting tracks in the world, where patience matters until it is time to go."

        if "bristol" in name:
            return "Bristol is short-track racing at high speed, where traffic and rhythm can define the night."

        if "martinsville" in name:
            return "Martinsville rewards braking discipline, clean corner exit, and patience in traffic."

        if "charlotte" in name:
            return "Charlotte is a classic mile-and-a-half where clean air, tire falloff, and momentum can shape the race."

        if "nashville" in name:
            return "Nashville rewards momentum and clean exits, especially when drivers are packed together in traffic."

        return "Track position, tire management, and clean restarts could all play a role tonight."

    def safe_int(self, value):
        try:
            return int(value)
        except Exception:
            return 0

    def ordinal(self, number):
        try:
            number = int(number)
        except Exception:
            return str(number)

        if 10 <= number % 100 <= 20:
            suffix = "th"
        else:
            suffix = {1: "st", 2: "nd", 3: "rd"}.get(number % 10, "th")

        return f"{number}{suffix}"