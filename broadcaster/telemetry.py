import irsdk


class IRacingTelemetry:
    def __init__(self):
        self.ir = irsdk.IRSDK()

    def startup(self):
        return self.ir.startup()

    def is_connected(self):
        return self.ir.is_initialized and self.ir.is_connected

    def get_session_info(self):
        return self.ir["SessionInfo"]

    def get_driver_info(self):
        return self.ir["DriverInfo"]

    def get_session_flags(self):
        try:
            return self.ir["SessionFlags"] or 0
        except Exception:
            return 0

    def get_lap(self):
        try:
            return int(self.ir["Lap"] or 0)
        except Exception:
            return 0

    def get_total_laps(self):
        session_info = self.get_session_info()

        if not session_info:
            return 0

        current_session = session_info.get("CurrentSessionNum", 0)
        sessions = session_info.get("Sessions", [])

        if current_session >= len(sessions):
            return 0

        session = sessions[current_session]
        session_laps = session.get("SessionLaps", 0)

        try:
            return int(session_laps)
        except Exception:
            return 0

    def get_results(self):
        session_info = self.get_session_info()

        if not session_info:
            return []

        current_session = session_info.get("CurrentSessionNum", 0)
        sessions = session_info.get("Sessions", [])

        if current_session >= len(sessions):
            return []

        session = sessions[current_session]
        return session.get("ResultsPositions") or []

    def get_driver_lookup(self):
        driver_info = self.get_driver_info()

        if not driver_info:
            return {}

        drivers = driver_info.get("Drivers", [])
        lookup = {}

        for driver in drivers:
            car_idx = driver.get("CarIdx")
            name = driver.get("UserName", f"CarIdx {car_idx}")
            number = driver.get("CarNumber", "?")

            lookup[car_idx] = {
                "name": name,
                "number": number,
            }

        return lookup

    def get_track_info(self):
        session_info = self.get_session_info()

        track_name = "the speedway"
        track_city = ""
        track_country = ""
        weather = "unknown"
        skies = "unknown"

        if session_info:
            weekend_info = session_info.get("WeekendInfo", {})

            track_name = weekend_info.get("TrackName", track_name)
            track_city = weekend_info.get("TrackCity", "")
            track_country = weekend_info.get("TrackCountry", "")
            weather = weekend_info.get("WeatherType", weather)
            skies = weekend_info.get("Skies", skies)

        return {
            "track_name": track_name,
            "track_city": track_city,
            "track_country": track_country,
            "weather": weather,
            "skies": skies,
            "air_temp": self.safe_read("AirTemp"),
            "track_temp": self.safe_read("TrackTempCrew"),
            "track_wetness": self.safe_read("TrackWetness"),
            "wind_speed": self.safe_read("WindVel"),
        }

    def safe_read(self, key):
        try:
            value = self.ir[key]

            if value is None:
                return None

            return value
        except Exception:
            return None