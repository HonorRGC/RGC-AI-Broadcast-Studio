from types import SimpleNamespace

from app import cleanup_live_broadcast_session, prefade_music_before_restart_call


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


class FadeAudioBed:
    def __init__(self):
        self.calls = []

    def fade_out_and_wait(self, **kwargs):
        self.calls.append(kwargs)
        return True


def test_prefade_music_before_restart_call_blocks_for_one_to_green():
    audio = FadeAudioBed()
    item = SimpleNamespace(dedupe_key="race_control:one_to_green:restart")

    faded = prefade_music_before_restart_call(item, audio)

    assert faded is True
    assert audio.calls == [{"duration_seconds": 1.3, "steps": 12}]


def test_prefade_music_before_restart_call_ignores_other_broadcasts():
    audio = FadeAudioBed()
    item = SimpleNamespace(dedupe_key="race_control:caution")

    faded = prefade_music_before_restart_call(item, audio)

    assert faded is False
    assert audio.calls == []
