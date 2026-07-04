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
