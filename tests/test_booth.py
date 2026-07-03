from broadcast.booth import BroadcastBooth


def test_no_voice_flag_reports_why_audio_is_disabled():
    booth = BroadcastBooth(enable_voice=False)

    ready, reason = booth.voice_status()

    assert ready is False
    assert reason == "disabled by --no-voice"
