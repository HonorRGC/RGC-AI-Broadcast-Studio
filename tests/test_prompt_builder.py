from production.editorial_producer import EditorialItem
from production.prompt_builder import PromptBuilder


def test_action_prompt_forbids_unverified_lane_claims():
    assignment = EditorialItem(
        story_type="three_car_battle",
        headline="Three-car battle developing",
        summary="Three drivers are packed together.",
    )

    prompt = PromptBuilder().build_prompt("lead", assignment)

    assert "Do not invent an inside or outside lane" in prompt["user"]
    assert "three-wide formation" in prompt["user"]


def test_prompt_includes_verified_league_driver_notes():
    assignment = EditorialItem(
        story_type="battle",
        headline="Austin Peterson is under pressure",
        summary="Austin Peterson is defending the lead.",
    )

    prompt = PromptBuilder().build_prompt(
        "jeff",
        assignment,
        race_knowledge={
            "league_driver_context": [
                (
                    "Austin Peterson in the number 77: from Nashville, TN, USA; "
                    "driving style: aggressive on restarts; sponsor: RGC Motorsports"
                )
            ]
        },
    )

    assert "Verified League Driver Notes:" in prompt["user"]
    assert "RGC Motorsports" in prompt["user"]
    assert "use at most one" in prompt["user"]


def test_prompt_includes_verified_league_stats():
    assignment = EditorialItem(
        story_type="battle",
        headline="Austin Peterson is under pressure",
        summary="Austin Peterson is defending the lead.",
    )

    prompt = PromptBuilder().build_prompt(
        "jeff",
        assignment,
        race_knowledge={
            "league_driver_context": [
                (
                    "Austin Peterson in the number 77 stats: points: 1st; "
                    "season wins: 4; track starts: 5, track wins: 2"
                )
            ]
        },
    )

    assert "Verified League Driver Notes:" in prompt["user"]
    assert "season wins: 4" in prompt["user"]
    assert "track wins: 2" in prompt["user"]


def test_prompt_includes_producer_notes_and_broadcast_angle():
    assignment = EditorialItem(
        story_type="biggest_mover",
        headline="Big mover",
        summary="The 24 is moving forward.",
        priority=8,
        broadcast_angle="quiet charge through traffic",
        producer_notes=("Do not make this only a position-gain read.",),
    )

    prompt = PromptBuilder().build_prompt("jeff", assignment)

    assert "Broadcast Angle: quiet charge through traffic" in prompt["user"]
    assert "Do not make this only a position-gain read" in prompt["user"]
    assert "not reading a timing screen" in prompt["user"]
