from production.commentary_cleaner import CommentaryCleaner


def test_commentary_cleaner_removes_broadcast_angle_label():
    cleaner = CommentaryCleaner()

    cleaned = cleaner.clean(
        "Michael DeTurck has taken the race lead. "
        "Broadcast angle: fight for control of the race."
    )

    assert cleaned == "Michael DeTurck has taken the race lead."
    assert "Broadcast angle" not in cleaned
