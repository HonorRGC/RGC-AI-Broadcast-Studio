import re

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

    def get_weekend_info(self):
        try:
            return self.ir["WeekendInfo"] or {}
        except Exception:
            return {}

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

        try:
            return int(session.get("SessionLaps", 0))
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

        return sessions[current_session].get("ResultsPositions") or []

    def get_driver_lookup(self):
        driver_info = self.get_driver_info()
        if not driver_info:
            return {}

        lookup = {}

        for driver in driver_info.get("Drivers", []):
            car_idx = driver.get("CarIdx")
            raw_name = driver.get("UserName", f"CarIdx {car_idx}")

            lookup[car_idx] = {
                "name": self.clean_driver_name(raw_name),
                "raw_name": raw_name,
                "number": driver.get("CarNumber", "?"),
            }

        return lookup

    def clean_driver_name(self, name):
        if not name:
            return name

        cleaned = str(name).strip()

        # Removes iRacing-style duplicate/account suffixes like:
        # Jason Johnson5 -> Jason Johnson
        # Tim Lee12 -> Tim Lee
        cleaned = re.sub(r"(?<=[A-Za-z])\d+$", "", cleaned).strip()

        return cleaned

    def get_car_idx_on_pit_road(self):
        try:
            data = self.ir["CarIdxOnPitRoad"]
            if data is None:
                return []
            return list(data)
        except Exception:
            return []

    def get_track_info(self):
        weekend_info = self.get_weekend_info()

        track_name = (
            weekend_info.get("TrackDisplayName")
            or weekend_info.get("TrackDisplayShortName")
            or weekend_info.get("TrackName")
            or "the speedway"
        )

        return {
            "track_name": track_name,
            "track_config": weekend_info.get("TrackConfigName", ""),
            "track_city": weekend_info.get("TrackCity", ""),
            "track_state": weekend_info.get("TrackState", ""),
            "track_country": weekend_info.get("TrackCountry", ""),
            "track_length": weekend_info.get("TrackLengthOfficial")
            or weekend_info.get("TrackLength", ""),
            "track_type": weekend_info.get("TrackType", ""),
            "track_direction": weekend_info.get("TrackDirection", ""),
            "weather": weekend_info.get("TrackWeatherType", "unknown"),
            "skies": weekend_info.get("TrackSkies", "unknown"),
            "air_temp": self.safe_read("AirTemp"),
            "track_temp": self.safe_read("TrackTempCrew"),
            "track_wetness": self.safe_read("TrackWetness"),
            "wind_speed": self.safe_read("WindVel"),
            "humidity": self.safe_read("RelativeHumidity"),
        }

    def debug_weekend_info(self):
        weekend_info = self.get_weekend_info()

        print()
        print("=" * 60)
        print("WEEKEND INFO DEBUG")
        print("=" * 60)

        for key, value in weekend_info.items():
            print(f"{key}: {value}")

        print("=" * 60)

    def safe_read(self, key):
        try:
            return self.ir[key]
        except Exception:
            return None