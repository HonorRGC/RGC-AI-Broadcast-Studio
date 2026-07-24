from config import (
    OVERLAY_EVENT_TITLE,
    OVERLAY_RACE_SPONSOR,
    RACE_SPONSOR_NAMES,
    RACE_SPONSOR_READS,
    SPONSOR_READ_CAUSE,
    SPONSOR_READ_MESSAGE,
    SPONSOR_READ_NAME,
    SPONSOR_READ_NAME_2,
    SPONSOR_READ_NAME_3,
    USE_SPONSOR_READS,
)


class SponsorReadDirector:
    """Schedules tasteful sponsor mentions at natural broadcast breaks."""

    def __init__(
        self,
        enabled=USE_SPONSOR_READS,
        sponsor_name=SPONSOR_READ_NAME,
        sponsor_name_2=SPONSOR_READ_NAME_2,
        sponsor_name_3=SPONSOR_READ_NAME_3,
        sponsor_names=None,
        sponsor_reads=None,
        cause=SPONSOR_READ_CAUSE,
        custom_message=SPONSOR_READ_MESSAGE,
        event_title=OVERLAY_EVENT_TITLE,
        fallback_sponsor=OVERLAY_RACE_SPONSOR,
        max_caution_reads=2,
    ):
        self.enabled = bool(enabled)
        self.sponsor_name = (sponsor_name or fallback_sponsor or "").strip()
        self.sponsor_names = self.clean_sponsor_names(
            sponsor_names
            if sponsor_names is not None
            else RACE_SPONSOR_NAMES or [self.sponsor_name, sponsor_name_2, sponsor_name_3]
        )
        self.sponsor_name = self.sponsor_names[0] if self.sponsor_names else ""
        self.sponsor_reads = {
            str(name or "").strip().lower(): str(read or "").strip()
            for name, read in (sponsor_reads or RACE_SPONSOR_READS or {}).items()
            if str(name or "").strip() and str(read or "").strip()
        }
        self.cause = (cause or self.detect_cause(event_title) or "").strip()
        self.custom_message = (custom_message or "").strip()
        self.max_caution_reads = int(max_caution_reads)
        self.opening_read_sent = False
        self.caution_reads_sent = 0
        self.caution_laps_used = set()
        self.read_index = 0

    def has_read(self):
        return bool(self.enabled and self.build_message())

    def opening_read(self):
        if self.opening_read_sent:
            return None
        message = self.build_message(opening=True, sponsor_name=self.next_sponsor_name())
        if message:
            self.opening_read_sent = True
        return message

    def caution_read(self, current_lap=0):
        if self.caution_reads_sent >= self.max_caution_reads:
            return None
        if current_lap in self.caution_laps_used:
            return None
        message = self.build_message(opening=False, sponsor_name=self.next_sponsor_name())
        if message:
            self.caution_reads_sent += 1
            self.caution_laps_used.add(current_lap)
        return message

    def build_message(self, opening=False, sponsor_name=None):
        if not self.enabled:
            return ""

        sponsor_name = (sponsor_name if sponsor_name is not None else self.current_sponsor_name()).strip()

        sponsor_script = self.sponsor_reads.get(sponsor_name.lower(), "")
        if sponsor_script:
            return self.with_cause(
                self.apply_custom_message_tokens(sponsor_script, sponsor_name)
            )

        if self.custom_message:
            return self.with_cause(
                self.apply_custom_message_tokens(self.custom_message, sponsor_name)
            )

        if not sponsor_name and not self.cause:
            return ""

        if sponsor_name and self.cause:
            if self.is_autism_awareness(self.cause):
                if opening:
                    return (
                        f"Tonight's broadcast is presented by {sponsor_name}, "
                        "as we help shine a light on Autism Awareness and celebrate "
                        "understanding, acceptance, and the families that make this "
                        "community stronger."
                    )
                return (
                    f"Tonight's coverage is presented by {sponsor_name}. "
                    "A reminder from all of us at RGC: Autism Awareness is about "
                    "understanding, acceptance, and supporting the families in our "
                    "racing community."
                )
            return (
                f"Tonight's coverage is presented by {sponsor_name}, "
                f"proudly supporting {self.cause}."
            )

        if sponsor_name:
            return self.with_cause(f"Tonight's coverage is presented by {sponsor_name}.")

        return f"Tonight's broadcast is proud to support {self.cause}."

    def next_sponsor_name(self):
        if not self.sponsor_names:
            return ""
        sponsor = self.sponsor_names[self.read_index % len(self.sponsor_names)]
        self.read_index += 1
        return sponsor

    def current_sponsor_name(self):
        return self.sponsor_names[0] if self.sponsor_names else ""

    @staticmethod
    def clean_sponsor_names(names):
        seen = set()
        cleaned = []
        for name in names or []:
            text = str(name or "").strip()
            if not text:
                continue
            key = text.lower()
            if key in seen:
                continue
            cleaned.append(text)
            seen.add(key)
        return cleaned[:5]

    @staticmethod
    def detect_cause(event_title):
        title = str(event_title or "")
        if "autism" in title.lower():
            return "Autism Awareness"
        return ""

    @staticmethod
    def is_autism_awareness(cause):
        return "autism" in str(cause or "").lower()

    def apply_custom_message_tokens(self, message, sponsor_name=None):
        return (
            str(message or "")
            .replace("{sponsor}", sponsor_name if sponsor_name is not None else self.current_sponsor_name())
            .replace("{cause}", self.cause)
        ).strip()

    def with_cause(self, message):
        message = str(message or "").strip()
        if not message or not self.cause:
            return message
        normalized_message = message.lower()
        normalized_cause = self.cause.lower()
        if normalized_cause in normalized_message:
            return message
        if self.is_autism_awareness(self.cause):
            return (
                f"{message} A reminder from all of us at RGC: Autism Awareness is about "
                "understanding, acceptance, and supporting the families in our racing community."
            )
        return f"{message} The broadcast is also proud to support {self.cause}."
