from production.commentary_cleaner import CommentaryCleaner


def test_commentary_cleaner_removes_broadcast_angle_label():
    cleaner = CommentaryCleaner()

    cleaned = cleaner.clean(
        "Michael DeTurck has taken the race lead. "
        "Broadcast angle: fight for control of the race."
    )

    assert cleaned == "Michael DeTurck has taken the race lead."
    assert "Broadcast angle" not in cleaned


def test_commentary_cleaner_removes_broadcaster_script_prefixes():
    cleaner = CommentaryCleaner()

    assert cleaner.clean("Mike: Green flag is in the air.") == "Green flag is in the air."
    assert cleaner.clean("Jeff, he is saving the right rear.") == "he is saving the right rear."
    assert cleaner.clean("Sarah - Pit road is busy.") == "Pit road is busy."
