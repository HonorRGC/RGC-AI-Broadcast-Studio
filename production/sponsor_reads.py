from config import (
    OVERLAY_EVENT_TITLE,
    OVERLAY_RACE_SPONSOR,
    SPONSOR_READ_CAUSE,
    SPONSOR_READ_MESSAGE,
    SPONSOR_READ_NAME,
    USE_SPONSOR_READS,
)


class SponsorReadDirector:
    """Schedules tasteful sponsor mentions at natural broadcast breaks."""

    def __init__(
        self,
        enabled=USE_SPONSOR_READS,
        sponsor_name=SPONSOR_READ_NAME,
        cause=SPONSOR_READ_CAUSE,
        custom_message=SPONSOR_READ_MESSAGE,
        event_title=OVERLAY_EVENT_TITLE,
        fallback_sponsor=OVERLAY_RACE_SPONSOR,
        max_caution_reads=2,
    ):
        self.enabled = bool(enabled)
        self.sponsor_name = (sponsor_name or fallback_sponsor or "").strip()
        self.cause = (cause or self.detect_cause(event_title) or "").strip()
        self.custom_message = (custom_message or "").strip()
        self.max_caution_reads = int(max_caution_reads)
        self.opening_read_sent = False
        self.caution_reads_sent = 0
        self.caution_laps_used = set()

    def has_read(self):
        return bool(self.enabled and self.build_message())

    def opening_read(self):
        if self.opening_read_sent:
            return None
        message = self.build_message(opening=True)
        if message:
            self.opening_read_sent = True
        return message

    def caution_read(self, current_lap=0):
        if self.caution_reads_sent >= self.max_caution_reads:
            return None
        if current_lap in self.caution_laps_used:
            return None
        message = self.build_message(opening=False)
        if message:
            self.caution_reads_sent += 1
            self.caution_laps_used.add(current_lap)
        return message

    def build_message(self, opening=False):
        if not self.enabled:
            return ""

        if self.custom_message:
            return self.apply_custom_message_tokens(self.custom_message)

        if not self.sponsor_name and not self.cause:
            return ""

        if self.sponsor_name and self.cause:
            if self.is_autism_awareness(self.cause):
                if opening:
                    return (
                        f"Tonight's broadcast is presented by {self.sponsor_name}, "
                        "as we help shine a light on Autism Awareness and celebrate "
                        "understanding, acceptance, and the families that make this "
                        "community stronger."
                    )
                return (
                    f"Tonight's coverage is presented by {self.sponsor_name}. "
                    "A reminder from all of us at RGC: Autism Awareness is about "
                    "understanding, acceptance, and supporting the families in our "
                    "racing community."
                )
            return (
                f"Tonight's coverage is presented by {self.sponsor_name}, "
                f"proudly supporting {self.cause}."
            )

        if self.sponsor_name:
            return f"Tonight's coverage is presented by {self.sponsor_name}."

        return f"Tonight's broadcast is proud to support {self.cause}."

    @staticmethod
    def detect_cause(event_title):
        title = str(event_title or "")
        if "autism" in title.lower():
            return "Autism Awareness"
        return ""

    @staticmethod
    def is_autism_awareness(cause):
        return "autism" in str(cause or "").lower()

    def apply_custom_message_tokens(self, message):
        return (
            str(message or "")
            .replace("{sponsor}", self.sponsor_name)
            .replace("{cause}", self.cause)
        ).strip()
