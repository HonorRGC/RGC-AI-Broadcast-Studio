from dataclasses import dataclass


@dataclass
class OpeningSegment:
    message: str
    priority: int = 10
    speaker: str = "lead"
    category: str = "opening"


class OpeningDirector:
    def __init__(self):
        self.completed = False
        self.sent = False

    def update(self, telemetry, results, driver_lookup, current_lap=0):
        if self.completed or self.sent:
            return []

        track_info = telemetry.get_track_info()

        segments = [
            self.build_welcome(track_info),
            self.build_track_info(track_info),
        ]

        if self.has_valid_lineup(results):
            segments.append(self.build_field_rundown(results, driver_lookup))

        self.sent = True
        self.completed = True
        return segments

    def is_complete(self):
        return self.completed

    def has_valid_lineup(self, results):
        if not results:
            return False

        valid = 0
        for car in results:
            if self.safe_int(car.get("Position", 0)) > 0 and car.get("CarIdx") is not None:
                valid += 1

        return valid >= 5

    def build_welcome(self, track_info):
        track_name = track_info.get("track_name", "the speedway")
        city = track_info.get("track_city", "")
        state = self.expand_state(track_info.get("track_state", ""))
        location = f" in {city}, {state}" if city and state else ""

        return OpeningSegment(
            f"Welcome to {track_name}{location}. The field is getting ready for tonight's race.",
            priority=10,
            speaker="lead",
            category="opening_welcome",
        )

    def build_track_info(self, track_info):
        track_name = track_info.get("track_name", "the speedway")
        track_type = track_info.get("track_type", "")
        track_length = self.format_track_length(track_info.get("track_length"))
        air_temp = self.format_temperature(track_info.get("air_temp"))
        track_temp = self.format_temperature(track_info.get("track_temp"))

        parts = []

        if track_length and track_type:
            parts.append(f"{track_name} is a {track_length} {track_type}.")
        elif track_length:
            parts.append(f"{track_name} measures {track_length}.")

        if air_temp:
            parts.append(f"Air temperature is {air_temp}.")

        if track_temp:
            parts.append(f"Track temperature is {track_temp}.")

        parts.append(self.track_note(track_name))

        return OpeningSegment(
            " ".join(parts),
            priority=10,
            speaker="lead",
            category="opening_track_info",
        )

    def build_field_rundown(self, results, driver_lookup, max_cars=10):
        sorted_results = sorted(
            results,
            key=lambda car: self.safe_int(car.get("Position", 999)),
        )

        lines = ["Here is your starting lineup through the top ten."]

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
            " ".join(lines),
            priority=10,
            speaker="lead",
            category="opening_field_rundown",
        )

    def expand_state(self, state):
        states = {
            "TN": "Tennessee",
            "FL": "Florida",
            "CA": "California",
            "NC": "North Carolina",
            "SC": "South Carolina",
            "GA": "Georgia",
            "VA": "Virginia",
            "TX": "Texas",
            "AZ": "Arizona",
            "NV": "Nevada",
            "IL": "Illinois",
            "IN": "Indiana",
            "OH": "Ohio",
            "PA": "Pennsylvania",
            "MI": "Michigan",
            "WI": "Wisconsin",
            "NY": "New York",
            "ME": "Maine",
        }

        return states.get(str(state).upper(), state)

    def format_track_length(self, value):
        if not value:
            return ""

        text = str(value).strip()

        try:
            number = float(text.split()[0])

            if "km" in text.lower():
                return f"{number * 0.621371:.2f}-mile"

            if "mi" in text.lower():
                return f"{number:.2f}-mile"
        except Exception:
            return text

        return text

    def format_temperature(self, value):
        try:
            return f"{round((float(value) * 9 / 5) + 32)} degrees Fahrenheit"
        except Exception:
            return None

    def track_note(self, track_name):
        name = str(track_name).lower()

        if "nashville" in name:
            return "Nashville rewards momentum and clean exits, especially when drivers are packed together in traffic."

        if "homestead" in name:
            return "Homestead rewards momentum, tire management, and drivers who can work multiple lanes."

        if "daytona" in name:
            return "Daytona is all about drafting help, timing, and deciding when to make the move."

        if "talladega" in name:
            return "Talladega is one of the biggest drafting tracks in the world, where patience matters until it is time to go."

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
