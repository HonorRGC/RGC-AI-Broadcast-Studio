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
            "You are part of a three-person booth with a lead announcer, "
            "analyst, and pit-road strategy reporter. "
            "Sound natural, human, and conversational. "
            "When it fits naturally, briefly answer, build on, or hand off to "
            "another broadcaster, but do not force banter into every call. "
            "Do not start with broadcaster names, role labels, or script-style "
            "prefixes followed by punctuation. Do not directly call out "
            "another broadcaster by name. "
            "Do not refer to another booth member in third person. "
            "Do not ask another booth member a question. "
            "Just continue the thought naturally in your own voice. "
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
        broadcast_angle = getattr(assignment, "broadcast_angle", "")
        if broadcast_angle:
            lines.append(f"Broadcast Angle: {broadcast_angle}")
        producer_notes = tuple(getattr(assignment, "producer_notes", ()) or ())
        if producer_notes:
            lines.append("Producer Notes:")
            for note in producer_notes[:5]:
                lines.append(f"- {note}")
        if getattr(assignment, "story_type", "") in (
            "side_by_side",
            "three_car_battle",
            "live_side_by_side",
            "live_three_wide",
            "live_pass_clear",
        ):
            lines.append(
                "Accuracy: Use only the stated relationship. Do not invent an inside "
                "or outside lane, three-wide formation, contact, or a completed pass "
                "unless the assignment explicitly says the pass looks clear."
            )
        lines.append("")

        if race_state:
            lines.append("RACE STATE")
            lines.append("----------")
            lines.append(f"Moment: {getattr(getattr(race_state, 'moment', None), 'value', 'UNKNOWN')}")
            lines.append(f"Lap: {getattr(race_state, 'current_lap', 0)} of {getattr(race_state, 'total_laps', 0)}")
            lines.append(
                f"Race Laps To Go: {getattr(race_state, 'laps_remaining', 0)}"
            )
            lines.append(
                "Lap wording: if you mention this number, call it laps to go "
                "or laps remaining. Do not say laps ahead."
            )
            lines.append(
                "Lap restraint: do not mention laps remaining on routine battle, "
                "pass, or driver update assignments unless the assignment is "
                "specifically about a lap-count milestone, the final 10 laps, "
                "white flag, checkered flag, caution, or restart."
            )
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

            league_driver_context = race_knowledge.get("league_driver_context") or []
            if league_driver_context:
                lines.append("Verified League Driver Notes:")
                for context_line in league_driver_context[:3]:
                    lines.append(f"- {context_line}")

            lines.append("")

        lines.append("DELIVERY INSTRUCTIONS")
        lines.append("---------------------")
        lines.append(self.delivery_instruction(speaker))
        lines.append(
            "Sound like you are following a race-long story, not reading a timing screen. "
            "If a position-gain fact is included, use it as supporting context, not the whole call."
        )
        lines.append(
            "Booth chemistry: if it sounds natural, make this feel like part of a "
            "team broadcast. Continue the previous thought, add a reason, answer "
            "the implied question, or connect strategy back to the race story. "
            "Do not say broadcaster names, ask another broadcaster a question, "
            "refer to the booth in third person, or use script-style labels. "
            "Keep any handoff short and conversational."
        )

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
                "It is okay to sound like you are answering the lead call or "
                "adding onto the previous thought when that fits the assignment. "
                "If verified league driver notes are provided, use at most one "
                "naturally fitting detail and do not force it. "
                "Limit it to 1 or 2 sentences."
            )

        if speaker == "sarah":
            return (
                "Give a short pit-road or strategy-style update. "
                "Focus on race strategy, timing, or consequences. "
                "It is okay to connect your update back to what the booth just "
                "framed, as long as the information stays specific. "
                "If verified league driver notes are provided, use at most one "
                "naturally fitting detail and do not force it. "
                "Limit it to 1 or 2 sentences."
            )

        return (
            "Deliver this like a lead announcer on a live race broadcast. "
            "Make it exciting but not overdone. "
            "When a story needs analysis or pit context, you may set up a "
            "short natural handoff without naming another broadcaster. "
            "If verified league driver notes are provided, use at most one "
            "naturally fitting detail and do not force it. "
            "Limit it to 1 or 2 sentences."
        )
