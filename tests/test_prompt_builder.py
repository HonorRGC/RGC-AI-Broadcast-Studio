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
