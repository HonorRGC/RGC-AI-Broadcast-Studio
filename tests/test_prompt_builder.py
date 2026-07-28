from production.editorial_producer import EditorialItem
from production.multiclass import build_multiclass_context
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


def test_prompt_prioritizes_league_track_history_over_generic_track_talk():
    assignment = EditorialItem(
        story_type="biggest_mover",
        headline="Driver moving forward",
        summary="The 34 has gained five positions.",
    )

    prompt = PromptBuilder().build_prompt(
        "jeff",
        assignment,
        race_knowledge={
            "track_profile": {
                "style": "pack_draft",
                "label": "pack drafting track",
                "notes": "Pack momentum can matter here.",
            },
            "league_driver_context": [
                (
                    "T.J. Lee in the number 34 stats: last race finish: 1st; "
                    "track starts: 6, track wins: 2, best track finish: 1st"
                )
            ],
        },
    )

    assert "League-stat priority" in prompt["user"]
    assert "has won at this track before" in prompt["user"]
    assert "Use at most one stat" in prompt["user"]
    assert "Draft-track restraint" in prompt["user"]


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
    assert "Do not refer to another booth member in third person" in prompt["system"]
    assert "Do not ask another booth member a question" in prompt["system"]
    assert "what the booth just framed" in prompt["user"]
    assert "ask another broadcaster a question" in prompt["user"]
    assert "refer to the booth in third person" in prompt["user"]


def test_prompt_includes_road_course_discipline():
    assignment = EditorialItem(
        story_type="battle",
        headline="Battle for fifth",
        summary="Two cars are close through the middle sector.",
    )

    prompt = PromptBuilder().build_prompt(
        "jeff",
        assignment,
        race_knowledge={
            "track_profile": {
                "style": "road_course",
                "label": "road course",
                "notes": "Emphasize braking zones and corner exits.",
            }
        },
    )

    assert "Track Profile: road course" in prompt["user"]
    assert "Road-course discipline" in prompt["user"]
    assert "freight-train" in prompt["user"]
    assert "braking zone" in prompt["user"]


def test_prompt_adds_draft_track_restraint_for_routine_driver_stories():
    assignment = EditorialItem(
        story_type="biggest_mover",
        headline="Driver moving forward",
        summary="The 24 has gained six positions.",
    )

    prompt = PromptBuilder().build_prompt(
        "jeff",
        assignment,
        race_knowledge={
            "track_profile": {
                "style": "pack_draft",
                "label": "pack drafting track",
                "notes": "Pack momentum and lane timing can matter here.",
            }
        },
    )

    assert "Draft-track restraint" in prompt["user"]
    assert "do not mention the draft" in prompt["user"]
    assert "routine driver stories" in prompt["user"]
    assert "execution, patience, timing" in prompt["user"]


def test_prompt_includes_multiclass_discipline():
    assignment = EditorialItem(
        story_type="battle",
        headline="Class traffic developing",
        summary="A faster car is closing on slower traffic.",
    )
    multiclass = build_multiclass_context(
        [{"CarIdx": 1, "Position": 1}, {"CarIdx": 2, "Position": 2}],
        {
            1: {"name": "Prototype Leader", "number": "1", "car_class_id": "p2", "car_class_short_name": "LMP2"},
            2: {"name": "GT Leader", "number": "21", "car_class_id": "gt3", "car_class_short_name": "GT3"},
        },
    )

    prompt = PromptBuilder().build_prompt(
        "jeff",
        assignment,
        race_knowledge={"multiclass": multiclass},
    )

    assert "Multiclass Race: YES" in prompt["user"]
    assert "LMP2" in prompt["user"]
    assert "GT3" in prompt["user"]
    assert "Multiclass discipline" in prompt["user"]
    assert "overall lead" in prompt["user"]
