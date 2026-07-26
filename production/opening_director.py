from dataclasses import dataclass

from production.track_style import (
    is_long_straight_draft_assist_track,
    is_road_course,
    is_true_pack_drafting_track,
)


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
        self.race_outlook_sent = False
        self.pit_report_sent = False
        self.lineup_sent = False
        self.hype_sent = False
        self.lineup_ready_ticks = 0

    def update(self, telemetry, results, driver_lookup, current_lap=0):
        segments = []
        track_info = telemetry.get_track_info()

        if not self.welcome_sent:
            segments.append(self.build_welcome(track_info))
            self.welcome_sent = True
            self.track_info_sent = True

        if not self.race_outlook_sent:
            segments.append(self.build_race_outlook(track_info))
            self.race_outlook_sent = True

        if not self.pit_report_sent:
            segments.append(self.build_pit_report(track_info))
            self.pit_report_sent = True

        if not self.lineup_sent and self.has_valid_lineup(results):
            self.lineup_ready_ticks += 1
            if self.lineup_ready_ticks < 5:
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
            and self.race_outlook_sent
            and self.pit_report_sent
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
        details = []
        story = self.track_opening_story(track_info)
        if story:
            details.append(story)
        track_description = self.track_description(track_info)
        if track_description:
            details.append(track_description)
        conditions = self.build_weather_summary(track_info)
        if conditions:
            details.append(conditions)
        detail_text = f" {' '.join(details)}" if details else ""

        return OpeningSegment(
            f"Welcome to {track_name}{location}.{detail_text}",
            priority=10,
            category="opening_welcome",
        )

    def track_opening_story(self, track_info):
        track_name = track_info.get("track_name", "the speedway")
        name = str(track_name or "").lower()
        if "daytona" in name:
            return (
                "This is one of racing's landmark venues, where the draft can "
                "turn patience into a winning move in a heartbeat."
            )
        if "talladega" in name:
            return (
                "This place has built its reputation on huge packs, big runs, "
                "and decisions that have to be made at nearly full throttle."
            )
        if "michigan" in name:
            return (
                "Michigan gives drivers room to search for clean air, but the "
                "long straightaways punish anyone who loses momentum."
            )
        if "homestead" in name:
            return (
                "Homestead is a driver's track, with multiple lanes and a wall "
                "that rewards commitment but punishes one small mistake."
            )
        if "martinsville" in name:
            return (
                "Martinsville is short-track pressure from the first lap, where "
                "brake discipline and patience can matter more than raw speed."
            )
        if "bristol" in name:
            return (
                "Bristol turns every lap into traffic management, with the walls "
                "close and patience in very short supply."
            )
        if "nashville" in name:
            return (
                "Nashville has become a momentum race, where clean exits and "
                "traffic decisions can build or break a run."
            )
        length = self.track_length_miles(track_info.get("track_length"))
        track_type = str(track_info.get("track_type", "") or "").lower()
        if length and length <= 1.0 and "road" not in track_type:
            return (
                "Short-track nights are built on rhythm, patience, and surviving "
                "the restart stack-ups."
            )
        if is_road_course(track_info):
            return (
                "This is a rhythm race, where braking zones, exits, and avoiding "
                "the big mistake can decide the night."
            )
        return (
            "Tonight is about building a complete race, balancing track position, "
            "tire life, and the moments when it is time to attack."
        )

    def track_description(self, track_info):
        track_name = track_info.get("track_name", "the speedway")
        track_type = str(track_info.get("track_type", "") or "").lower()
        track_length = self.format_track_length(track_info.get("track_length"))

        if track_length and track_type:
            return f"{track_name} is a {track_length} {track_type}."
        if track_length:
            return f"{track_name} measures {track_length}."
        return ""

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

    def build_race_outlook(self, track_info):
        track_name = track_info.get("track_name", "this place")
        track_type = str(track_info.get("track_type", "") or "").lower()
        length_miles = self.track_length_miles(track_info.get("track_length"))
        if length_miles and length_miles <= 1.0:
            message = (
                "The biggest thing tonight is patience. Restarts stack up quickly, "
                "and the drivers who keep the nose clean should have options late."
            )
        elif self.is_drafting_track(track_info):
            message = (
                "The draft should shape this race. Runs build fast, and timing "
                "the lane changes may matter more than raw speed."
            )
        elif is_long_straight_draft_assist_track(track_info):
            message = (
                "The long straightaways can help drivers build a run, but this "
                "is still about braking, corner exit, and keeping the car "
                "balanced through the slower corners."
            )
        elif is_road_course(track_info):
            message = (
                "Rhythm and braking zones decide this one. Clean exits and "
                "mistake-free laps should pay off over a full run."
            )
        else:
            message = (
                "The story to watch is who can protect track position while "
                "saving enough tire to attack when the run gets long."
            )
        return OpeningSegment(
            message,
            priority=9,
            speaker="jeff",
            category="opening_race_outlook",
        )

    def build_pit_report(self, track_info):
        track_name = track_info.get("track_name", "this place")
        length_miles = self.track_length_miles(track_info.get("track_length"))
        if length_miles and length_miles <= 1.0:
            message = (
                "Down here on pit road, track position will be huge. A clean stop "
                "can keep a driver out of the hornet's nest."
            )
        elif self.is_drafting_track(track_info):
            message = (
                "Pit road timing could be a big swing tonight. If fuel strategy "
                "comes into play, the cleanest group stop can win track position."
            )
        elif is_road_course(track_info):
            message = (
                "Down here on pit road, road-course strategy is all about the "
                "window. A clean in-lap, a clean out-lap, and avoiding pit-road "
                "speeding can make the undercut or overcut work."
            )
        else:
            message = (
                "Pit road should be quiet early, but once tires start to matter, "
                "the timing of that first stop can change the race."
            )
        return OpeningSegment(
            message,
            priority=8,
            speaker="sarah",
            category="opening_pit_report",
        )

    def build_hype(self):
        return OpeningSegment(
            (
                "The field is set, the pace car is ready, and the next flag "
                "will start this one. Let's settle in and go racing."
            ),
            priority=7,
            speaker="lead",
            category="opening_hype",
            delay_seconds=8.0,
        )

    def build_weather_summary(self, track_info):
        parts = []
        skies = self.format_skies(track_info.get("skies"))
        air_temp = self.format_temperature(track_info.get("air_temp"))
        track_temp = self.format_temperature(track_info.get("track_temp"))
        humidity = self.format_humidity(track_info.get("humidity"))
        wind = self.format_wind(track_info.get("wind_speed"))
        wetness = self.format_track_wetness(track_info.get("track_wetness"))
        rain_chance = self.format_rain_chance(track_info)
        grip_note = self.grip_note(track_info)

        if skies:
            parts.append(f"Skies are {skies}")
        if air_temp:
            parts.append(f"air temperature is {air_temp}")
        if track_temp:
            parts.append(f"track temperature is {track_temp}")
        if rain_chance:
            parts.append(f"rain chance is {rain_chance}")
        if humidity:
            parts.append(f"humidity is {humidity}")
        if wind:
            parts.append(f"wind is around {wind}")

        if not parts and not wetness:
            return ""

        sentence = ", ".join(parts)
        if sentence:
            sentence = sentence[0].upper() + sentence[1:] + "."
        if wetness:
            sentence = f"{sentence} The racing surface is {wetness}.".strip()
        if grip_note:
            sentence = f"{sentence} {grip_note}".strip()
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
        miles = self.track_length_miles(value)
        if miles is None:
            return ""
        return self.broadcast_track_length(miles)

    def track_length_miles(self, value):
        if not value:
            return None
        text = str(value).strip()
        try:
            number = float(text.split()[0])
            if "km" in text.lower():
                return number * 0.621371
            if "mi" in text.lower():
                return number
        except (TypeError, ValueError):
            return None
        return number

    def broadcast_track_length(self, miles):
        common_lengths = (
            (0.5, "half-mile"),
            (0.75, "three-quarter-mile"),
            (0.875, "seven-eighths-mile"),
            (1.0, "one-mile"),
            (1.25, "mile-and-a-quarter"),
            (1.33, "mile-and-a-third"),
            (1.5, "mile-and-a-half"),
            (2.0, "two-mile"),
            (2.5, "two-and-a-half-mile"),
        )
        for target, label in common_lengths:
            if abs(float(miles) - target) <= 0.06:
                return label
        if miles >= 2.0:
            return f"{miles:.1f}-mile"
        return f"{miles:.2f}-mile"

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
            text = self.broadcast_weather_text(value)
            return "" if text in ("", "unknown", "none") else text

    def broadcast_weather_text(self, value):
        text = str(value or "").strip().lower()
        replacements = (
            ("dynamic sky", ""),
            ("dynamic skies", ""),
            ("dynamic weather", ""),
            ("dynamic", ""),
        )
        for old, new in replacements:
            text = text.replace(old, new)
        text = " ".join(text.replace("_", " ").replace("-", " ").split())
        if text in ("partly cloudy skies", "partly clouds"):
            return "partly cloudy"
        if text in ("mostly cloudy skies",):
            return "mostly cloudy"
        return text

    def is_drafting_track(self, track_info):
        return is_true_pack_drafting_track(track_info)

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

    def format_rain_chance(self, track_info):
        for key in (
            "rain_chance",
            "chance_of_rain",
            "precipitation_chance",
            "forecast_rain_chance",
        ):
            if key not in track_info:
                continue
            try:
                value = float(track_info.get(key))
                if value <= 1:
                    value *= 100
                return f"{round(value)} percent"
            except (TypeError, ValueError):
                text = str(track_info.get(key, "") or "").strip()
                if text:
                    return text
        wetness = self.safe_int(track_info.get("track_wetness"), 0)
        weather = str(track_info.get("weather", "") or "").lower()
        skies = self.format_skies(track_info.get("skies")).lower()
        if wetness == 0 and "rain" not in weather and "overcast" not in skies:
            return "0 percent"
        return ""

    def grip_note(self, track_info):
        track_temp_f = self.temperature_to_fahrenheit(track_info.get("track_temp"))
        air_temp_f = self.temperature_to_fahrenheit(track_info.get("air_temp"))
        skies = self.format_skies(track_info.get("skies")).lower()
        session_time = str(
            track_info.get("time_of_day")
            or track_info.get("session_time_of_day")
            or track_info.get("track_time")
            or ""
        ).lower()
        is_night = any(word in session_time for word in ("night", "pm", "evening"))
        is_day = any(word in session_time for word in ("day", "afternoon", "am"))

        if track_temp_f and track_temp_f <= 80:
            return (
                "With that cooler racing surface, the cars should have a little "
                "more grip, especially early in a run."
            )
        if is_night and track_temp_f and track_temp_f <= 95:
            return (
                "Because this is a cooler night race, grip should come in quicker "
                "and drivers may be able to attack harder on restarts."
            )
        if track_temp_f and track_temp_f >= 105:
            return (
                "That hotter track should make the tires give up faster, so the "
                "drivers who manage throttle and corner entry may have the advantage later in a run."
            )
        if is_day and air_temp_f and air_temp_f >= 85:
            return (
                "With daytime heat in the air, expect the track to get slicker "
                "as the run goes on."
            )
        if "cloud" in skies or "overcast" in skies:
            return (
                "Cloud cover can help keep the surface more consistent, which "
                "usually gives drivers a more predictable balance."
            )
        return ""

    def temperature_to_fahrenheit(self, value):
        try:
            return (float(value) * 9 / 5) + 32
        except (TypeError, ValueError):
            return 0.0

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
