from types import SimpleNamespace

from app import handle_producer_command
from production.race_control import RaceControlCommandBuilder, RaceControlService


class SourceSpy:
    def __init__(self, result=True):
        self.commands = []
        self.result = result

    def send_admin_chat_command(self, command):
        self.commands.append(command)
        return self.result


class OverlaySpy:
    def __init__(self):
        self.events = []

    def add_producer_event(self, **kwargs):
        self.events.append(kwargs)


def test_race_control_builder_formats_global_commands():
    builder = RaceControlCommandBuilder()

    assert builder.build("throw_yellow").command == "!yellow"
    assert builder.build("extend_caution").command == "!pacelaps +1"
    assert builder.build("one_to_green").command == "!pacelaps 1"
    assert builder.build("clear_all").command == "!clearall"


def test_race_control_builder_formats_driver_commands():
    builder = RaceControlCommandBuilder()
    payload = {"car_number": "34"}

    assert builder.build("clear_penalty", payload).command == "!clear #34"
    assert builder.build("eol", payload).command == "!eol #34"
    assert builder.build("drive_through", payload).command == "!black #34 D"
    assert builder.build("timed_black", {"car_number": "34", "seconds": 25}).command == "!black #34 25"
    assert builder.build("waveby", payload).command == "!waveby #34"
    assert builder.build("dq", payload).command == "!dq #34"
    assert builder.build("remove", payload).command == "!remove #34"


def test_race_control_service_blocks_when_disabled():
    source = SourceSpy()
    service = RaceControlService(enabled=False)

    result = service.execute("throw_yellow", {}, source)

    assert result.ok is False
    assert source.commands == []
    assert "OFF" in result.message


def test_race_control_service_sends_when_enabled():
    source = SourceSpy()
    service = RaceControlService(enabled=True)

    result = service.execute("drive_through", {"car_number": "34"}, source)

    assert result.ok is True
    assert source.commands == ["!black #34 D"]
    assert "sent" in result.message


def test_race_control_service_reports_broadcast_safe_clipboard_mode():
    source = SourceSpy(result="copied")
    service = RaceControlService(enabled=True)

    result = service.execute("throw_yellow", {}, source)

    assert result.ok is True
    assert result.command == "!yellow"
    assert "copied" in result.message
    assert "broadcast-safe" in result.message


def test_race_control_service_reports_open_chat_mode():
    source = SourceSpy(result="chat_opened")
    service = RaceControlService(enabled=True)

    result = service.execute("throw_yellow", {}, source)

    assert result.ok is True
    assert result.command == "!yellow"
    assert "prepared in iRacing chat" in result.message
    assert "Ctrl+V" in result.message


def test_producer_race_control_command_logs_to_feed():
    source = SourceSpy()
    overlay = OverlaySpy()
    service = RaceControlService(enabled=True)

    handle_producer_command(
        "race_control",
        {"action": "clear_penalty", "car_number": "34"},
        overlay,
        source=source,
        engine=None,
        booth=None,
        camera_director=SimpleNamespace(),
        race_control_service=service,
    )

    assert source.commands == ["!clear #34"]
    assert overlay.events[0]["title"] == "Race Control"
    assert "!clear #34" in overlay.events[0]["message"]


def test_producer_can_toggle_race_admin_mode():
    overlay = OverlaySpy()
    service = RaceControlService(enabled=False)

    handle_producer_command(
        "race_admin_on",
        {},
        overlay,
        source=SimpleNamespace(),
        engine=None,
        booth=None,
        camera_director=SimpleNamespace(),
        race_control_service=service,
    )

    assert service.enabled is True
    assert "enabled" in overlay.events[0]["message"]
