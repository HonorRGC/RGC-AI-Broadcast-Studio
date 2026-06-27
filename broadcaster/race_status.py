class RaceStatus:
    GREEN = 0x00000004
    YELLOW = 0x00000008
    YELLOW_WAVING = 0x00000100
    CAUTION = 0x00004000
    CAUTION_WAVING = 0x00008000

    def __init__(self):
        self.is_caution = False
        self.is_green = False
        self.was_caution = False
        self.was_green = False
        self.last_flags = None

    def update_from_flags(self, session_flags):
        self.last_flags = session_flags

        self.was_caution = self.is_caution
        self.was_green = self.is_green

        if session_flags is None:
            self.is_caution = False
            self.is_green = False
            return

        self.is_green = bool(session_flags & self.GREEN)

        self.is_caution = bool(
            session_flags & self.YELLOW
            or session_flags & self.YELLOW_WAVING
            or session_flags & self.CAUTION
            or session_flags & self.CAUTION_WAVING
        )

    def yellow_just_came_out(self):
        return self.is_caution and not self.was_caution

    def green_just_came_out(self):
        return self.is_green and not self.was_green