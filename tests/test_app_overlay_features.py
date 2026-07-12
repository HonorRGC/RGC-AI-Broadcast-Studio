from types import SimpleNamespace

from app import (
    find_brand_graphic_for_name,
    split_sponsor_names,
    should_show_movers_graphic,
    show_overlay_feature,
    sponsor_graphics_for_mentions,
    sponsor_mentions_for_message,
)


class OverlaySpy:
    def __init__(self):
        self.stat_panels = []
        self.special_presentations = []

    def show_stat_panel(self, **kwargs):
        self.stat_panels.append(kwargs)
        return True

    def show_special_presentation(self, **kwargs):
        self.special_presentations.append(kwargs)


class RaceIntelligenceStub:
    def __init__(self, movers):
        self.movers = movers

    def get_biggest_movers(self, limit=5):
        return self.movers[:limit]


def mover(car_idx, gained):
    return SimpleNamespace(
        car_idx=car_idx,
        positions_gained=gained,
        current_position=4,
        car_number="24",
        driver_name="Dean Marsh",
        starting_position=9,
    )


def engine_with_movers(*movers):
    return SimpleNamespace(race_intelligence=RaceIntelligenceStub(list(movers)))


def item(category="race_story", target=24, message="Driver has gained positions."):
    return SimpleNamespace(
        category=category,
        camera_target_car_idx=target,
        message=message,
    )


def test_pit_updates_do_not_show_overlay_graphic():
    overlay = OverlaySpy()

    show_overlay_feature(
        item(category="caution_pit_summary", target=None),
        overlay,
        source=SimpleNamespace(get_results=lambda: []),
        engine=SimpleNamespace(),
    )

    assert overlay.stat_panels == []


def test_biggest_movers_graphic_does_not_show_for_routine_position_gain():
    engine = engine_with_movers(mover(24, 3))

    assert should_show_movers_graphic(item(target=24), engine) is False


def test_biggest_movers_graphic_requires_target_to_be_top_mover():
    engine = engine_with_movers(mover(10, 8), mover(11, 7), mover(12, 6), mover(24, 9))

    assert should_show_movers_graphic(item(target=24), engine) is False


def test_biggest_movers_graphic_uses_shared_long_cooldown():
    overlay = OverlaySpy()
    engine = engine_with_movers(mover(24, 6))

    show_overlay_feature(item(target=24), overlay, engine=engine)

    assert overlay.stat_panels[0]["kind"] == "biggest_movers"
    assert overlay.stat_panels[0]["dedupe_key"] == "biggest_movers"
    assert overlay.stat_panels[0]["minimum_interval"] == 180.0


def test_sponsor_mention_graphic_pops_for_rgc_and_autism():
    overlay = OverlaySpy()
    message = (
        "Tonight's coverage is presented by RGC Motorsports. "
        "Autism Awareness is about understanding and acceptance."
    )

    show_overlay_feature(item(category="sponsor_read", target=None, message=message), overlay)

    presentation = overlay.special_presentations[0]
    assert presentation["kind"] == "sponsor_bug"
    assert presentation["duration"] == 5.0
    assert "RGC Motorsports" in presentation["title"]
    assert "Autism Awareness" in presentation["title"]
    assert "/assets/rgc_motorsports.png" in presentation["graphics"]
    assert "/assets/autism_awareness.png" in presentation["graphics"]


def test_sponsor_mention_detection_is_message_based():
    assert sponsor_mentions_for_message("Thanks to RGC Motorsports.") == [
        "RGC Motorsports"
    ]
    assert sponsor_mentions_for_message("Supporting autism families.") == [
        "Autism Awareness"
    ]


def test_sponsor_graphics_use_expected_defaults():
    assert sponsor_graphics_for_mentions(
        ["RGC Motorsports", "Autism Awareness"]
    ) == [
        "/assets/rgc_motorsports.png",
        "/assets/autism_awareness.png",
    ]


def test_sponsor_names_can_be_split_from_profile_style_value():
    assert split_sponsor_names("Bob's Auto Parts; Autism Awareness | RGC Motorsports") == [
        "Bob's Auto Parts",
        "Autism Awareness",
        "RGC Motorsports",
    ]


def test_sponsor_graphic_matching_uses_configured_brand_graphics(monkeypatch):
    import app

    monkeypatch.setattr(
        app,
        "OVERLAY_BRAND_GRAPHICS",
        [
            "/assets/bobs_auto_parts.png",
            "/assets/autism_awareness.png",
        ],
    )

    assert find_brand_graphic_for_name("Bob's Auto Parts") == "/assets/bobs_auto_parts.png"
