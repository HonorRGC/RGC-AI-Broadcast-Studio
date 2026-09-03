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
            "live_pressure_battle",
        ):
            lines.append(
                "Accuracy: Use only the stated relationship. Unless the assignment "
                "explicitly says a driver worked past another driver, describe this as a close "
                "battle, pressure, or cars stacked together. Do not invent an inside "
                "or outside lane, side-by-side formation, three-wide formation, "
                "contact, or a completed pass."
            )
        if getattr(assignment, "story_type", "") == "formation_multiple_packs":
            lines.append(
                "Accuracy: Talk only about the packs and gap stated in the "
                "assignment. Do not invent which lane caused the split, do not "
                "claim the second pack is catching the lead pack unless the "
                "assignment says so, and keep this as a concise race-development call."
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

            track_profile = race_knowledge.get("track_profile") or {}
            if track_profile:
                label = track_profile.get("label") or track_profile.get("style") or ""
                notes = track_profile.get("notes") or ""
                if label:
                    lines.append(f"Track Profile: {label}")
                if notes:
                    lines.append(f"Track Guidance: {notes}")

            multiclass = race_knowledge.get("multiclass")
            if getattr(multiclass, "active", False):
                lines.extend(multiclass.to_prompt_lines())

            league_driver_context = race_knowledge.get("league_driver_context") or []
            if league_driver_context:
                lines.append("Verified League Driver Profiles:")
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
            "Restraint: do not add tire wear, fuel mileage, patience, strategy, "
            "or racecraft reasoning to every routine battle or driver update. "
            "Many good calls should be simple: identify the battle, name the "
            "drivers, include one useful stat or driver note if available, and "
            "let the camera breathe."
        )
        if getattr(assignment, "story_type", "") in (
            "battle",
            "battle_for_top_five",
            "battle_for_top_ten",
            "side_by_side",
            "three_car_battle",
            "live_side_by_side",
            "live_three_wide",
            "live_pressure_battle",
        ):
            lines.append(
                "Battle variety: do not make this the same gap-and-pressure call "
                "every time. Choose one angle: spotlight under-covered drivers, "
                "tell viewers this is worth watching for a few corners, connect "
                "one verified driver stat if available, or simply let the pictures "
                "carry the moment. Avoid adding a generic lesson at the end."
            )
        lines.append(
            "Booth chemistry: if it sounds natural, make this feel like part of a "
            "team broadcast. Continue the previous thought, add a reason, answer "
            "the implied question, or connect strategy back to the race story. "
            "Do not say broadcaster names, ask another broadcaster a question, "
            "refer to the booth in third person, or use script-style labels. "
            "Keep any handoff short and conversational."
        )
        league_driver_context = (race_knowledge or {}).get("league_driver_context") or []
        if league_driver_context:
            lines.append(
                "League-stat priority: when verified league profiles include track "
                "starts, track wins, best track finish, previous race finish, "
                "points position, season wins, or career starts, prefer one "
                "naturally fitting stat over another generic track-style comment. "
                "Strong examples: a driver has won at this track before, ran "
                "well here previously, finished well last time out, or has a "
                "championship points battle shaping the race. When the story is "
                "about a driver gaining spots, defending position, leading, "
                "recovering, or losing ground, points position and points-to-next "
                "are useful if they raise the stakes. Use at most one stat in the call."
            )
        track_profile = (race_knowledge or {}).get("track_profile") or {}
        if track_profile.get("style") == "pack_draft":
            lines.append(
                "Draft-track restraint: the race is at a drafting track, but do "
                "not mention the draft, freight train, lanes, air, or pack "
                "momentum in every call. Use that language only when the "
                "assignment is specifically about a pack formation, lane move, "
                "fuel saving in traffic, or a run being built. For routine "
                "driver stories, focus instead on execution, patience, timing, "
                "pressure, confidence, track position, or how the driver's race "
                "is developing."
            )
        if track_profile.get("style") == "road_course":
            lines.append(
                "Road-course discipline: avoid oval pack-draft, freight-train, "
                "and lane-train language unless the assignment explicitly supports it. "
                "Use road-racing terms like braking zone, apex, corner exit, curbs, "
                "traffic, undercut, overcut, and track limits when they fit."
            )
        multiclass = (race_knowledge or {}).get("multiclass")
        if getattr(multiclass, "active", False):
            lines.append(
                "Multiclass discipline: do not call every overall-position move "
                "as a same-class battle. When possible, identify whether the "
                "story is for the overall lead, an in-class position, or faster "
                "class traffic working through slower class traffic."
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
                "Explain why this matters only when the story needs it; "
                "otherwise add a quick observation and let the race breathe. "
                "It is okay to sound like you are answering the lead call or "
                "adding onto the previous thought when that fits the assignment. "
                "If verified league driver profiles are provided, use at most one "
                "naturally fitting detail and do not force it. "
                "Limit it to 1 or 2 sentences."
            )

        if speaker == "sarah":
            return (
                "Give a short pit-road or strategy-style update. "
                "Focus on race strategy, timing, or consequences when the "
                "assignment is a pit or strategy item; otherwise keep it factual. "
                "It is okay to connect your update back to what the booth just "
                "framed, as long as the information stays specific. "
                "If verified league driver profiles are provided, use at most one "
                "naturally fitting detail and do not force it. "
                "Limit it to 1 or 2 sentences."
            )

        return (
            "Deliver this like a lead announcer on a live race broadcast. "
            "Make it exciting but not overdone. "
            "When a story needs analysis or pit context, you may set up a "
            "short natural handoff without naming another broadcaster. "
            "If verified league driver profiles are provided, use at most one "
            "naturally fitting detail and do not force it. "
            "Limit it to 1 or 2 sentences."
        )
