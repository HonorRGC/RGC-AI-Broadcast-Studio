class PromptBuilder:
    """
    Builds structured prompts for OpenAI commentary.

    OpenAI should not decide what matters.
    It receives a clear broadcast assignment and turns it into natural speech.
    """

    def build_prompt(
        self,
        speaker,
        assignment,
        race_state=None,
        race_knowledge=None,
        broadcast_style="professional TV",
    ):
        speaker = str(speaker or "lead").lower()

        system_prompt = self.build_system_prompt(speaker, broadcast_style)
        user_prompt = self.build_user_prompt(
            speaker=speaker,
            assignment=assignment,
            race_state=race_state,
            race_knowledge=race_knowledge,
        )

        return {
            "system": system_prompt,
            "user": user_prompt,
        }

    def build_system_prompt(self, speaker, broadcast_style):
        role = self.speaker_role(speaker)

        return (
            f"You are {role} for a professional motorsports broadcast. "
            f"The broadcast style is {broadcast_style}. "
            "Sound natural, human, and conversational. "
            "Do not mention telemetry, data, story type, confidence, or internal system terms. "
            "Do not repeat the same idea twice. "
            "Keep it concise and broadcast-ready."
        )

    def build_user_prompt(self, speaker, assignment, race_state=None, race_knowledge=None):
        lines = []

        lines.append("EDITORIAL ASSIGNMENT")
        lines.append("--------------------")
        lines.append(f"Headline: {getattr(assignment, 'headline', '')}")
        lines.append(f"Summary: {getattr(assignment, 'summary', '')}")
        lines.append(f"Priority: {getattr(assignment, 'priority', '')}")
        lines.append("")

        if race_state:
            lines.append("RACE STATE")
            lines.append("----------")
            lines.append(f"Moment: {getattr(getattr(race_state, 'moment', None), 'value', 'UNKNOWN')}")
            lines.append(f"Lap: {getattr(race_state, 'current_lap', 0)} of {getattr(race_state, 'total_laps', 0)}")
            lines.append(f"Laps Remaining: {getattr(race_state, 'laps_remaining', 0)}")
            lines.append("")

        if race_knowledge:
            lines.append("RACE CONTEXT")
            lines.append("------------")

            best_battle = race_knowledge.get("best_battle")
            if best_battle:
                lines.append(f"Best Battle: {getattr(best_battle, 'summary', '')}")

            top_story = race_knowledge.get("top_story")
            if top_story:
                lines.append(f"Top Story: {getattr(top_story, 'summary', '')}")

            lines.append("")

        lines.append("DELIVERY INSTRUCTIONS")
        lines.append("---------------------")
        lines.append(self.delivery_instruction(speaker))

        return "\n".join(lines)

    def speaker_role(self, speaker):
        if speaker == "jeff":
            return "the color commentator"

        if speaker == "sarah":
            return "the pit and strategy reporter"

        return "the lead announcer"

    def delivery_instruction(self, speaker):
        if speaker == "jeff":
            return (
                "Give one sharp analyst-style observation. "
                "Explain why this matters or what the driver did well. "
                "Limit it to 1 or 2 sentences."
            )

        if speaker == "sarah":
            return (
                "Give a short pit-road or strategy-style update. "
                "Focus on race strategy, timing, or consequences. "
                "Limit it to 1 or 2 sentences."
            )

        return (
            "Deliver this like a lead announcer on a live race broadcast. "
            "Make it exciting but not overdone. "
            "Limit it to 1 or 2 sentences."
        )