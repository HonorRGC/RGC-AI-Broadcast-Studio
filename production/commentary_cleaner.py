import re


class CommentaryCleaner:
    """
    Cleans rule-based commentary before it reaches the booth.

    This is a temporary bridge until OpenAI generates more natural
    broadcast language.
    """

    def clean(self, message):
        if not message:
            return ""

        cleaned = str(message)

        cleaned = self.remove_broadcaster_prefix(cleaned)
        cleaned = self.remove_broadcaster_asides(cleaned)
        cleaned = self.remove_broadcaster_third_person(cleaned)
        cleaned = self.remove_debug_phrases(cleaned)
        cleaned = self.remove_duplicate_sentences(cleaned)
        cleaned = self.remove_wrapping_quotes(cleaned)
        cleaned = self.fix_spacing(cleaned)

        return cleaned.strip()

    def remove_broadcaster_prefix(self, message):
        cleaned = re.sub(r"^\s*[\"'“”‘’]+", "", message)
        return re.sub(
            r"^\s*(Mike|Jeff|Sarah|Lead|Color|Pit)\s*[:,-]\s*",
            "",
            cleaned,
            flags=re.IGNORECASE,
        )

    def remove_broadcaster_asides(self, message):
        cleaned = re.sub(
            r"\s*,\s*(Mike|Jeff|Sarah)\s*,\s*",
            " ",
            message,
            flags=re.IGNORECASE,
        )
        cleaned = re.sub(
            r"^\s*(Mike|Jeff|Sarah)\s*,\s+",
            "",
            cleaned,
            flags=re.IGNORECASE,
        )
        return cleaned

    def remove_broadcaster_third_person(self, message):
        patterns = [
            (
                r"\b(Mike|Jeff|Sarah)\s+will be watching whether\b",
                "We'll watch whether",
            ),
            (
                r"\b(Mike|Jeff|Sarah)\s+will be watching to see if\b",
                "We'll watch to see if",
            ),
            (
                r"\b(Mike|Jeff|Sarah)\s+will be watching\b",
                "We'll be watching",
            ),
        ]
        cleaned = message
        for pattern, replacement in patterns:
            cleaned = re.sub(pattern, replacement, cleaned, flags=re.IGNORECASE)
        return cleaned

    def remove_wrapping_quotes(self, message):
        cleaned = message.strip()
        cleaned = re.sub(r"^[\"'“”‘’]+", "", cleaned)
        cleaned = re.sub(r"[\"'“”‘’]+$", "", cleaned)
        return cleaned

    def remove_debug_phrases(self, message):
        patterns = [
            r"\bStory type:\s*[^.]+\.?",
            r"\bCurrent story:\s*[^.]+\.?",
            r"\bConfidence:\s*\d+\s*percent\.?",
            r"\bBroadcast angle:\s*[^.?!]+[.?!]?",
            r"\bBroadcast Angle:\s*[^.?!]+[.?!]?",
            r"\bUse confident but careful wording:\s*[^.?!]+[.?!]?",
            r"\bUse confident but careful language\.?",
            r"\bconfident but careful wording[:,]?\s*",
            r"\bconfident but careful language[:,]?\s*",
            r"\bwithout mentioning telemetry, confidence, leaderboard delay, or official scoring delay\.?",
            r"\bwithout mentioning telemetry, confidence, or official scoring delay\.?",
            r"\bofficial scoring delay\.?",
            r"\bHe is currently the biggest mover in the field\.?",
            r"\bShe is currently the biggest mover in the field\.?",
        ]

        cleaned = message

        for pattern in patterns:
            cleaned = re.sub(pattern, "", cleaned, flags=re.IGNORECASE)

        return cleaned

    def remove_duplicate_sentences(self, message):
        sentences = re.split(r"(?<=[.!?])\s+", message)
        seen = set()
        output = []

        for sentence in sentences:
            normalized = sentence.strip().lower()

            if not normalized:
                continue

            if normalized in seen:
                continue

            seen.add(normalized)
            output.append(sentence.strip())

        return " ".join(output)

    def fix_spacing(self, message):
        message = re.sub(r"\s+", " ", message)
        message = re.sub(r"\s+\.", ".", message)
        message = re.sub(r"\s+,", ",", message)
        return message
