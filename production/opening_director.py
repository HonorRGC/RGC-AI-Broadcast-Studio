from dataclasses import dataclass


@dataclass
class OpeningSegment:
    message: str
    priority: int = 10
    speaker: str = "lead"
    category: str = "opening"
    delay_seconds: float = 0.0
    camera_sequence: tuple[int, ...] = ()
    camera_sequence_steps: tuple[tuple, ...] = ()
    camera_return_home_after_sequence: bool = False


class OpeningDirector:
    LINEUP_GROUP_SIZE = 1

    def __init__(self):
        self.welcome_sent = False
        self.track_info_sent = False
        self.lineup_sent = False
        self.hype_sent = False
        self.lineup_ready_ticks = 0

    def update(self, telemetry, results, driver_lookup, current_lap=0):
        segments = []
        track_info = telemetry.get_track_info()

        if not self.welcome_sent:
            segments.append(self.build_welcome(track_info))
            self.welcome_sent = True

        if not self.track_info_sent:
            segments.append(self.build_track_info(track_info))
            self.track_info_sent = True

        if not self.lineup_sent and self.has_valid_lineup(results):
            self.lineup_ready_ticks += 1
            if self.lineup_ready_ticks < 3:
                return segments
            total_laps_reader = getattr(telemetry, "get_total_laps", None)
            total_laps = total_laps_reader() if total_laps_reader else 0
            segments.extend(
                self.build_field_rundown(
                    results,
                    driver_lookup,
                    track_name=track_info.get("track_name", "the speedway"),
                    total_laps=total_laps,
                )
            )
            self.lineup_sent = True
            if not self.hype_sent:
                segments.append(self.build_hype())
                self.hype_sent = True

        return segments

    def is_complete(self):
        return (
            self.welcome_sent
            and self.track_info_sent
            and self.lineup_sent
            and self.hype_sent
        )

    def has_valid_lineup(self, results):
        valid = [car for car in results or [] if car.get("CarIdx") is not None]
        return len(valid) >= 5

    def build_welcome(self, track_info):
        track_name = track_info.get("track_name", "the speedway")
        city = track_info.get("track_city", "")
        state = self.expand_state(track_info.get("track_state", ""))
        location = f" in {city}, {state}" if city and state else ""

        return OpeningSegment(
            f"Welcome to {track_name}{location}. The cars are on the grid as we get ready for today's race.",
            priority=10,
            category="opening_welcome",
        )

    def build_track_info(self, track_info):
        track_name = track_info.get("track_name", "the speedway")
        track_type = str(track_info.get("track_type", "") or "").lower()
        track_length = self.format_track_length(track_info.get("track_length"))

        parts = []
        if track_length and track_type:
            parts.append(f"{track_name} is a {track_length} {track_type}.")
        elif track_length:
            parts.append(f"{track_name} measures {track_length}.")

        conditions = self.build_weather_summary(track_info)
        if conditions:
            parts.append(conditions)

        parts.append(self.track_note(track_name))

        return OpeningSegment(
            " ".join(parts),
            priority=10,
            category="opening_track_info",
        )

    def build_hype(self):
        return OpeningSegment(
            (
                "I am fired up for this one. This has all the makings of an "
                "awesome race, so let's go racing, boys and girls."
            ),
            priority=8,
            speaker="lead",
            category="opening_hype",
            delay_seconds=1.5,
        )

    def build_weather_summary(self, track_info):
        parts = []
        skies = self.format_skies(track_info.get("skies"))
        air_temp = self.format_temperature(track_info.get("air_temp"))
        track_temp = self.format_temperature(track_info.get("track_temp"))
        humidity = self.format_humidity(track_info.get("humidity"))
        wind = self.format_wind(track_info.get("wind_speed"))
        wetness = self.format_track_wetness(track_info.get("track_wetness"))

        if skies:
            parts.append(f"Skies are {skies}")
        if air_temp:
            parts.append(f"the air temperature is {air_temp}")
        if track_temp:
            parts.append(f"the track temperature is {track_temp}")
        if humidity:
            parts.append(f"humidity is {humidity}")
        if wind:
            parts.append(f"winds are around {wind}")

        if not parts and not wetness:
            return ""

        sentence = ", ".join(parts)
        if sentence:
            sentence = sentence[0].upper() + sentence[1:] + "."
        if wetness:
            sentence = f"{sentence} The racing surface is {wetness}.".strip()
        return sentence

    def build_field_rundown(
        self,
        results,
        driver_lookup,
        track_name="",
        total_laps=0,
    ):
        zero_based = self.results_are_zero_based(results)
        sorted_results = sorted(
            results,
            key=lambda car: self.display_position(car.get("Position", 999), zero_based),
        )
        entries = []
        for car in sorted_results:
            car_idx = car.get("CarIdx")
            if car_idx is None:
                continue

            position = self.display_position(car.get("Position", 999), zero_based)
            if position <= 0 or position >= 999:
                continue

            driver_info = driver_lookup.get(car_idx, {})
            name = driver_info.get("name", f"Car {car_idx}")
            number = driver_info.get("number", "?")
            entries.append(
                {
                    "car_idx": car_idx,
                    "position": position,
                    "number": number,
                    "name": name,
                }
            )

        segments = []
        for start in range(0, len(entries), self.LINEUP_GROUP_SIZE):
            group = entries[start : start + self.LINEUP_GROUP_SIZE]
            group_car_indices = tuple(entry["car_idx"] for entry in group)
            group_messages = [
                self.format_lineup_entry(
                    entry["position"],
                    entry["number"],
                    entry["name"],
                )
                for entry in group
            ]
            group_number = start // self.LINEUP_GROUP_SIZE + 1
            intro = (
                "Here is your starting lineup. "
                if group_number == 1
                else ""
            )
            closing = ""
            is_final_segment = start + self.LINEUP_GROUP_SIZE >= len(entries)
            if is_final_segment and track_name:
                lap_text = f" for {total_laps} laps" if total_laps else ""
                closing = (
                    f" That is your {len(entries)}-car field{lap_text} "
                    f"at {track_name}."
                )
            segments.append(
                OpeningSegment(
                    f"{intro}{' '.join(group_messages)}{closing}",
                    priority=9,
                    speaker="jeff",
                    category=f"opening_field_rundown_{group_number}",
                    camera_sequence=group_car_indices,
                    camera_sequence_steps=tuple(
                        (car_idx, "Rear Chase", 0) for car_idx in group_car_indices
                    ),
                    camera_return_home_after_sequence=is_final_segment,
                )
            )
        return segments

    def format_lineup_entry(self, position, number, name):
        if position == 1:
            return f"On the pole, the {number} of {name}."
        if position == 2:
            return f"Alongside in second, the {number} of {name}."
        return f"Starting {self.ordinal(position)}, the {number} of {name}."

    def results_are_zero_based(self, results):
        return any(self.safe_int(car.get("Position", 999), 999) == 0 for car in results)

    def display_position(self, value, zero_based):
        position = self.safe_int(value, 999)
        return position + 1 if zero_based else position

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
        except (TypeError, ValueError):
            return text
        return text

    def format_temperature(self, value):
        try:
            return f"{round((float(value) * 9 / 5) + 32)} degrees Fahrenheit"
        except (TypeError, ValueError):
            return ""

    def format_skies(self, value):
        if value is None:
            return ""
        labels = {0: "clear", 1: "partly cloudy", 2: "mostly cloudy", 3: "overcast"}
        try:
            return labels.get(int(value), "")
        except (TypeError, ValueError):
            text = str(value).strip().lower()
            return "" if text in ("", "unknown", "none") else text

    def format_humidity(self, value):
        try:
            humidity = float(value)
            if humidity <= 1:
                humidity *= 100
            return f"{round(humidity)} percent"
        except (TypeError, ValueError):
            return ""

    def format_wind(self, value):
        try:
            return f"{round(float(value) * 2.23694)} miles per hour"
        except (TypeError, ValueError):
            return ""

    def format_track_wetness(self, value):
        labels = {
            0: "dry",
            1: "mostly dry",
            2: "very lightly wet",
            3: "lightly wet",
            4: "moderately wet",
            5: "very wet",
            6: "extremely wet",
        }
        try:
            return labels.get(int(value), "")
        except (TypeError, ValueError):
            return ""

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
        return "Track position, tire management, and clean restarts could all play a role today."

    def safe_int(self, value, default=0):
        try:
            return int(value)
        except (TypeError, ValueError):
            return default

    def ordinal(self, number):
        number = self.safe_int(number, number)
        if not isinstance(number, int):
            return str(number)
        if 10 <= number % 100 <= 20:
            suffix = "th"
        else:
            suffix = {1: "st", 2: "nd", 3: "rd"}.get(number % 10, "th")
        return f"{number}{suffix}"
