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


def test_sponsor_read_uses_separate_cause_name_and_spoken_read():
    director = SponsorReadDirector(
        sponsor_name="RGC Motorsports",
        cause="Autism Awareness",
        cause_read="Autism Awareness celebrates understanding, acceptance, and support for every family in the racing community.",
    )

    message = director.opening_read()

    assert "RGC Motorsports" in message
    assert "Autism Awareness celebrates understanding" in message


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


def test_sponsor_reads_rotate_spoken_sponsors_in_order():
    director = SponsorReadDirector(
        sponsor_names=["Sponsor One", "Sponsor Two", "Sponsor Three"],
        cause="Community Night",
        custom_message="{sponsor} is supporting {cause}.",
    )

    opening = director.opening_read()
    first_caution = director.caution_read(current_lap=10)
    second_caution = director.caution_read(current_lap=20)

    assert opening == "Sponsor One is supporting Community Night."
    assert first_caution == "Sponsor Two is supporting Community Night."
    assert second_caution == "Sponsor Three is supporting Community Night."


def test_sponsor_reads_support_five_sponsors_and_per_sponsor_scripts():
    director = SponsorReadDirector(
        sponsor_names=["One", "Two", "Three", "Four", "Five"],
        sponsor_reads={
            "One": "{sponsor} brings you the opening laps.",
            "Two": "{sponsor} keeps us rolling.",
        },
        cause="Autism Awareness",
        max_caution_reads=5,
    )

    messages = [
        director.opening_read(),
        director.caution_read(current_lap=10),
        director.caution_read(current_lap=20),
        director.caution_read(current_lap=30),
        director.caution_read(current_lap=40),
    ]

    assert "One brings you the opening laps." in messages[0]
    assert "Two keeps us rolling." in messages[1]
    assert "Three" in messages[2]
    assert "Four" in messages[3]
    assert "Five" in messages[4]
    assert all("Autism Awareness" in message for message in messages)


def test_sponsor_read_custom_script_supports_tokens():
    director = SponsorReadDirector(
        sponsor_name="RGC Motorsports",
        cause="Autism Awareness",
        custom_message=(
            "Tonight's race is presented by {sponsor}, proudly supporting {cause}."
        ),
    )

    message = director.opening_read()

    assert message == (
        "Tonight's race is presented by RGC Motorsports, "
        "proudly supporting Autism Awareness."
    )
