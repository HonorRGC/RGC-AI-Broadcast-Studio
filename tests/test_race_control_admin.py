from types import SimpleNamespace

from app import handle_producer_command
from broadcast.broadcast_queue import BroadcastQueue
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
        self.special = None

    def add_producer_event(self, **kwargs):
        self.events.append(kwargs)

    def show_special_presentation(self, **kwargs):
        self.special = kwargs

    def clear_special_presentation(self):
        self.special = None

    def current_state_dict(self):
        return {
            "event": {
                "sponsor_graphics": ["/assets/rgc.png"],
                "graphics": ["/assets/fallback.png"],
            }
        }


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


def test_race_control_service_reports_copy_failure():
    source = SourceSpy(result="copy_failed")
    service = RaceControlService(enabled=True)

    result = service.execute("throw_yellow", {}, source)

    assert result.ok is False
    assert result.command == "!yellow"
    assert "Could not copy" in result.message


def test_producer_race_control_command_logs_to_feed():
    source = SourceSpy()
    overlay = OverlaySpy()
    service = RaceControlService(enabled=True)
    race_director = SimpleNamespace(marked=False)
    race_director.mark_admin_caution_pending = lambda: setattr(race_director, "marked", True)

    handle_producer_command(
        "race_control",
        {"action": "throw_yellow"},
        overlay,
        source=source,
        engine=SimpleNamespace(race_director=race_director),
        booth=None,
        camera_director=SimpleNamespace(),
        race_control_service=service,
    )

    assert source.commands == ["!yellow"]
    assert race_director.marked is True
    assert overlay.events[0]["title"] == "Race Control"
    assert "!yellow" in overlay.events[0]["message"]


def test_producer_race_control_drive_through_is_broadcast():
    source = SourceSpy()
    overlay = OverlaySpy()
    service = RaceControlService(enabled=True)
    queue = BroadcastQueue()

    handle_producer_command(
        "race_control",
        {
            "action": "drive_through",
            "car_number": "34",
            "driver_name": "T.J. Lee",
        },
        overlay,
        source=source,
        engine=SimpleNamespace(broadcast_queue=queue),
        booth=None,
        camera_director=SimpleNamespace(),
        race_control_service=service,
    )

    assert source.commands == ["!black #34 D"]
    assert queue.items[0].message == (
        "Race control has issued a drive-through penalty to the 34 of T.J. Lee."
    )
    assert queue.items[0].category == "race_control"


def test_producer_race_control_caution_management_is_broadcast():
    source = SourceSpy()
    overlay = OverlaySpy()
    service = RaceControlService(enabled=True)
    queue = BroadcastQueue()

    handle_producer_command(
        "race_control",
        {"action": "extend_caution"},
        overlay,
        source=source,
        engine=SimpleNamespace(broadcast_queue=queue),
        booth=None,
        camera_director=SimpleNamespace(),
        race_control_service=service,
    )
    handle_producer_command(
        "race_control",
        {"action": "one_to_green"},
        overlay,
        source=source,
        engine=SimpleNamespace(broadcast_queue=queue),
        booth=None,
        camera_director=SimpleNamespace(),
        race_control_service=service,
    )

    messages = [item.message for item in queue.items]
    assert "Race control is extending this caution one more lap" in messages[0]
    assert "Race control has shortened this caution" in messages[1]


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


def test_producer_can_show_and_clear_caution_review_slate():
    overlay = OverlaySpy()

    handle_producer_command(
        "caution_review_slate_on",
        {},
        overlay,
        source=SimpleNamespace(),
        engine=None,
        booth=None,
        camera_director=SimpleNamespace(),
    )

    assert overlay.special["kind"] == "caution_review_slate"
    assert overlay.special["title"] == "Caution Review"
    assert overlay.special["graphics"] == ["/assets/rgc.png"]
    assert "review slate is live" in overlay.events[0]["message"].lower()

    handle_producer_command(
        "caution_review_slate_off",
        {},
        overlay,
        source=SimpleNamespace(),
        engine=None,
        booth=None,
        camera_director=SimpleNamespace(),
    )

    assert overlay.special is None
    assert "cleared" in overlay.events[1]["message"].lower()
