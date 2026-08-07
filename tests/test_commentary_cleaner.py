from production.commentary_cleaner import CommentaryCleaner


def test_commentary_cleaner_removes_broadcast_angle_label():
    cleaner = CommentaryCleaner()

    cleaned = cleaner.clean(
        "Michael DeTurck has taken the race lead. "
        "Broadcast angle: fight for control of the race."
    )

    assert cleaned == "Michael DeTurck has taken the race lead."
    assert "Broadcast angle" not in cleaned


def test_commentary_cleaner_removes_live_battle_prompt_leakage():
    cleaner = CommentaryCleaner()

    cleaned = cleaner.clean(
        "Use confident but careful wording: the pass looks complete live, "
        "while official scoring may take a moment to update. T.J. Lee has "
        "cleared the 24 on the outside."
    )

    assert cleaned == "T.J. Lee has cleared the 24 on the outside."
    assert "confident but careful" not in cleaned
    assert "official scoring" not in cleaned


def test_commentary_cleaner_removes_scoring_disclaimer_without_prefix():
    cleaner = CommentaryCleaner()

    cleaned = cleaner.clean(
        "Joshua Slate has worked past Luke Thompson for fourth. "
        "The pass looks complete as they run."
    )

    assert cleaned == "Joshua Slate has worked past Luke Thompson for fourth."
    assert "pass looks complete" not in cleaned


def test_commentary_cleaner_removes_broadcaster_script_prefixes():
    cleaner = CommentaryCleaner()

    assert cleaner.clean("Mike: Green flag is in the air.") == "Green flag is in the air."
    assert cleaner.clean("Jeff, he is saving the right rear.") == "he is saving the right rear."
    assert cleaner.clean("Sarah - Pit road is busy.") == "Pit road is busy."


def test_commentary_cleaner_removes_broadcaster_asides_from_openai_lines():
    cleaner = CommentaryCleaner()

    assert cleaner.clean(
        "Clean air is Armstrong's prize right now, Jeff, but he's going to have to defend."
    ) == "Clean air is Armstrong's prize right now but he's going to have to defend."
    assert cleaner.clean(
        "The question now, Jeff, is whether the challenger can stay close enough."
    ) == "The question now is whether the challenger can stay close enough."
    assert cleaner.clean(
        "Mike, Porter has done the hard part by getting right to Armstrong's bumper."
    ) == "Porter has done the hard part by getting right to Armstrong's bumper."


def test_commentary_cleaner_rewrites_third_person_booth_references():
    cleaner = CommentaryCleaner()

    assert cleaner.clean(
        "Jeff will be watching whether that's traffic exposing the handling."
    ) == "We'll watch whether that's traffic exposing the handling."
    assert cleaner.clean(
        "Jeff: “That’s a tight three-car shelf forming with Hindley.”"
    ) == "That’s a tight three-car shelf forming with Hindley."
