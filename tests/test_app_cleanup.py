from app import cleanup_live_broadcast_session


class Source:
    def __init__(self):
        self.live_returns = 0

    def return_to_live(self):
        self.live_returns += 1
        return True


class ReplayDirector:
    def __init__(self):
        self.audio_stops = 0

    def stop_replay_audio(self):
        self.audio_stops += 1


class Controller:
    def __init__(self, method_name):
        self.stops = 0
        setattr(self, method_name, self.stop)

    def stop(self):
        self.stops += 1


def test_cleanup_live_broadcast_session_returns_live_and_stops_audio():
    source = Source()
    replay = ReplayDirector()
    anthem = Controller("stop_audio")
    practice = Controller("stop_music")
    caution_bed = Controller("stop")

    returned = cleanup_live_broadcast_session(
        source,
        replay_director=replay,
        anthem_director=anthem,
        practice_presentation_director=practice,
        caution_audio_bed=caution_bed,
    )

    assert returned is True
    assert source.live_returns == 1
    assert replay.audio_stops == 1
    assert anthem.stops == 1
    assert practice.stops == 1
    assert caution_bed.stops == 1
