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


def test_prompt_encourages_natural_booth_chemistry_without_forcing_banter():
    assignment = EditorialItem(
        story_type="battle",
        headline="Lead battle tightening",
        summary="The second-place car is closing on the leader.",
    )

    prompt = PromptBuilder().build_prompt("lead", assignment)

    assert "three-person booth" in prompt["system"]
    assert "do not force banter" in prompt["system"]
    assert "Booth chemistry" in prompt["user"]
    assert "Continue the previous thought" in prompt["user"]
    assert "Do not say broadcaster names" in prompt["user"]
    assert "Keep any handoff short and conversational" in prompt["user"]


def test_prompt_forbids_script_style_broadcaster_name_prefixes():
    assignment = EditorialItem(
        story_type="pit_strategy",
        headline="Pit strategy developing",
        summary="Several cars are short-pitting under green.",
    )

    prompt = PromptBuilder().build_prompt("sarah", assignment)

    assert "Do not start with broadcaster names" in prompt["system"]
    assert "Mike:" not in prompt["system"]
    assert "Jeff:" not in prompt["system"]
    assert "Sarah:" not in prompt["system"]
    assert "Mike," not in prompt["system"]
    assert "Jeff," not in prompt["system"]
    assert "Do not directly call out another broadcaster by name" in prompt["system"]
    assert "what the booth just framed" in prompt["user"]
