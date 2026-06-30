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

        cleaned = self.remove_debug_phrases(cleaned)
        cleaned = self.remove_duplicate_sentences(cleaned)
        cleaned = self.fix_spacing(cleaned)

        return cleaned.strip()

    def remove_debug_phrases(self, message):
        patterns = [
            r"\bStory type:\s*[^.]+\.?",
            r"\bCurrent story:\s*[^.]+\.?",
            r"\bConfidence:\s*\d+\s*percent\.?",
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