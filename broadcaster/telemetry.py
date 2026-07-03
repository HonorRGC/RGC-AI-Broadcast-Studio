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

    def is_replay_at_live_edge(self, frame_tolerance=120):
        frame_number = self.safe_read("ReplayFrameNum")
        frame_end = self.safe_read("ReplayFrameNumEnd")
        try:
            return int(frame_end) - int(frame_number) <= int(frame_tolerance)
        except (TypeError, ValueError):
            return None

    def return_to_live(self):
        try:
            seek_sent = self.ir.replay_search(irsdk.RpySrchMode.to_end)
            speed_sent = self.ir.replay_set_play_speed(1)
            return bool(seek_sent and speed_sent)
        except Exception:
            return False

    def get_session_time(self):
        try:
            return float(self.ir["SessionTime"] or 0.0)
        except Exception:
            return 0.0

    def seek_replay_session_time(self, session_num, session_time_seconds):
        try:
            seek_sent = self.ir.replay_search_session_time(
                int(session_num),
                max(0, int(float(session_time_seconds) * 1000)),
            )
            speed_sent = self.ir.replay_set_play_speed(1)
            return bool(seek_sent and speed_sent)
        except Exception:
            return False

    def seek_previous_incident(self, pre_roll_frames=360):
        try:
            seek_sent = self.ir.replay_search(irsdk.RpySrchMode.prev_incident)
            if pre_roll_frames:
                self.ir.replay_set_play_position(
                    irsdk.RpyPosMode.current,
                    -abs(int(pre_roll_frames)),
                )
            speed_sent = self.ir.replay_set_play_speed(1)
            return bool(seek_sent and speed_sent)
        except Exception:
            return False

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
        results = [
            dict(car)
            for car in self.get_current_session().get("ResultsPositions") or []
        ]
        incident_counts = self.get_car_idx_incident_counts()
        if incident_counts:
            for car in results:
                car_idx = car.get("CarIdx")
                try:
                    count = incident_counts[int(car_idx)]
                except (IndexError, TypeError, ValueError):
                    continue
                if count is not None:
                    car["Incidents"] = int(count)

        player_car_idx = self.get_player_car_idx()
        if player_car_idx is not None:
            incident_count = self.get_player_incident_count()
            for car in results:
                if car.get("CarIdx") == player_car_idx:
                    car["Incidents"] = incident_count
                    break
        return results

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

    def switch_camera_to_incident(self, group_number, camera_number=0):
        try:
            return bool(
                self.ir.cam_switch_pos(
                    irsdk.csMode.at_incident,
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

    def get_car_idx_incident_counts(self):
        for key in [
            "CarIdxIncidentCount",
            "CarIdxIncidents",
            "CarIdxMyIncidentCount",
            "CarIdxDriverIncidentCount",
        ]:
            values = self.safe_array_read(key)
            if values:
                return values
        return []

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
