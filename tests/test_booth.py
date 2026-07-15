from broadcast.booth import BroadcastBooth


def test_no_voice_flag_reports_why_audio_is_disabled():
    booth = BroadcastBooth(enable_voice=False)

    ready, reason = booth.voice_status()

    assert ready is False
    assert reason == "disabled by --no-voice"


def test_broadcast_booth_publishes_to_producer_sink():
    events = []
    booth = BroadcastBooth(enable_voice=False, producer_sink=lambda **event: events.append(event))

    booth.broadcast("Green flag is in the air.", speaker="lead")

    assert events == [
        {
            "kind": "broadcast",
            "title": "RGC BROADCAST - LEAD",
            "message": "Green flag is in the air.",
            "speaker": "LEAD",
        }
    ]
