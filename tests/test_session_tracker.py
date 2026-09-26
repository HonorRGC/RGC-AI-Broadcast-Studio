from production.session_tracker import SessionTracker, WeekendSession


def test_tracker_normalizes_weekend_session_names():
    tracker = SessionTracker()

    assert tracker.update("Practice").current == WeekendSession.PRACTICE
    assert tracker.update("Lone Qualify").current == WeekendSession.QUALIFYING
    transition = tracker.update("Race")

    assert transition.entered_race is True
    assert tracker.is_race() is True


def test_unknown_session_is_not_treated_as_race():
    tracker = SessionTracker()

    transition = tracker.update("")

    assert transition.current == WeekendSession.UNKNOWN
    assert tracker.is_race() is False
