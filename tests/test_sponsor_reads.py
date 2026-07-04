from production.sponsor_reads import SponsorReadDirector


def test_sponsor_read_mentions_rgcmotorsports_and_autism_awareness():
    director = SponsorReadDirector(
        sponsor_name="RGC Motorsports",
        cause="Autism Awareness",
        event_title="RGC Autism Awareness 100",
    )

    message = director.opening_read()

    assert "RGC Motorsports" in message
    assert "Autism Awareness" in message
    assert "understanding" in message
    assert "acceptance" in message


def test_sponsor_read_can_detect_autism_from_event_title():
    director = SponsorReadDirector(
        sponsor_name="RGC Motorsports",
        cause="",
        event_title="RGC Autism Awareness 100",
    )

    message = director.caution_read(current_lap=12)

    assert "RGC Motorsports" in message
    assert "Autism Awareness" in message


def test_caution_sponsor_reads_are_capped_and_once_per_lap():
    director = SponsorReadDirector(
        sponsor_name="RGC Motorsports",
        cause="Autism Awareness",
        max_caution_reads=1,
    )

    first = director.caution_read(current_lap=10)
    same_lap = director.caution_read(current_lap=10)
    second_caution = director.caution_read(current_lap=20)

    assert first
    assert same_lap is None
    assert second_caution is None
