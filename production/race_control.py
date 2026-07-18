from __future__ import annotations

from dataclasses import dataclass


DRIVER_ACTIONS = {
    "clear_penalty",
    "eol",
    "drive_through",
    "timed_black",
    "waveby",
    "dq",
    "remove",
}

DANGEROUS_ACTIONS = {
    "throw_yellow",
    "clear_all",
    "dq",
    "remove",
}


@dataclass
class RaceControlCommand:
    action: str
    command: str
    label: str
    requires_driver: bool = False
    dangerous: bool = False


@dataclass
class RaceControlResult:
    ok: bool
    command: str = ""
    message: str = ""
    action: str = ""
    dangerous: bool = False


class RaceControlCommandBuilder:
    def build(self, action, payload=None):
        payload = payload or {}
        action = str(action or "").strip().lower()
        driver = self.driver_token(payload)

        if action == "throw_yellow":
            return RaceControlCommand(
                action=action,
                command=self.with_optional_message("!yellow", payload),
                label="Throw caution",
                dangerous=True,
            )
        if action == "extend_caution":
            return RaceControlCommand(
                action=action,
                command="!pacelaps +1",
                label="Extend caution one lap",
            )
        if action == "one_to_green":
            return RaceControlCommand(
                action=action,
                command="!pacelaps 1",
                label="Set caution to one-to-green",
            )
        if action == "clear_all":
            return RaceControlCommand(
                action=action,
                command="!clearall",
                label="Clear all penalties",
                dangerous=True,
            )

        if action in DRIVER_ACTIONS and not driver:
            raise ValueError("Select a driver before sending this race-control command.")

        if action == "clear_penalty":
            return RaceControlCommand(action, f"!clear {driver}", "Clear driver penalty", True)
        if action == "eol":
            return RaceControlCommand(action, f"!eol {driver}", "Send driver EOL", True)
        if action == "drive_through":
            return RaceControlCommand(action, f"!black {driver} D", "Give drive-through", True)
        if action == "timed_black":
            seconds = self.penalty_seconds(payload)
            return RaceControlCommand(
                action,
                f"!black {driver} {seconds}",
                f"Give {seconds}-second black flag",
                True,
            )
        if action == "waveby":
            return RaceControlCommand(action, f"!waveby {driver}", "Wave driver around", True)
        if action == "dq":
            return RaceControlCommand(action, f"!dq {driver}", "Disqualify driver", True, True)
        if action == "remove":
            return RaceControlCommand(action, f"!remove {driver}", "Remove driver", True, True)

        raise ValueError(f"Unknown race-control action: {action}")

    def driver_token(self, payload):
        token = str(payload.get("driver_token", "") or "").strip()
        if token:
            return self.clean_driver_token(token)
        car_number = str(payload.get("car_number", "") or "").strip()
        if car_number:
            return f"#{self.clean_car_number(car_number)}"
        return ""

    @staticmethod
    def clean_car_number(value):
        cleaned = "".join(ch for ch in str(value or "") if ch.isalnum())
        return cleaned[:8]

    @staticmethod
    def clean_driver_token(value):
        value = str(value or "").strip()
        if value.startswith("#"):
            return f"#{RaceControlCommandBuilder.clean_car_number(value)}"
        return ".".join(part for part in value.replace(" ", ".").split(".") if part)[:64]

    @staticmethod
    def penalty_seconds(payload):
        try:
            seconds = int(payload.get("seconds", 15))
        except (TypeError, ValueError):
            seconds = 15
        return max(1, min(seconds, 120))

    @staticmethod
    def with_optional_message(command, payload):
        message = str(payload.get("message", "") or "").strip()
        if not message:
            return command
        safe_message = " ".join(message.replace("\r", " ").replace("\n", " ").split())
        return f"{command} {safe_message[:120]}"


class RaceControlService:
    def __init__(self, enabled=False, builder=None):
        self.enabled = bool(enabled)
        self.builder = builder or RaceControlCommandBuilder()

    def set_enabled(self, enabled):
        self.enabled = bool(enabled)

    def execute(self, action, payload, source):
        if not self.enabled:
            return RaceControlResult(
                ok=False,
                action=str(action or ""),
                message="Race Admin Mode is OFF. Turn it on before sending iRacing admin commands.",
            )

        try:
            command = self.builder.build(action, payload)
        except ValueError as exc:
            return RaceControlResult(
                ok=False,
                action=str(action or ""),
                message=str(exc),
            )

        sender = getattr(source, "send_admin_chat_command", None)
        if not callable(sender):
            return RaceControlResult(
                ok=False,
                action=command.action,
                command=command.command,
                dangerous=command.dangerous,
                message="This telemetry source cannot send iRacing admin chat commands.",
            )

        send_result = sender(command.command)
        if send_result == "copied":
            return RaceControlResult(
                ok=True,
                action=command.action,
                command=command.command,
                dangerous=command.dangerous,
                message=(
                    f"{command.label} copied for broadcast-safe manual send: {command.command}. "
                    "Paste/send it in iRacing chat, or use RACE_ADMIN_SEND_MODE=ui_paste for off-stream testing."
                ),
            )

        sent = bool(send_result)
        return RaceControlResult(
            ok=sent,
            action=command.action,
            command=command.command,
            dangerous=command.dangerous,
            message=(
                f"{command.label} sent: {command.command}"
                if sent
                else f"iRacing did not accept the admin command: {command.command}"
            ),
        )
