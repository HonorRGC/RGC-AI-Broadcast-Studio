class Jeff:
    """
    Jeff is the color analyst.

    He does not call the race.
    He explains why a story matters.
    """

    def analyze(self, event):
        story = getattr(event, "story", "")
        message = getattr(event, "message", "")
        event_type = getattr(event, "event_type", "")

        if event_type == "PASS":
            return self.analyze_pass(event, story, message)

        return None

    def analyze_pass(self, event, story, message):
        new_position = getattr(event, "new_position", 999)
        positions_gained = getattr(event, "positions_gained_from_start", 0)

        if new_position == 1:
            return (
                "That is a huge moment. Taking the lead is one thing, "
                "but now the question is whether he can control the pace from out front."
            )

        if positions_gained >= 8:
            return (
                "What impresses me is the patience. He has not had to force every move, "
                "he has just kept putting himself in the right position."
            )

        if new_position <= 5:
            return (
                "That is where the race changes. Once you get inside the top five, "
                "every mistake matters and every restart becomes critical."
            )

        if new_position <= 10:
            return (
                "That is a good, steady drive. He is not just gaining spots, "
                "he is putting himself into the conversation."
            )

        return None