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

    def get_session_state(self):
        try:
            return int(self.ir["SessionState"] or 0)
        except Exception:
            return 0

    def get_current_session_num(self):
        try:
            return int(self.ir["SessionNum"])
        except Exception:
            session_info = self.get_session_info() or {}
            try:
                return int(session_info.get("CurrentSessionNum", 0))
            except (TypeError, ValueError):
                return 0

    def get_current_session(self):
        session_info = self.get_session_info() or {}
        sessions = session_info.get("Sessions", []) or []
        current_session_num = self.get_current_session_num()

        for session in sessions:
            try:
                if int(session.get("SessionNum")) == current_session_num:
                    return session
            except (TypeError, ValueError):
                continue

        if 0 <= current_session_num < len(sessions):
            return sessions[current_session_num]
        return {}

    def get_session_type(self):
        session = self.get_current_session()
        return session.get("SessionType") or session.get("SessionName") or "Unknown"

    def get_total_laps(self):
        session = self.get_current_session()

        try:
            return int(session.get("SessionLaps", 0))
        except Exception:
            return 0

    def get_results(self):
        return self.get_current_session().get("ResultsPositions") or []

    def get_starting_grid(self):
        """Return the fullest available race grid before live results populate."""
        current_results = self.get_results()
        candidates = [current_results, self.get_qualifying_results()]

        sessions = (self.get_session_info() or {}).get("Sessions", []) or []
        current_session_num = self.get_current_session_num()
        for session in reversed(sessions):
            try:
                session_num = int(session.get("SessionNum", -1))
            except (TypeError, ValueError):
                session_num = -1
            session_type = str(
                session.get("SessionType") or session.get("SessionName") or ""
            ).lower()
            if session_num < current_session_num and "qual" in session_type:
                candidates.append(session.get("ResultsPositions") or [])

        return max(candidates, key=self._valid_result_count, default=[])

    def get_qualifying_results(self):
        qualify_info = self.safe_read("QualifyResultsInfo") or {}
        if not isinstance(qualify_info, dict):
            return []
        return qualify_info.get("Results") or []

    @staticmethod
    def _valid_result_count(results):
        return sum(1 for car in results or [] if car.get("CarIdx") is not None)

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

    def get_camera_groups(self):
        camera_info = self.safe_read("CameraInfo") or {}
        if not isinstance(camera_info, dict):
            return []
        return camera_info.get("Groups") or []

    def switch_camera_to_car(self, car_number, group_number, camera_number=0):
        try:
            return bool(
                self.ir.cam_switch_num(
                    str(car_number),
                    int(group_number),
                    int(camera_number),
                )
            )
        except Exception:
            return False

    def clean_driver_name(self, name):
        if not name:
            return name

        cleaned = str(name).strip()
        cleaned = re.sub(r"(?<=[A-Za-z])\d+$", "", cleaned).strip()

        return cleaned

    def get_player_car_idx(self):
        try:
            return int(self.ir["PlayerCarIdx"])
        except Exception:
            return None

    def get_player_incident_count(self):
        for key in [
            "PlayerCarMyIncidentCount",
            "PlayerCarDriverIncidentCount",
            "PlayerIncidents",
            "PlayerCarTeamIncidentCount",
        ]:
            try:
                value = self.ir[key]
                if value is not None:
                    return int(value)
            except Exception:
                pass

        return 0

    def get_car_idx_on_pit_road(self):
        try:
            data = self.ir["CarIdxOnPitRoad"]
            if data is None:
                return []
            return list(data)
        except Exception:
            return []

    def get_car_idx_track_surface(self):
        return self.safe_array_read("CarIdxTrackSurface")

    def get_car_idx_track_surface_material(self):
        return self.safe_array_read("CarIdxTrackSurfaceMaterial")

    def get_car_idx_lap_dist_pct(self):
        return self.safe_array_read("CarIdxLapDistPct")

    def get_car_idx_est_time(self):
        return self.safe_array_read("CarIdxEstTime")

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

    def safe_array_read(self, key):
        try:
            data = self.ir[key]
            if data is None:
                return []
            return list(data)
        except Exception:
            return []
