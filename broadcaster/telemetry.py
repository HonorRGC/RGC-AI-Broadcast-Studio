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