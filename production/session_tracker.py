from dataclasses import dataclass
from enum import Enum


class WeekendSession(Enum):
    UNKNOWN = "Unknown"
    PRACTICE = "Practice"
    QUALIFYING = "Qualifying"
    WARMUP = "Warmup"
    RACE = "Race"


@dataclass(frozen=True)
class SessionTransition:
    previous: WeekendSession
    current: WeekendSession
    changed: bool

    @property
    def entered_race(self):
        return self.changed and self.current == WeekendSession.RACE


class SessionTracker:
    def __init__(self):
        self.current = WeekendSession.UNKNOWN

    def update(self, session_type):
        next_session = self.normalize(session_type)
        previous = self.current
        changed = next_session != previous
        self.current = next_session
        return SessionTransition(previous, next_session, changed)

    def is_race(self):
        return self.current == WeekendSession.RACE

    @staticmethod
    def normalize(value):
        text = str(value or "").strip().lower()
        if "race" in text:
            return WeekendSession.RACE
        if "qual" in text:
            return WeekendSession.QUALIFYING
        if "practice" in text:
            return WeekendSession.PRACTICE
        if "warm" in text:
            return WeekendSession.WARMUP
        return WeekendSession.UNKNOWN
