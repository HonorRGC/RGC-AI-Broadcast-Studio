import irsdk


class IRacingTelemetry:
    def __init__(self):
        self.ir = irsdk.IRSDK()

    def startup(self):
        return self.ir.startup()

    def is_connected(self):
        return self.ir.is_initialized and self.ir.is_connected

    def get_results(self):
        session_info = self.ir["SessionInfo"]

        if not session_info:
            return []

        current_session = session_info.get("CurrentSessionNum", 0)
        sessions = session_info.get("Sessions", [])

        if current_session >= len(sessions):
            return []

        session = sessions[current_session]
        return session.get("ResultsPositions") or []