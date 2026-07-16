import json
import mimetypes
import threading
import time
from dataclasses import dataclass, field
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path
from typing import Any
from urllib.parse import unquote

from config import (
    OVERLAY_BRAND_GRAPHICS,
    OVERLAY_EVENT_TITLE,
    OVERLAY_RACE_SPONSOR,
    OVERLAY_SERIES_NAME,
)


@dataclass
class OverlayEventConfig:
    title: str = OVERLAY_EVENT_TITLE
    sponsor: str = OVERLAY_RACE_SPONSOR
    series: str = OVERLAY_SERIES_NAME
    graphics: list[str] = field(default_factory=lambda: list(OVERLAY_BRAND_GRAPHICS))


@dataclass
class LeaderboardEntry:
    position: int
    car_idx: int
    car_number: str
    driver_name: str
    laps_complete: int = 0
    interval: str = ""
    fastest_lap: str = ""
    starting_position: int = 0
    position_delta: int = 0
    laps_led: int = 0
    incidents: int = 0
    last_pit_lap: int = 0
    last_pit_stop_seconds: float = 0.0
    last_pit_lane_seconds: float = 0.0
    on_pit_road: bool = False
    producer_note: str = ""

    def to_dict(self):
        return {
            "position": self.position,
            "car_idx": self.car_idx,
            "car_number": self.car_number,
            "driver_name": self.driver_name,
            "laps_complete": self.laps_complete,
            "interval": self.interval,
            "fastest_lap": self.fastest_lap,
            "starting_position": self.starting_position,
            "position_delta": self.position_delta,
            "laps_led": self.laps_led,
            "incidents": self.incidents,
            "last_pit_lap": self.last_pit_lap,
            "last_pit_stop_seconds": self.last_pit_stop_seconds,
            "last_pit_lane_seconds": self.last_pit_lane_seconds,
            "on_pit_road": self.on_pit_road,
            "producer_note": self.producer_note,
        }


@dataclass
class FeaturedDriver:
    car_number: str = ""
    driver_name: str = ""
    story: str = ""
    car_image_url: str = ""
    expires_at: float = 0.0

    def to_dict(self):
        return {
            "car_number": self.car_number,
            "driver_name": self.driver_name,
            "story": self.story,
            "car_image_url": self.car_image_url,
        }


@dataclass
class SpecialPresentation:
    kind: str = ""
    title: str = ""
    subtitle: str = ""
    graphics: list[str] = field(default_factory=list)
    expires_at: float = 0.0

    def to_dict(self):
        return {
            "kind": self.kind,
            "title": self.title,
            "subtitle": self.subtitle,
            "graphics": list(self.graphics),
        }


@dataclass
class StatPanelRow:
    label: str = ""
    value: str = ""
    detail: str = ""

    def to_dict(self):
        return {
            "label": self.label,
            "value": self.value,
            "detail": self.detail,
        }


@dataclass
class StatPanel:
    kind: str = ""
    title: str = ""
    subtitle: str = ""
    rows: list[StatPanelRow] = field(default_factory=list)
    expires_at: float = 0.0

    def to_dict(self):
        return {
            "kind": self.kind,
            "title": self.title,
            "subtitle": self.subtitle,
            "rows": [row.to_dict() for row in self.rows],
        }


@dataclass
class ProducerFeedItem:
    kind: str = "info"
    title: str = ""
    message: str = ""
    speaker: str = ""
    created_at: float = 0.0

    def to_dict(self):
        return {
            "kind": self.kind,
            "title": self.title,
            "message": self.message,
            "speaker": self.speaker,
            "created_at": self.created_at,
        }


@dataclass
class OverlayState:
    event: OverlayEventConfig = field(default_factory=OverlayEventConfig)
    session_type: str = "Unknown"
    track_name: str = ""
    lap: int = 0
    total_laps: int = 0
    session_time_remaining: float = 0.0
    caution: bool = False
    green: bool = False
    featured_driver: FeaturedDriver | None = None
    special_presentation: SpecialPresentation | None = None
    stat_panel: StatPanel | None = None
    leaderboard: list[LeaderboardEntry] = field(default_factory=list)
    lap_history: list[dict[str, Any]] = field(default_factory=list)

    def to_dict(self):
        return {
            "event": {
                "title": self.event.title,
                "sponsor": self.event.sponsor,
                "series": self.event.series,
                "graphics": list(self.event.graphics),
            },
            "session_type": self.session_type,
            "track_name": self.track_name,
            "lap": self.lap,
            "total_laps": self.total_laps,
            "session_time_remaining": self.session_time_remaining,
            "caution": self.caution,
            "green": self.green,
            "featured_driver": (
                self.featured_driver.to_dict() if self.featured_driver else None
            ),
            "special_presentation": (
                self.special_presentation.to_dict()
                if self.special_presentation
                else None
            ),
            "stat_panel": self.stat_panel.to_dict() if self.stat_panel else None,
            "leaderboard": [entry.to_dict() for entry in self.leaderboard],
            "lap_history": list(self.lap_history),
        }


class OverlayStateBuilder:
    def __init__(
        self,
        event_config=None,
        max_entries=20,
        fixed_entries=15,
        cycle_interval_seconds=8,
        clock=None,
    ):
        self.event_config = event_config or OverlayEventConfig()
        self.max_entries = int(max_entries)
        self.fixed_entries = int(fixed_entries)
        self.cycle_interval_seconds = max(1, int(cycle_interval_seconds))
        self.clock = clock or time.monotonic
        self.last_leaderboard = []
        self.lap_status_by_lap = {}

    def build_from_telemetry(self, telemetry):
        results = telemetry.get_results()
        driver_lookup = telemetry.get_driver_lookup()
        track_info = telemetry.get_track_info()
        session_type_reader = getattr(telemetry, "get_session_type", None)
        session_type = session_type_reader() if session_type_reader else "Unknown"

        leaderboard = self.build_leaderboard(results, driver_lookup, session_type)
        if leaderboard:
            self.last_leaderboard = leaderboard
        elif self.is_race_session(session_type) and self.last_leaderboard:
            leaderboard = self.last_leaderboard

        lap = self.best_race_lap(results, telemetry.get_lap())
        caution = self.is_caution(telemetry)
        green = self.is_green(telemetry, session_type=session_type, lap=lap, caution=caution)
        self.update_lap_history(session_type, lap, caution, green)

        return OverlayState(
            event=self.event_config,
            session_type=session_type,
            track_name=(track_info or {}).get("track_name", ""),
            lap=lap,
            total_laps=self.safe_int(telemetry.get_total_laps()),
            session_time_remaining=self.session_time_remaining(telemetry),
            caution=caution,
            green=green,
            leaderboard=leaderboard,
            lap_history=self.build_lap_history(self.safe_int(telemetry.get_total_laps())),
        )

    def best_race_lap(self, results, telemetry_lap=0):
        laps = [self.safe_int(telemetry_lap)]
        for car in results or []:
            laps.append(self.safe_int(car.get("LapsComplete", car.get("Lap", 0))))
        return max(laps, default=0)

    def session_time_remaining(self, telemetry):
        reader = getattr(telemetry, "get_session_time_remaining", None)
        if not reader:
            return 0.0
        try:
            return max(float(reader() or 0.0), 0.0)
        except (TypeError, ValueError):
            return 0.0

    def build_leaderboard(self, results, driver_lookup, session_type="Race"):
        valid_results = [
            dict(car)
            for car in results or []
            if car.get("CarIdx") is not None
        ]
        zero_based = any(self.safe_int(car.get("Position"), 999) == 0 for car in valid_results)
        valid_results.sort(key=lambda car: self.safe_int(car.get("Position"), 999))
        leader_laps = max(
            [
                self.safe_int(car.get("LapsComplete", car.get("Lap", 0)))
                for car in valid_results
            ],
            default=0,
        )
        leader_car = valid_results[0] if valid_results else {}

        leaderboard = []
        for car in valid_results:
            car_idx = car.get("CarIdx")
            driver = (driver_lookup or {}).get(car_idx, {})
            raw_position = self.safe_int(car.get("Position"), len(leaderboard) + 1)
            display_position = raw_position + 1 if zero_based else raw_position
            starting_position = self.starting_position(car)
            position_delta = (
                starting_position - display_position if starting_position > 0 else 0
            )
            laps_led = self.laps_led(car)
            incidents = self.incident_count(car)
            last_pit_lap = self.last_pit_lap(car)
            last_pit_stop_seconds = self.last_pit_stop_seconds(car)
            last_pit_lane_seconds = self.last_pit_lane_seconds(car)
            fastest_lap = self.format_lap_time(self.best_lap_value(car))
            on_pit_road = self.on_pit_road(car)
            leaderboard.append(
                LeaderboardEntry(
                    position=display_position,
                    car_idx=car_idx,
                    car_number=str(driver.get("number") or "?"),
                    driver_name=str(driver.get("name") or f"Car {car_idx}"),
                    laps_complete=self.safe_int(
                        car.get("LapsComplete", car.get("Lap", 0))
                    ),
                    interval=self.format_entry_metric(
                        car,
                        display_position,
                        session_type,
                        leader_laps,
                        leader_car,
                    ),
                    fastest_lap=fastest_lap,
                    starting_position=starting_position,
                    position_delta=position_delta,
                    laps_led=laps_led,
                    incidents=incidents,
                    last_pit_lap=last_pit_lap,
                    last_pit_stop_seconds=last_pit_stop_seconds,
                    last_pit_lane_seconds=last_pit_lane_seconds,
                    on_pit_road=on_pit_road,
                    producer_note=self.producer_note(
                        driver_name=str(driver.get("name") or f"Car {car_idx}"),
                        display_position=display_position,
                        starting_position=starting_position,
                        position_delta=position_delta,
                        laps_led=laps_led,
                        incidents=incidents,
                        last_pit_lap=last_pit_lap,
                        last_pit_stop_seconds=last_pit_stop_seconds,
                        last_pit_lane_seconds=last_pit_lane_seconds,
                        on_pit_road=on_pit_road,
                        fastest_lap=fastest_lap,
                    ),
                )
            )
        return self.visible_leaderboard_window(leaderboard)

    def starting_position(self, car):
        for key in (
            "StartingPosition",
            "StartPosition",
            "StartPos",
            "GridPosition",
            "QualifyingPosition",
        ):
            value = self.safe_int(car.get(key), 0)
            if value > 0:
                return value
        return 0

    def laps_led(self, car):
        for key in ("LapsLed", "LedLaps", "LeaderLaps"):
            value = self.safe_int(car.get(key), 0)
            if value > 0:
                return value
        return 0

    def incident_count(self, car):
        for key in ("Incidents", "IncidentCount", "DriverIncidents"):
            value = self.safe_int(car.get(key), 0)
            if value > 0:
                return value
        return 0

    def last_pit_lap(self, car):
        for key in ("LastPitLap", "PitStopLap", "last_pit_lap"):
            value = self.safe_int(car.get(key), 0)
            if value > 0:
                return value
        return 0

    def last_pit_stop_seconds(self, car):
        for key in ("LastPitStopSeconds", "PitStopTime", "last_pit_stop_seconds"):
            value = self.safe_float(car.get(key), 0.0)
            if value > 0:
                return value
        return 0.0

    def last_pit_lane_seconds(self, car):
        for key in ("LastPitLaneSeconds", "PitLaneTime", "last_pit_lane_seconds"):
            value = self.safe_float(car.get(key), 0.0)
            if value > 0:
                return value
        return 0.0

    def on_pit_road(self, car):
        for key in ("OnPitRoad", "IsOnPitRoad", "PitRoad"):
            value = car.get(key)
            if value in (True, 1, "1", "true", "True", "YES", "yes"):
                return True
        return False

    def producer_note(
        self,
        driver_name="",
        display_position=0,
        starting_position=0,
        position_delta=0,
        laps_led=0,
        incidents=0,
        last_pit_lap=0,
        last_pit_stop_seconds=0.0,
        last_pit_lane_seconds=0.0,
        on_pit_road=False,
        fastest_lap="",
    ):
        name = driver_name or "This driver"
        if on_pit_road:
            return f"{name} is on pit road now; watch whether this is strategy or damage repair."
        if position_delta >= 5:
            return (
                f"Big mover: {name} is up {position_delta} spots from "
                f"{self.ordinal(starting_position)} on the grid."
            )
        if position_delta <= -5:
            return (
                f"{name} has lost {abs(position_delta)} spots from "
                f"{self.ordinal(starting_position)}; worth watching for trouble or strategy."
            )
        if laps_led > 0:
            lap_word = "lap" if laps_led == 1 else "laps"
            return f"{name} has led {laps_led} {lap_word} today."
        if last_pit_lap > 0:
            details = f"Last pit stop came around lap {last_pit_lap}"
            if last_pit_stop_seconds > 0:
                details += f" with {last_pit_stop_seconds:.1f} seconds stopped"
            if last_pit_lane_seconds > 0:
                details += f" and {last_pit_lane_seconds:.1f} seconds on pit lane"
            return details + "."
        if incidents >= 4:
            return f"{name} is carrying {incidents} incident points; keep an eye on the penalty limit."
        if fastest_lap:
            return f"Best lap for {name}: {fastest_lap}."
        return f"{name} is running {self.ordinal(display_position)}; check for nearby battles before making the call."

    def ordinal(self, value):
        value = self.safe_int(value)
        if value <= 0:
            return "--"
        if 10 <= value % 100 <= 20:
            suffix = "th"
        else:
            suffix = {1: "st", 2: "nd", 3: "rd"}.get(value % 10, "th")
        return f"{value}{suffix}"

    def format_entry_metric(
        self,
        car,
        display_position,
        session_type,
        leader_laps=0,
        leader_car=None,
    ):
        if self.is_timed_session(session_type):
            return self.format_lap_time(self.best_lap_value(car))
        explicit_laps_down = self.explicit_laps_down(car)
        if explicit_laps_down > 0:
            lap_word = "lap" if explicit_laps_down == 1 else "laps"
            return f"-{explicit_laps_down} {lap_word}"
        interval = self.format_interval(car)
        laps_down = self.computed_laps_down(car, leader_laps)
        if laps_down > 0 and self.should_show_computed_laps_down(
            car,
            leader_car or {},
            laps_down,
            interval,
        ):
            lap_word = "lap" if laps_down == 1 else "laps"
            return f"-{laps_down} {lap_word}"
        if display_position != 1 and interval:
            return interval
        if laps_down > 0:
            lap_word = "lap" if laps_down == 1 else "laps"
            return f"-{laps_down} {lap_word}"
        return "" if display_position == 1 else interval

    def explicit_laps_down(self, car):
        for key in ("LapsBehind", "LapsDown"):
            value = self.safe_int(car.get(key), 0)
            if value > 0:
                return value
        return 0

    def computed_laps_down(self, car, leader_laps=0):
        car_laps = self.safe_int(car.get("LapsComplete", car.get("Lap", 0)))
        if leader_laps > 0 and car_laps > 0:
            return max(leader_laps - car_laps, 0)
        return 0

    def should_show_computed_laps_down(self, car, leader_car, laps_down, interval=""):
        if laps_down >= 2:
            return True
        if not interval:
            return True

        leader_pct = self.lap_distance_pct(leader_car)
        car_pct = self.lap_distance_pct(car)
        if leader_pct is None or car_pct is None:
            return False

        # Avoid the common start/finish flash: leader has just crossed the
        # stripe, while the next cars are still at the end of the previous lap.
        if leader_pct <= 0.15 and car_pct >= 0.85:
            return False

        return True

    def lap_distance_pct(self, car):
        for key in ("LapDistPct", "LapDist", "LapDistancePct"):
            if key in car and car.get(key) not in (None, ""):
                value = self.safe_float(car.get(key), -1.0)
                if 0.0 <= value <= 1.0:
                    return value
        return None

    def is_timed_session(self, session_type):
        text = str(session_type or "").lower()
        return "practice" in text or "qual" in text

    def is_race_session(self, session_type):
        return "race" in str(session_type or "").lower()

    def best_lap_value(self, car):
        for key in ("FastestTime", "BestLapTime", "FastestLapTime", "BestTime"):
            if key in car and car.get(key) not in (None, "", 0, 0.0):
                return self.safe_float(car.get(key))
        return 0.0

    def format_lap_time(self, seconds):
        seconds = self.safe_float(seconds)
        if seconds <= 0:
            return ""
        minutes = int(seconds // 60)
        remainder = seconds - minutes * 60
        if minutes:
            return f"{minutes}:{remainder:06.3f}"
        return f"{remainder:.3f}"

    def is_caution(self, telemetry):
        flags_reader = getattr(telemetry, "get_session_flags", None)
        flags = flags_reader() if flags_reader else 0
        try:
            flags = int(flags or 0)
        except Exception:
            flags = 0
        return bool(flags & (0x00000008 | 0x00000100 | 0x00004000 | 0x00008000))

    def is_green(self, telemetry, session_type="Race", lap=0, caution=None):
        if caution is None:
            caution = self.is_caution(telemetry)
        if caution:
            return False

        flags_reader = getattr(telemetry, "get_session_flags", None)
        flags = flags_reader() if flags_reader else 0
        try:
            flags = int(flags or 0)
        except Exception:
            flags = 0
        if flags & 0x00000004:
            return True
        return self.is_race_session(session_type) and self.safe_int(lap) > 0

    def update_lap_history(self, session_type, lap, caution, green):
        lap = self.safe_int(lap)
        if not self.is_race_session(session_type) or lap <= 0:
            if not self.is_race_session(session_type):
                self.lap_status_by_lap = {}
            return
        status = "caution" if caution else "green" if green else ""
        if not status:
            return
        existing = self.lap_status_by_lap.get(lap)
        if existing == "caution":
            return
        self.lap_status_by_lap[lap] = status

    def build_lap_history(self, total_laps=0):
        if not self.lap_status_by_lap:
            return []
        total_laps = self.safe_int(total_laps)
        last_lap = max(max(self.lap_status_by_lap), total_laps)
        return [
            {"lap": lap, "status": self.lap_status_by_lap.get(lap, "pending")}
            for lap in range(1, last_lap + 1)
        ]

    def visible_leaderboard_window(self, leaderboard):
        if len(leaderboard) <= self.max_entries:
            return leaderboard[: self.max_entries]

        fixed_count = min(self.fixed_entries, self.max_entries)
        cycle_count = self.max_entries - fixed_count
        if cycle_count <= 0:
            return leaderboard[: self.max_entries]

        fixed = leaderboard[:fixed_count]
        rotating = leaderboard[fixed_count:]
        if len(rotating) <= cycle_count:
            return leaderboard[: self.max_entries]

        step = int(self.clock() // self.cycle_interval_seconds)
        page_count = (len(rotating) + cycle_count - 1) // cycle_count
        page = step % page_count
        start = page * cycle_count
        return fixed + rotating[start : start + cycle_count]

    def format_interval(self, car):
        if "Time" in car and car.get("Time") not in (None, ""):
            value = self.safe_float(car.get("Time"))
            if value > 0:
                return f"+{value:.1f}"
        if "Gap" in car and car.get("Gap") not in (None, ""):
            value = self.safe_float(car.get("Gap"))
            if value > 0:
                return f"+{value:.1f}"
        return ""

    @staticmethod
    def safe_int(value, default=0):
        try:
            return int(value)
        except (TypeError, ValueError):
            return default

    @staticmethod
    def safe_float(value, default=0.0):
        try:
            return float(value)
        except (TypeError, ValueError):
            return default


class OverlayServer:
    def __init__(self, host="127.0.0.1", port=8765, state_builder=None):
        self.host = host
        self.port = int(port)
        self.state_builder = state_builder or OverlayStateBuilder()
        self.state = OverlayState(event=self.state_builder.event_config)
        self.lock = threading.Lock()
        self.featured_driver = None
        self.special_presentation = None
        self.stat_panel = None
        self.last_stat_panel_key = ""
        self.last_stat_panel_at = 0.0
        self.producer_feed = []
        self.max_producer_feed_items = 60
        self.pending_commands = []
        self.control_state = {
            "auto_camera": True,
            "openai": False,
            "elevenlabs": False,
        }
        self.httpd = None
        self.thread = None
        self.static_dir = Path(__file__).resolve().parent / "static"
        self.paint_preview_dir = self.default_paint_preview_dir()

    @property
    def url(self):
        return f"http://{self.host}:{self.port}/overlay"

    @property
    def producer_url(self):
        return f"http://{self.host}:{self.port}/producer"

    def start(self):
        handler = self.make_handler()
        self.httpd = ThreadingHTTPServer((self.host, self.port), handler)
        self.thread = threading.Thread(
            target=self.httpd.serve_forever,
            name="rgc-overlay-server",
            daemon=True,
        )
        self.thread.start()
        return self.url

    def stop(self):
        if self.httpd:
            self.httpd.shutdown()
            self.httpd.server_close()
            self.httpd = None

    def update_from_telemetry(self, telemetry):
        state = self.state_builder.build_from_telemetry(telemetry)
        with self.lock:
            if (
                self.featured_driver
                and self.featured_driver.expires_at > time.monotonic()
            ):
                state.featured_driver = self.featured_driver
            else:
                self.featured_driver = None
            if (
                self.special_presentation
                and self.special_presentation.expires_at > time.monotonic()
            ):
                state.special_presentation = self.special_presentation
            else:
                self.special_presentation = None
            if self.stat_panel and self.stat_panel.expires_at > time.monotonic():
                state.stat_panel = self.stat_panel
            else:
                self.stat_panel = None
            self.state = state

    def show_featured_driver(
        self,
        car_number,
        driver_name,
        story="",
        duration=10.0,
        car_image_url="",
    ):
        with self.lock:
            self.featured_driver = FeaturedDriver(
                car_number=str(car_number or ""),
                driver_name=str(driver_name or ""),
                story=str(story or ""),
                car_image_url=str(car_image_url or ""),
                expires_at=time.monotonic() + float(duration),
            )
            self.state.featured_driver = self.featured_driver

    def show_special_presentation(
        self,
        kind,
        title,
        subtitle="",
        duration=90.0,
        graphics=None,
    ):
        with self.lock:
            self.special_presentation = SpecialPresentation(
                kind=str(kind or ""),
                title=str(title or ""),
                subtitle=str(subtitle or ""),
                graphics=list(graphics or self.state_builder.event_config.graphics),
                expires_at=time.monotonic() + float(duration),
            )
            self.state.special_presentation = self.special_presentation

    def clear_special_presentation(self):
        with self.lock:
            self.special_presentation = None
            self.state.special_presentation = None

    def show_stat_panel(
        self,
        kind,
        title,
        subtitle="",
        rows=None,
        duration=10.0,
        dedupe_key="",
        minimum_interval=12.0,
    ):
        now = time.monotonic()
        key = str(dedupe_key or f"{kind}:{title}:{subtitle}")
        with self.lock:
            if (
                key
                and key == self.last_stat_panel_key
                and now - self.last_stat_panel_at < float(minimum_interval)
            ):
                return False
            self.last_stat_panel_key = key
            self.last_stat_panel_at = now
            self.stat_panel = StatPanel(
                kind=str(kind or ""),
                title=str(title or ""),
                subtitle=str(subtitle or ""),
                rows=[
                    row
                    if isinstance(row, StatPanelRow)
                    else StatPanelRow(
                        label=str((row or {}).get("label", "")),
                        value=str((row or {}).get("value", "")),
                        detail=str((row or {}).get("detail", "")),
                    )
                    for row in (rows or [])
                ],
                expires_at=now + float(duration),
            )
            self.state.stat_panel = self.stat_panel
        return True

    def add_producer_event(self, kind="info", title="", message="", speaker=""):
        item = ProducerFeedItem(
            kind=str(kind or "info"),
            title=str(title or ""),
            message=str(message or ""),
            speaker=str(speaker or ""),
            created_at=time.time(),
        )
        with self.lock:
            self.producer_feed.insert(0, item)
            self.producer_feed = self.producer_feed[: self.max_producer_feed_items]
        return item

    def set_control_state(self, **updates):
        with self.lock:
            self.control_state.update(updates)

    def enqueue_command(self, command, payload=None):
        command_item = {
            "command": str(command or ""),
            "payload": dict(payload or {}),
            "created_at": time.time(),
        }
        with self.lock:
            self.pending_commands.append(command_item)
        return command_item

    def drain_commands(self):
        with self.lock:
            commands = list(self.pending_commands)
            self.pending_commands = []
        return commands

    def current_state_dict(self):
        with self.lock:
            data = self.state.to_dict()
            data["producer_feed"] = [item.to_dict() for item in self.producer_feed]
            data["control_state"] = dict(self.control_state)
            return data

    def make_handler(self):
        server = self

        class Handler(BaseHTTPRequestHandler):
            def do_GET(self):
                if self.path in ("/", "/overlay"):
                    self.send_text(OVERLAY_HTML, "text/html; charset=utf-8")
                    return

                if self.path == "/producer":
                    self.send_text(PRODUCER_HTML, "text/html; charset=utf-8")
                    return

                if self.path == "/overlay/state":
                    self.send_json(server.current_state_dict())
                    return

                if self.path.startswith("/assets/"):
                    self.send_asset(self.path.removeprefix("/assets/"))
                    return

                if self.path.startswith("/paint-previews/"):
                    self.send_paint_preview(self.path.removeprefix("/paint-previews/"))
                    return

                self.send_error(404)

            def do_POST(self):
                if self.path == "/producer/command":
                    try:
                        length = int(self.headers.get("Content-Length", "0") or 0)
                    except ValueError:
                        length = 0
                    raw_body = self.rfile.read(max(0, length))
                    try:
                        data = json.loads(raw_body.decode("utf-8") or "{}")
                    except json.JSONDecodeError:
                        self.send_json({"ok": False, "error": "Invalid JSON"})
                        return
                    command = str(data.get("command", "") or "")
                    payload = data.get("payload", {}) or {}
                    if not command:
                        self.send_json({"ok": False, "error": "Missing command"})
                        return
                    server.enqueue_command(command, payload)
                    self.send_json({"ok": True})
                    return

                self.send_error(404)

            def send_json(self, data: dict[str, Any]):
                body = json.dumps(data).encode("utf-8")
                self.send_response(200)
                self.send_header("Content-Type", "application/json")
                self.send_header("Cache-Control", "no-store")
                self.send_header("Content-Length", str(len(body)))
                self.end_headers()
                self.wfile.write(body)

            def send_text(self, text, content_type):
                body = text.encode("utf-8")
                self.send_response(200)
                self.send_header("Content-Type", content_type)
                self.send_header("Cache-Control", "no-store")
                self.send_header("Content-Length", str(len(body)))
                self.end_headers()
                self.wfile.write(body)

            def send_asset(self, raw_name):
                name = unquote(raw_name).replace("\\", "/").split("/")[-1]
                path = (server.static_dir / name).resolve()
                try:
                    path.relative_to(server.static_dir.resolve())
                except ValueError:
                    self.send_error(404)
                    return
                if not path.exists() or not path.is_file():
                    self.send_error(404)
                    return

                body = path.read_bytes()
                content_type = mimetypes.guess_type(path.name)[0] or "application/octet-stream"
                self.send_response(200)
                self.send_header("Content-Type", content_type)
                self.send_header("Cache-Control", "public, max-age=3600")
                self.send_header("Content-Length", str(len(body)))
                self.end_headers()
                self.wfile.write(body)

            def send_paint_preview(self, raw_name):
                name = unquote(raw_name).replace("\\", "/").split("/")[-1]
                path = (server.paint_preview_dir / name).resolve()
                try:
                    path.relative_to(server.paint_preview_dir.resolve())
                except ValueError:
                    self.send_error(404)
                    return
                if not path.exists() or not path.is_file():
                    self.send_error(404)
                    return

                body = path.read_bytes()
                content_type = mimetypes.guess_type(path.name)[0] or "image/png"
                self.send_response(200)
                self.send_header("Content-Type", content_type)
                self.send_header("Cache-Control", "public, max-age=3600")
                self.send_header("Content-Length", str(len(body)))
                self.end_headers()
                self.wfile.write(body)

            def log_message(self, *_):
                return

        return Handler

    @staticmethod
    def default_paint_preview_dir():
        try:
            from production.car_paint_preview import default_preview_cache_dir

            return default_preview_cache_dir()
        except Exception:
            return Path.home() / ".rgc_ai_broadcast_studio" / "paint_previews"


PRODUCER_HTML = r"""<!doctype html>
<html lang="en">
<head>
  <meta charset="utf-8" />
  <meta name="viewport" content="width=device-width, initial-scale=1" />
  <title>RGC Producer Assist</title>
  <style>
    :root {
      --bg: #070a0f;
      --panel: #101722;
      --panel-2: #151e2d;
      --line: rgba(255, 255, 255, 0.13);
      --text: #eef4ff;
      --muted: #9aa8bc;
      --green: #27d17f;
      --yellow: #ffd447;
      --red: #e94b5f;
      --blue: #53a7ff;
    }

    * { box-sizing: border-box; }

    body {
      margin: 0;
      min-height: 100vh;
      font-family: "Segoe UI", Arial, sans-serif;
      color: var(--text);
      background:
        radial-gradient(circle at top left, rgba(83, 167, 255, 0.18), transparent 30%),
        linear-gradient(135deg, #05070b, var(--bg));
    }

    .page {
      padding: 18px;
      display: grid;
      gap: 14px;
    }

    .topbar,
    .card,
    .driver-detail,
    .leaderboard {
      background: rgba(16, 23, 34, 0.92);
      border: 1px solid var(--line);
      border-radius: 16px;
      box-shadow: 0 18px 45px rgba(0, 0, 0, 0.28);
    }

    .topbar {
      padding: 14px 16px;
      display: grid;
      grid-template-columns: 1.4fr 1fr;
      gap: 12px;
      align-items: center;
    }

    h1, h2, h3, p { margin: 0; }

    h1 {
      font-size: 24px;
      letter-spacing: 0.04em;
      text-transform: uppercase;
    }

    .subtitle {
      margin-top: 4px;
      color: var(--muted);
      font-size: 14px;
    }

    .flag {
      justify-self: end;
      padding: 10px 16px;
      border-radius: 999px;
      font-weight: 900;
      letter-spacing: 0.08em;
      color: #05100a;
      background: var(--green);
      text-transform: uppercase;
    }

    .flag.caution {
      color: #211600;
      background: var(--yellow);
      animation: pulse 1s infinite alternate;
    }

    .flag.unknown {
      color: var(--text);
      background: #313c4f;
    }

    .grid {
      display: grid;
      grid-template-columns: repeat(5, minmax(150px, 1fr));
      gap: 12px;
    }

    .card {
      padding: 13px 14px;
      min-height: 82px;
    }

    .label {
      color: var(--muted);
      text-transform: uppercase;
      font-size: 11px;
      letter-spacing: 0.1em;
    }

    .value {
      margin-top: 7px;
      font-size: 24px;
      font-weight: 900;
    }

    .main {
      display: grid;
      grid-template-columns: 1.1fr 0.9fr;
      gap: 14px;
      align-items: start;
    }

    .leaderboard {
      overflow: hidden;
    }

    .section-head {
      padding: 13px 14px;
      border-bottom: 1px solid var(--line);
      display: flex;
      justify-content: space-between;
      gap: 12px;
      align-items: center;
    }

    .section-head h2 {
      font-size: 17px;
      text-transform: uppercase;
      letter-spacing: 0.06em;
    }

    .hint {
      color: var(--muted);
      font-size: 12px;
    }

    .rows {
      max-height: calc(100vh - 295px);
      overflow: auto;
    }

    .driver-row {
      display: grid;
      grid-template-columns: 48px 74px 1fr 64px 92px 110px;
      gap: 10px;
      align-items: center;
      padding: 9px 14px;
      border-bottom: 1px solid rgba(255, 255, 255, 0.07);
      cursor: pointer;
      transition: background 0.12s ease, border-color 0.12s ease;
    }

    .driver-row:hover,
    .driver-row.selected {
      background: rgba(83, 167, 255, 0.14);
    }

    .driver-row.selected {
      border-left: 4px solid var(--blue);
      padding-left: 10px;
    }

    .pos {
      font-weight: 900;
      color: var(--blue);
    }

    .num {
      font-weight: 900;
      color: #fff;
    }

    .name {
      overflow: hidden;
      white-space: nowrap;
      text-overflow: ellipsis;
      font-weight: 700;
    }

    .small {
      color: var(--muted);
      font-size: 12px;
    }

    .driver-detail {
      padding: 16px;
      display: grid;
      gap: 14px;
    }

    .driver-title {
      display: grid;
      grid-template-columns: 90px 1fr;
      gap: 12px;
      align-items: center;
    }

    .big-number {
      height: 72px;
      border-radius: 14px;
      display: grid;
      place-items: center;
      background: linear-gradient(135deg, #1d2d45, #101722);
      border: 1px solid var(--line);
      font-size: 29px;
      font-weight: 950;
    }

    .driver-name {
      font-size: 24px;
      font-weight: 950;
    }

    .detail-grid {
      display: grid;
      grid-template-columns: repeat(2, minmax(0, 1fr));
      gap: 10px;
    }

    .detail-item {
      padding: 10px;
      background: rgba(255, 255, 255, 0.05);
      border: 1px solid rgba(255, 255, 255, 0.08);
      border-radius: 12px;
    }

    .story-box {
      padding: 12px;
      border-radius: 14px;
      border: 1px solid rgba(83, 167, 255, 0.28);
      background: rgba(83, 167, 255, 0.09);
      color: #dcecff;
      line-height: 1.35;
    }

    .button-row {
      display: grid;
      grid-template-columns: repeat(2, minmax(0, 1fr));
      gap: 10px;
    }

    button {
      border: 0;
      border-radius: 12px;
      padding: 11px 12px;
      color: white;
      background: #27496d;
      font-weight: 800;
      cursor: not-allowed;
      opacity: 0.72;
    }

    .control-button {
      cursor: pointer;
      opacity: 1;
      background: #294b73;
    }

    .control-button.danger { background: #8f2e37; }
    .control-button.good { background: #1f7550; }
    .control-button.warn { background: #8b6a1c; }

    .panel {
      padding: 12px;
      background: rgba(255, 255, 255, 0.045);
      border: 1px solid rgba(255, 255, 255, 0.08);
      border-radius: 14px;
    }

    .panel h3 {
      margin-bottom: 6px;
      color: #fff;
      font-size: 14px;
      text-transform: uppercase;
      letter-spacing: 0.06em;
    }

    .feed {
      display: grid;
      gap: 8px;
      max-height: 300px;
      overflow: auto;
    }

    .feed-item {
      padding: 9px 10px;
      border-radius: 10px;
      background: rgba(255, 255, 255, 0.045);
      border-left: 4px solid #56657a;
    }

    .feed-item.broadcast { border-left-color: var(--green); }
    .feed-item.camera { border-left-color: var(--blue); }
    .feed-item.replay { border-left-color: var(--yellow); }
    .feed-item.warning { border-left-color: var(--red); }

    .feed-title {
      font-size: 12px;
      font-weight: 900;
      text-transform: uppercase;
      letter-spacing: 0.06em;
      color: #fff;
    }

    .feed-message {
      margin-top: 3px;
      color: #dbe5f4;
      line-height: 1.3;
    }

    @keyframes pulse {
      from { filter: brightness(1); }
      to { filter: brightness(1.28); }
    }

    @media (max-width: 1050px) {
      .grid { grid-template-columns: repeat(2, minmax(150px, 1fr)); }
      .main { grid-template-columns: 1fr; }
      .rows { max-height: none; }
    }
  </style>
</head>
<body>
  <div class="page">
    <header class="topbar">
      <div>
        <h1>RGC Producer Assist</h1>
        <p class="subtitle" id="event-line">Waiting for broadcast state...</p>
      </div>
      <div class="flag unknown" id="flag-pill">Waiting</div>
    </header>

    <section class="grid">
      <div class="card"><div class="label">Session</div><div class="value" id="session-value">--</div></div>
      <div class="card"><div class="label">Race Lap</div><div class="value" id="lap-value">--</div></div>
      <div class="card"><div class="label">Cautions</div><div class="value" id="cautions-value">--</div></div>
      <div class="card"><div class="label">Last Caution</div><div class="value" id="last-caution-value">--</div></div>
      <div class="card"><div class="label">Green / Yellow Laps</div><div class="value" id="lap-mix-value">--</div></div>
    </section>

    <main class="main">
      <section class="leaderboard">
        <div class="section-head">
          <h2>Live Leaderboard</h2>
          <span class="hint">Click a driver for notes</span>
        </div>
        <div class="rows" id="leaderboard-rows"></div>
      </section>

      <aside class="driver-detail">
        <div class="driver-title">
          <div class="big-number" id="detail-number">--</div>
          <div>
            <div class="driver-name" id="detail-name">Select a driver</div>
            <div class="small" id="detail-subtitle">Live race information will show here.</div>
          </div>
        </div>

        <div class="detail-grid">
          <div class="detail-item"><div class="label">Position</div><div class="value" id="detail-position">--</div></div>
          <div class="detail-item"><div class="label">Started</div><div class="value" id="detail-start">--</div></div>
          <div class="detail-item"><div class="label">Spots +/-</div><div class="value" id="detail-delta">--</div></div>
          <div class="detail-item"><div class="label">Interval</div><div class="value" id="detail-interval">--</div></div>
          <div class="detail-item"><div class="label">Laps Complete</div><div class="value" id="detail-laps">--</div></div>
          <div class="detail-item"><div class="label">Laps Led</div><div class="value" id="detail-led">--</div></div>
          <div class="detail-item"><div class="label">Incidents</div><div class="value" id="detail-incidents">--</div></div>
          <div class="detail-item"><div class="label">Fastest Lap</div><div class="value" id="detail-fastest">--</div></div>
          <div class="detail-item"><div class="label">Last Pit</div><div class="value" id="detail-last-pit">--</div></div>
          <div class="detail-item"><div class="label">Pit Time</div><div class="value" id="detail-pit-time">--</div></div>
        </div>

        <div class="story-box" id="story-box">
          Producer note: pick a driver from the leaderboard. This panel is built to become the broadcaster control room.
        </div>

        <div class="button-row">
          <button class="control-button" id="follow-driver-button">Move Camera to Driver</button>
          <button class="control-button" id="leader-camera-button">Back to Leader</button>
        </div>

        <div class="panel">
          <h3>Control Room Toggles</h3>
          <div class="button-row">
            <button class="control-button" id="auto-camera-button">Auto Camera</button>
            <button class="control-button" id="openai-button">OpenAI</button>
            <button class="control-button" id="elevenlabs-button">ElevenLabs</button>
            <button class="control-button" id="return-live-button">Return Live</button>
            <button class="control-button warn" id="pause-replay-button">Pause Replay</button>
            <button class="control-button warn" id="play-replay-button">Play Replay</button>
            <button class="control-button warn" id="rewind-button">Rewind 10 sec</button>
            <button class="control-button warn" id="fast-forward-button">Forward 10 sec</button>
          </div>
        </div>

        <div class="panel" id="featured-panel">
          <h3>Current Broadcast Focus</h3>
          <div class="small">No featured driver on the overlay right now.</div>
        </div>

        <div class="panel" id="stat-panel">
          <h3>Active Graphic / Stat Panel</h3>
          <div class="small">No stat panel is active.</div>
        </div>

        <div class="panel">
          <h3>Producer Feed</h3>
          <div class="feed" id="producer-feed">
            <div class="small">Broadcast notes will appear here once the session starts.</div>
          </div>
        </div>
      </aside>
    </main>
  </div>

  <script>
    let selectedCarIdx = null;
    let lastState = null;

    function text(id, value) {
      document.getElementById(id).textContent = value;
    }

    function ordinal(n) {
      const value = Number(n);
      if (!Number.isFinite(value) || value <= 0) return "--";
      const mod10 = value % 10;
      const mod100 = value % 100;
      if (mod10 === 1 && mod100 !== 11) return `${value}st`;
      if (mod10 === 2 && mod100 !== 12) return `${value}nd`;
      if (mod10 === 3 && mod100 !== 13) return `${value}rd`;
      return `${value}th`;
    }

    function formatLap(state) {
      const lap = Number(state.lap || 0);
      const total = Number(state.total_laps || 0);
      if (total > 0) return `${lap} / ${total}`;
      return lap > 0 ? String(lap) : "--";
    }

    function formatDelta(value) {
      const number = Number(value || 0);
      if (!Number.isFinite(number) || number === 0) return "--";
      return number > 0 ? `+${number}` : String(number);
    }

    function formatSeconds(value) {
      const number = Number(value || 0);
      if (!Number.isFinite(number) || number <= 0) return "--";
      return `${number.toFixed(1)}s`;
    }

    function formatPit(driver) {
      const lap = Number(driver.last_pit_lap || 0);
      if (driver.on_pit_road) return "On pit road";
      return lap > 0 ? `Lap ${lap}` : "--";
    }

    function lapHistorySummary(history) {
      let cautionSegments = 0;
      let lastCautionLap = "";
      let greenLaps = 0;
      let cautionLaps = 0;
      let previous = "";
      for (const lap of history || []) {
        if (lap.status === "caution") {
          cautionLaps += 1;
          lastCautionLap = lap.lap;
          if (previous !== "caution") cautionSegments += 1;
        }
        if (lap.status === "green") greenLaps += 1;
        previous = lap.status;
      }
      return { cautionSegments, lastCautionLap, greenLaps, cautionLaps };
    }

    function renderHeader(state) {
      const event = state.event || {};
      text("event-line", `${event.title || "Untitled Event"} • ${state.track_name || "Unknown Track"}${event.sponsor ? " • " + event.sponsor : ""}`);
      text("session-value", state.session_type || "Unknown");
      text("lap-value", formatLap(state));

      const flag = document.getElementById("flag-pill");
      flag.className = "flag";
      if (state.caution) {
        flag.classList.add("caution");
        flag.textContent = "Caution";
      } else if (state.green) {
        flag.textContent = "Green";
      } else {
        flag.classList.add("unknown");
        flag.textContent = "Waiting";
      }

      const summary = lapHistorySummary(state.lap_history);
      text("cautions-value", summary.cautionSegments || "0");
      text("last-caution-value", summary.lastCautionLap ? `Lap ${summary.lastCautionLap}` : "--");
      text("lap-mix-value", `${summary.greenLaps} / ${summary.cautionLaps}`);
    }

    function driverKey(driver) {
      return String(driver.car_idx ?? `${driver.position}:${driver.car_number}:${driver.driver_name}`);
    }

    function renderLeaderboard(state) {
      const rows = document.getElementById("leaderboard-rows");
      const leaderboard = state.leaderboard || [];
      if (!leaderboard.length) {
        rows.innerHTML = '<div class="driver-row"><div class="small">No leaderboard data yet.</div></div>';
        return;
      }
      if (selectedCarIdx === null || !leaderboard.some(driver => driverKey(driver) === selectedCarIdx)) {
        selectedCarIdx = driverKey(leaderboard[0]);
      }
      rows.innerHTML = "";
      for (const driver of leaderboard) {
        const key = driverKey(driver);
        const row = document.createElement("div");
        row.className = `driver-row${key === selectedCarIdx ? " selected" : ""}`;
        row.innerHTML = `
          <div class="pos">${ordinal(driver.position)}</div>
          <div class="num">#${driver.car_number || "--"}</div>
          <div class="name">${driver.driver_name || "Unknown Driver"}</div>
          <div class="small">${formatDelta(driver.position_delta)}</div>
          <div class="small">${driver.interval || "--"}</div>
          <div class="small">${driver.fastest_lap || "--"}</div>
        `;
        row.addEventListener("click", () => {
          selectedCarIdx = key;
          renderAll(lastState);
        });
        rows.appendChild(row);
      }
    }

    function selectedDriver(state) {
      const leaderboard = state.leaderboard || [];
      return leaderboard.find(driver => driverKey(driver) === selectedCarIdx) || leaderboard[0] || null;
    }

    function renderDriverDetail(state) {
      const driver = selectedDriver(state);
      if (!driver) return;
      text("detail-number", `#${driver.car_number || "--"}`);
      text("detail-name", driver.driver_name || "Unknown Driver");
      text("detail-subtitle", `${state.session_type || "Session"} at ${state.track_name || "the track"}`);
      text("detail-position", ordinal(driver.position));
      text("detail-start", driver.starting_position ? ordinal(driver.starting_position) : "--");
      text("detail-delta", formatDelta(driver.position_delta));
      text("detail-interval", driver.interval || "--");
      text("detail-laps", driver.laps_complete ?? "--");
      text("detail-led", driver.laps_led || "--");
      text("detail-incidents", driver.incidents || "--");
      text("detail-fastest", driver.fastest_lap || "--");
      text("detail-last-pit", formatPit(driver));
      const pitStop = formatSeconds(driver.last_pit_stop_seconds);
      const laneTime = formatSeconds(driver.last_pit_lane_seconds);
      text("detail-pit-time", pitStop !== "--" || laneTime !== "--" ? `${pitStop} / ${laneTime}` : "--");

      const lap = formatLap(state);
      const note = [
        driver.producer_note || `${driver.driver_name || "This driver"} is currently ${ordinal(driver.position)} in the running order.`,
        driver.starting_position ? `Started ${ordinal(driver.starting_position)}; ${formatDelta(driver.position_delta)} spots.` : "",
        driver.laps_led ? `Laps led: ${driver.laps_led}.` : "",
        driver.interval ? `Interval shown: ${driver.interval}.` : "",
        driver.fastest_lap ? `Fastest lap: ${driver.fastest_lap}.` : "",
        `Race status: ${state.caution ? "under caution" : state.green ? "green flag" : "not green yet"} on lap ${lap}.`
      ].filter(Boolean).join(" ");
      text("story-box", note);
    }

    function renderFeatured(state) {
      const panel = document.getElementById("featured-panel");
      const featured = state.featured_driver;
      if (!featured) {
        panel.innerHTML = '<h3>Current Broadcast Focus</h3><div class="small">No featured driver on the overlay right now.</div>';
        return;
      }
      panel.innerHTML = `
        <h3>Current Broadcast Focus</h3>
        <div><strong>#${featured.car_number || "--"} ${featured.driver_name || ""}</strong></div>
        <div class="small">${featured.story || "Camera/driver graphic is active."}</div>
      `;
    }

    function renderStatPanel(state) {
      const panel = document.getElementById("stat-panel");
      const stat = state.stat_panel;
      if (!stat) {
        panel.innerHTML = '<h3>Active Graphic / Stat Panel</h3><div class="small">No stat panel is active.</div>';
        return;
      }
      const rows = (stat.rows || []).map(row =>
        `<div class="small"><strong>${row.label || ""}</strong> ${row.value || ""} ${row.detail || ""}</div>`
      ).join("");
      panel.innerHTML = `
        <h3>${stat.title || "Active Stat Panel"}</h3>
        <div class="small">${stat.subtitle || ""}</div>
        ${rows}
      `;
    }

    function controlEnabled(state, key) {
      return Boolean((state.control_state || {})[key]);
    }

    function renderControlButtons(state) {
      const autoButton = document.getElementById("auto-camera-button");
      const openAiButton = document.getElementById("openai-button");
      const elevenButton = document.getElementById("elevenlabs-button");
      const autoOn = controlEnabled(state, "auto_camera");
      const openAiOn = controlEnabled(state, "openai");
      const elevenOn = controlEnabled(state, "elevenlabs");
      autoButton.textContent = autoOn ? "Auto Camera: ON" : "Auto Camera: OFF";
      openAiButton.textContent = openAiOn ? "OpenAI: ON" : "OpenAI: OFF";
      elevenButton.textContent = elevenOn ? "ElevenLabs: ON" : "ElevenLabs: OFF";
      autoButton.className = `control-button ${autoOn ? "good" : "danger"}`;
      openAiButton.className = `control-button ${openAiOn ? "good" : "danger"}`;
      elevenButton.className = `control-button ${elevenOn ? "good" : "danger"}`;
    }

    async function sendProducerCommand(command, payload = {}) {
      try {
        await fetch("/producer/command", {
          method: "POST",
          headers: { "Content-Type": "application/json" },
          body: JSON.stringify({ command, payload })
        });
      } catch (error) {
        console.warn("Producer command failed", command, error);
      }
    }

    function renderProducerFeed(state) {
      const feed = document.getElementById("producer-feed");
      const items = state.producer_feed || [];
      feed.innerHTML = "";
      if (!items.length) {
        feed.innerHTML = '<div class="small">Broadcast notes will appear here once the session starts.</div>';
        return;
      }
      for (const item of items.slice(0, 30)) {
        const node = document.createElement("div");
        node.className = `feed-item ${item.kind || "info"}`;
        const title = document.createElement("div");
        title.className = "feed-title";
        const speaker = item.speaker ? ` • ${String(item.speaker).toUpperCase()}` : "";
        title.textContent = `${item.title || item.kind || "Producer"}${speaker}`;
        const message = document.createElement("div");
        message.className = "feed-message";
        message.textContent = item.message || "";
        node.appendChild(title);
        node.appendChild(message);
        feed.appendChild(node);
      }
    }

    function renderAll(state) {
      if (!state) return;
      lastState = state;
      renderHeader(state);
      renderLeaderboard(state);
      renderDriverDetail(state);
      renderFeatured(state);
      renderStatPanel(state);
      renderProducerFeed(state);
      renderControlButtons(state);
    }

    document.getElementById("follow-driver-button").addEventListener("click", () => {
      const driver = selectedDriver(lastState || {});
      if (!driver) return;
      sendProducerCommand("camera_follow_driver", {
        car_idx: driver.car_idx,
        group_name: "TV1"
      });
    });
    document.getElementById("leader-camera-button").addEventListener("click", () => {
      sendProducerCommand("camera_follow_leader");
    });
    document.getElementById("auto-camera-button").addEventListener("click", () => {
      const on = controlEnabled(lastState || {}, "auto_camera");
      sendProducerCommand(on ? "auto_camera_off" : "auto_camera_on");
    });
    document.getElementById("openai-button").addEventListener("click", () => {
      const on = controlEnabled(lastState || {}, "openai");
      sendProducerCommand(on ? "openai_off" : "openai_on");
    });
    document.getElementById("elevenlabs-button").addEventListener("click", () => {
      const on = controlEnabled(lastState || {}, "elevenlabs");
      sendProducerCommand(on ? "elevenlabs_off" : "elevenlabs_on");
    });
    document.getElementById("return-live-button").addEventListener("click", () => {
      sendProducerCommand("replay_return_live");
    });
    document.getElementById("pause-replay-button").addEventListener("click", () => {
      sendProducerCommand("replay_pause");
    });
    document.getElementById("play-replay-button").addEventListener("click", () => {
      sendProducerCommand("replay_play");
    });
    document.getElementById("rewind-button").addEventListener("click", () => {
      sendProducerCommand("replay_rewind", { seconds: 10 });
    });
    document.getElementById("fast-forward-button").addEventListener("click", () => {
      sendProducerCommand("replay_fast_forward", { seconds: 10 });
    });

    async function refreshProducerAssist() {
      try {
        const response = await fetch("/overlay/state", { cache: "no-store" });
        renderAll(await response.json());
      } catch (error) {
        text("event-line", "Waiting for the broadcast overlay server...");
        document.getElementById("flag-pill").className = "flag unknown";
        document.getElementById("flag-pill").textContent = "Offline";
        console.warn("Producer Assist update failed", error);
      }
    }

    refreshProducerAssist();
    setInterval(refreshProducerAssist, 1000);
  </script>
</body>
</html>
"""


OVERLAY_HTML = r"""<!doctype html>
<html lang="en">
<head>
  <meta charset="utf-8" />
  <meta name="viewport" content="width=device-width, initial-scale=1" />
  <title>RGC AI Broadcast Overlay</title>
  <style>
    :root {
      --rgc-red: #d71920;
      --rgc-dark: rgba(8, 10, 14, 0.88);
      --rgc-panel: rgba(16, 20, 28, 0.90);
      --rgc-line: rgba(255, 255, 255, 0.22);
      --rgc-text: #f5f7fb;
      --rgc-muted: #aeb6c5;
    }

    html, body {
      width: 100%;
      height: 100%;
      margin: 0;
      overflow: hidden;
      background: transparent;
      color: var(--rgc-text);
      font-family: "Segoe UI", Arial, sans-serif;
    }

    .top-banner {
      position: absolute;
      left: 24px;
      right: 24px;
      top: 24px;
      min-width: 0;
      max-width: none;
      height: 76px;
      display: flex;
      align-items: center;
      justify-content: space-between;
      gap: 26px;
      padding: 0 26px;
      background: linear-gradient(90deg, rgba(7, 9, 13, 0.96), rgba(24, 30, 42, 0.92));
      border-bottom: 4px solid var(--rgc-red);
      box-shadow: 0 14px 34px rgba(0, 0, 0, 0.42);
      letter-spacing: 0.02em;
    }

    .session-center {
      position: absolute;
      left: 50%;
      top: 50%;
      transform: translate(-50%, -50%);
      min-width: 300px;
      padding: 8px 22px;
      border-radius: 999px;
      background: linear-gradient(90deg, rgba(215, 25, 32, 0.92), rgba(7, 9, 13, 0.88));
      border: 1px solid rgba(255, 255, 255, 0.26);
      box-shadow: 0 0 22px rgba(215, 25, 32, 0.34);
      color: #ffffff;
      text-align: center;
      font-size: 22px;
      font-weight: 950;
      text-transform: uppercase;
      letter-spacing: 0.08em;
      white-space: nowrap;
    }

    .top-banner.caution {
      border: 4px solid #ffd400;
      border-bottom-width: 5px;
      animation: cautionPulse 0.85s infinite alternate;
    }

    @keyframes cautionPulse {
      from { box-shadow: 0 0 16px rgba(255, 212, 0, 0.55); }
      to { box-shadow: 0 0 38px rgba(255, 212, 0, 0.98); }
    }

    .event-title {
      font-size: 28px;
      font-weight: 800;
      text-transform: uppercase;
      white-space: nowrap;
    }

    .title-side {
      display: flex;
      align-items: center;
      gap: 18px;
      min-width: 0;
    }

    .brand-graphic {
      max-width: 170px;
      max-height: 56px;
      object-fit: contain;
      filter: drop-shadow(0 7px 12px rgba(0, 0, 0, 0.55));
      opacity: 0.94;
    }

    .event-meta {
      display: flex;
      flex-direction: column;
      align-items: flex-end;
      font-size: 14px;
      color: var(--rgc-muted);
      text-transform: uppercase;
      line-height: 1.35;
      white-space: nowrap;
    }

    .sponsor {
      color: #fff;
      font-weight: 700;
    }

    .leaderboard {
      position: absolute;
      left: 24px;
      top: 124px;
      width: 264px;
      background: var(--rgc-panel);
      box-shadow: 0 14px 34px rgba(0, 0, 0, 0.40);
      border-left: 5px solid var(--rgc-red);
    }

    .leaderboard-header {
      display: grid;
      grid-template-columns: 1fr auto;
      gap: 8px;
      padding: 8px 10px;
      background: var(--rgc-dark);
      border-bottom: 4px solid var(--rgc-line);
      text-transform: uppercase;
      font-weight: 800;
    }

    .leaderboard.green .leaderboard-header {
      background: linear-gradient(90deg, rgba(21, 200, 95, 0.38), var(--rgc-dark) 72%);
      border-bottom-color: #15c85f;
      box-shadow: inset 0 -10px 18px rgba(21, 200, 95, 0.24), 0 0 18px rgba(21, 200, 95, 0.16);
    }

    .leaderboard.green {
      border-left-color: #15c85f;
    }

    .leaderboard.caution .leaderboard-header {
      border-bottom-color: #ffd400;
      box-shadow: inset 0 -10px 18px rgba(255, 212, 0, 0.22);
    }

    .leaderboard.caution {
      border-left-color: #ffd400;
    }

    .lap {
      color: var(--rgc-muted);
      font-size: 13px;
      align-self: center;
    }

    .row {
      display: grid;
      grid-template-columns: 30px 40px 1fr auto;
      gap: 6px;
      align-items: center;
      min-height: 25px;
      padding: 3px 8px;
      border-bottom: 1px solid rgba(255, 255, 255, 0.08);
      font-size: 12px;
    }

    .row:nth-child(even) {
      background: rgba(255, 255, 255, 0.035);
    }

    .row.cycle-divider {
      border-bottom: 3px solid rgba(215, 25, 32, 0.86);
      box-shadow: 0 3px 0 rgba(0, 0, 0, 0.28);
    }

    .lap-history {
      display: flex;
      gap: 2px;
      padding: 7px 8px 8px;
      background: rgba(0, 0, 0, 0.28);
      border-bottom: 1px solid rgba(255, 255, 255, 0.08);
    }

    .lap-history-segment {
      height: 8px;
      flex: 1 1 0;
      min-width: 2px;
      border-radius: 3px;
      background: rgba(255, 255, 255, 0.18);
    }

    .lap-history-segment.green {
      background: #15c85f;
      box-shadow: 0 0 6px rgba(21, 200, 95, 0.36);
    }

    .lap-history-segment.caution {
      background: #ffd400;
      box-shadow: 0 0 6px rgba(255, 212, 0, 0.42);
    }

    .lap-history-segment.pending {
      opacity: 0.35;
    }

    .pos {
      color: #fff;
      font-weight: 900;
      font-size: 14px;
    }

    .num {
      background: #fff;
      color: #111;
      border-radius: 3px;
      text-align: center;
      font-weight: 900;
      padding: 2px 5px;
    }

    .name {
      overflow: hidden;
      text-overflow: ellipsis;
      white-space: nowrap;
      font-weight: 650;
    }

    .gap {
      color: var(--rgc-muted);
      font-size: 12px;
    }

    .driver-card {
      position: absolute;
      left: 360px;
      bottom: 54px;
      min-width: 430px;
      max-width: 760px;
      display: grid;
      grid-template-columns: 86px minmax(0, 160px) 1fr;
      background: linear-gradient(90deg, rgba(7, 9, 13, 0.96), rgba(24, 30, 42, 0.92));
      border-left: 6px solid var(--rgc-red);
      box-shadow: 0 14px 34px rgba(0, 0, 0, 0.42);
      text-transform: uppercase;
    }

    .driver-card.no-image {
      grid-template-columns: 86px 1fr;
    }

    .driver-card-number {
      display: flex;
      align-items: center;
      justify-content: center;
      background: #fff;
      color: #111;
      font-weight: 950;
      font-size: 36px;
    }

    .driver-card-image {
      min-height: 74px;
      background-size: cover;
      background-position: center;
      border-left: 1px solid rgba(0, 0, 0, 0.32);
      border-right: 1px solid rgba(255, 255, 255, 0.12);
    }

    .driver-card-info {
      padding: 12px 18px;
    }

    .driver-card-name {
      font-size: 26px;
      font-weight: 900;
      white-space: nowrap;
      overflow: hidden;
      text-overflow: ellipsis;
    }

    .driver-card-story {
      margin-top: 4px;
      color: var(--rgc-muted);
      font-size: 13px;
      font-weight: 700;
      white-space: nowrap;
      overflow: hidden;
      text-overflow: ellipsis;
    }

    .stat-panel {
      position: absolute;
      right: 34px;
      bottom: 54px;
      width: 390px;
      background: linear-gradient(90deg, rgba(7, 9, 13, 0.96), rgba(24, 30, 42, 0.94));
      border-left: 6px solid var(--rgc-red);
      box-shadow: 0 14px 34px rgba(0, 0, 0, 0.42);
      text-transform: uppercase;
      overflow: hidden;
    }

    .stat-panel.biggest_movers {
      border-left-color: #15c85f;
    }

    .stat-panel.pit_update {
      border-left-color: #ffd400;
    }

    .stat-panel-header {
      padding: 12px 16px 10px;
      background: rgba(0, 0, 0, 0.32);
      border-bottom: 1px solid rgba(255, 255, 255, 0.14);
    }

    .stat-panel-title {
      font-size: 24px;
      font-weight: 950;
      letter-spacing: 0.04em;
    }

    .stat-panel-subtitle {
      margin-top: 3px;
      color: var(--rgc-muted);
      font-size: 12px;
      font-weight: 750;
    }

    .stat-panel-row {
      display: grid;
      grid-template-columns: 1fr auto;
      gap: 12px;
      padding: 9px 14px;
      border-bottom: 1px solid rgba(255, 255, 255, 0.08);
    }

    .stat-panel-label {
      min-width: 0;
      overflow: hidden;
      text-overflow: ellipsis;
      white-space: nowrap;
      font-size: 14px;
      font-weight: 850;
    }

    .stat-panel-value {
      color: #fff;
      font-size: 18px;
      font-weight: 950;
    }

    .stat-panel-detail {
      grid-column: 1 / -1;
      color: var(--rgc-muted);
      font-size: 11px;
      font-weight: 700;
      white-space: nowrap;
      overflow: hidden;
      text-overflow: ellipsis;
    }

    .hidden {
      display: none;
    }

    .special-presentation {
      position: absolute;
      left: 324px;
      right: 24px;
      top: 112px;
      height: 170px;
      display: flex;
      align-items: center;
      justify-content: center;
      z-index: 20;
      text-transform: uppercase;
      pointer-events: none;
    }

    .special-presentation.race_sponsors {
      left: 390px;
      right: 150px;
      top: 116px;
      height: 112px;
    }

    .special-presentation.sponsor_bug {
      left: auto;
      right: 52px;
      top: 160px;
      width: 360px;
      height: 104px;
      justify-content: flex-end;
      animation: sponsorBugPop 0.22s ease-out;
    }

    .special-presentation.hidden {
      display: none;
    }

    .ceremony-card {
      display: grid;
      grid-template-columns: 220px 1fr;
      align-items: center;
      gap: 32px;
      width: min(850px, 100%);
      padding: 18px 28px;
      background: linear-gradient(90deg, rgba(7, 9, 13, 0.94), rgba(24, 30, 42, 0.88));
      border: 1px solid rgba(255, 255, 255, 0.24);
      border-left: 6px solid var(--rgc-red);
      box-shadow: 0 18px 42px rgba(0, 0, 0, 0.48);
    }

    .special-presentation.race_sponsors .ceremony-card {
      grid-template-columns: 150px 1fr;
      gap: 22px;
      width: min(660px, 100%);
      padding: 12px 20px;
      border-left-width: 4px;
      background: linear-gradient(90deg, rgba(7, 9, 13, 0.88), rgba(24, 30, 42, 0.78));
    }

    .special-presentation.sponsor_bug .ceremony-card {
      grid-template-columns: 118px 1fr;
      gap: 14px;
      width: 360px;
      padding: 10px 14px;
      border-left-width: 4px;
      background: linear-gradient(90deg, rgba(7, 9, 13, 0.92), rgba(24, 30, 42, 0.82));
    }

    .ceremony-logo {
      width: 210px;
      height: 116px;
      object-fit: contain;
      filter: drop-shadow(0 10px 18px rgba(0, 0, 0, 0.62));
    }

    .special-presentation.race_sponsors .ceremony-logo {
      width: 145px;
      height: 74px;
    }

    .special-presentation.sponsor_bug .ceremony-logo {
      width: 112px;
      height: 62px;
    }

    .ceremony-title {
      font-size: 40px;
      font-weight: 950;
      letter-spacing: 0.05em;
    }

    .special-presentation.race_sponsors .ceremony-title {
      font-size: 26px;
      letter-spacing: 0.04em;
    }

    .special-presentation.sponsor_bug .ceremony-title {
      font-size: 18px;
      letter-spacing: 0.035em;
    }

    .ceremony-subtitle {
      margin-top: 14px;
      color: var(--rgc-muted);
      font-size: 18px;
      font-weight: 800;
      letter-spacing: 0.08em;
    }

    .special-presentation.race_sponsors .ceremony-subtitle {
      margin-top: 7px;
      font-size: 13px;
      letter-spacing: 0.06em;
    }

    .special-presentation.sponsor_bug .ceremony-subtitle {
      margin-top: 4px;
      font-size: 11px;
      letter-spacing: 0.05em;
    }

    @keyframes sponsorBugPop {
      from {
        opacity: 0;
        transform: translateX(18px) scale(0.96);
      }
      to {
        opacity: 1;
        transform: translateX(0) scale(1);
      }
    }

    .special-presentation.crank_it_up {
      left: 0;
      right: 0;
      top: auto;
      bottom: 24px;
      height: 124px;
      justify-content: center;
      gap: 0;
    }

    .crank-speaker {
      display: none;
      flex: none;
      width: 190px;
      height: 112px;
      background-repeat: no-repeat;
      background-position: center;
      background-size: contain;
      animation: crankSidePulse 0.58s infinite alternate ease-in-out;
      position: absolute;
      top: 6px;
      overflow: visible;
      filter:
        drop-shadow(0 0 18px rgba(255, 192, 0, 0.42))
        drop-shadow(0 0 28px rgba(215, 25, 32, 0.55));
    }

    .crank-speaker-left {
      left: 34px;
      --speaker-tilt: -2.5deg;
    }

    .crank-speaker-right {
      right: 34px;
      --speaker-tilt: 2.5deg;
    }

    .special-presentation.crank_it_up .crank-speaker {
      display: block;
    }

    .special-presentation.crank_it_up .ceremony-card {
      display: block;
      width: min(620px, 48vw);
      min-width: 500px;
      padding: 8px 34px 10px;
      text-align: center;
      border-left: 0;
      border-bottom: 5px solid var(--rgc-red);
      background:
        linear-gradient(90deg, rgba(7, 9, 13, 0.78), rgba(36, 12, 18, 0.82), rgba(7, 9, 13, 0.78)),
        repeating-linear-gradient(135deg, rgba(255,255,255,0.12) 0 8px, transparent 8px 16px);
      box-shadow:
        0 0 34px rgba(215, 25, 32, 0.42),
        0 0 62px rgba(255, 192, 0, 0.18);
    }

    .special-presentation.crank_it_up .ceremony-logo {
      display: block;
      width: min(460px, 100%);
      height: 66px;
      margin: 0 auto;
      object-fit: contain;
      filter:
        drop-shadow(0 0 12px rgba(255, 255, 255, 0.22))
        drop-shadow(0 0 24px rgba(215, 25, 32, 0.40));
    }

    .special-presentation.crank_it_up .ceremony-title {
      font-size: 18px;
      letter-spacing: 0.08em;
      text-shadow: 0 0 22px rgba(255, 255, 255, 0.28);
    }

    .special-presentation.crank_it_up .ceremony-subtitle {
      color: #ffffff;
      opacity: 0.82;
      margin-top: 2px;
      font-size: 12px;
    }

    @keyframes crankSidePulse {
      0% {
        transform: translateX(-3px) rotate(var(--speaker-tilt, 0deg)) scale(0.96);
      }
      35% {
        transform: translateX(2px) rotate(0.8deg) scale(1.02);
      }
      70% {
        transform: translateX(-1px) rotate(var(--speaker-tilt, 0deg)) scale(1.05);
      }
      100% {
        transform: translateX(2px) rotate(-0.8deg) scale(1.08);
      }
    }

    @keyframes speakerPulse {
      from {
        transform: rotate(var(--speaker-tilt, 0deg)) scale(0.98);
        filter: brightness(0.9);
      }
      to {
        transform: rotate(var(--speaker-tilt, 0deg)) scale(1.04);
        filter: brightness(1.2);
      }
    }
  </style>
</head>
<body>
  <section id="top-banner" class="top-banner">
    <div class="title-side">
      <img id="brand-graphic" class="brand-graphic hidden" alt="" />
      <div>
        <div id="event-title" class="event-title">RGC AI Broadcast</div>
        <div id="series" class="event-meta"></div>
      </div>
    </div>
    <div class="event-meta">
      <span id="track">Waiting for iRacing</span>
      <span id="sponsor" class="sponsor"></span>
    </div>
    <div id="session-center" class="session-center hidden"></div>
  </section>

  <section id="leaderboard" class="leaderboard">
    <div class="leaderboard-header">
      <span>Leaderboard</span>
      <span id="lap" class="lap">Lap --</span>
    </div>
    <div id="lap-history" class="lap-history hidden"></div>
    <div id="leaderboard-rows"></div>
  </section>

  <section id="driver-card" class="driver-card hidden">
    <div id="driver-card-number" class="driver-card-number"></div>
    <div id="driver-card-image" class="driver-card-image hidden"></div>
    <div class="driver-card-info">
      <div id="driver-card-name" class="driver-card-name"></div>
      <div id="driver-card-story" class="driver-card-story"></div>
    </div>
  </section>

  <section id="stat-panel" class="stat-panel hidden">
    <div class="stat-panel-header">
      <div id="stat-panel-title" class="stat-panel-title"></div>
      <div id="stat-panel-subtitle" class="stat-panel-subtitle"></div>
    </div>
    <div id="stat-panel-rows"></div>
  </section>

  <section id="special-presentation" class="special-presentation hidden">
    <div class="crank-speaker crank-speaker-left"></div>
    <div class="ceremony-card">
      <img id="ceremony-logo" class="ceremony-logo" alt="" />
      <div>
        <div id="ceremony-title" class="ceremony-title">RGC Anthem</div>
        <div id="ceremony-subtitle" class="ceremony-subtitle">Presented by RGC Motorsports</div>
      </div>
    </div>
    <div class="crank-speaker crank-speaker-right"></div>
  </section>

  <script>
    async function refreshOverlay() {
      try {
        const response = await fetch("/overlay/state", { cache: "no-store" });
        const state = await response.json();
        renderOverlay(state);
      } catch (error) {
        console.warn("Overlay update failed", error);
      }
    }

    function renderOverlay(state) {
      const event = state.event || {};
      setText("event-title", event.title || "RGC AI Broadcast");
      setText("series", event.series || "");
      setText("track", buildTrackLine(state));
      setText("sponsor", event.sponsor ? `Presented by ${event.sponsor}` : "");
      setText("lap", buildLapLine(state));
      setText("session-center", buildSessionCenterLine(state));
      document.getElementById("top-banner").classList.toggle("caution", !!state.caution);
      document.getElementById("leaderboard").classList.toggle("green", !!state.green);
      document.getElementById("leaderboard").classList.toggle("caution", !!state.caution);
      renderBrandGraphic(event.graphics || [], state.session_type);
      renderLapHistory(state.lap_history || []);
      renderDriverCard(state.featured_driver);
      renderSpecialPresentation(state.special_presentation);
      renderStatPanel(state.stat_panel);

      const rows = document.getElementById("leaderboard-rows");
      rows.innerHTML = "";
      for (const [index, entry] of (state.leaderboard || []).slice(0, 20).entries()) {
        const row = document.createElement("div");
        row.className = "row";
        if (index === 14) row.classList.add("cycle-divider");
        row.innerHTML = `
          <span class="pos">${entry.position}</span>
          <span class="num">${escapeHtml(entry.car_number || "?")}</span>
          <span class="name">${escapeHtml(entry.driver_name || "Unknown")}</span>
          <span class="gap">${escapeHtml(entry.interval || "")}</span>
        `;
        rows.appendChild(row);
      }
    }

    function renderSpecialPresentation(presentation) {
      const layer = document.getElementById("special-presentation");
      const active = !!(presentation && presentation.kind);
      layer.classList.toggle("hidden", !active);
      layer.classList.toggle("crank_it_up", active && presentation.kind === "crank_it_up");
      layer.classList.toggle("race_sponsors", active && presentation.kind === "race_sponsors");
      layer.classList.toggle("sponsor_bug", active && presentation.kind === "sponsor_bug");
      if (!active) {
        setCrankSideGraphic("crank-speaker-left", "");
        setCrankSideGraphic("crank-speaker-right", "");
        return;
      }
      setText("ceremony-title", presentation.title || "Please Rise");
      setText("ceremony-subtitle", presentation.subtitle || "Presented by RGC Motorsports");
      const logo = document.getElementById("ceremony-logo");
      const graphics = presentation.graphics || [];
      const isCrank = presentation.kind === "crank_it_up";
      const src = isCrank ? String(graphics[0] || "") : pickRotatingGraphic(graphics, 3.5);
      const sideSrc = isCrank ? (graphics[1] || graphics[0] || "") : "";
      setCrankSideGraphic("crank-speaker-left", sideSrc);
      setCrankSideGraphic("crank-speaker-right", sideSrc);
      logo.classList.toggle("hidden", !src);
      logo.src = src || "";
    }

    function setCrankSideGraphic(className, src) {
      const element = document.querySelector(`.${className}`);
      if (!element) return;
      element.style.backgroundImage = src ? `url("${src}")` : "";
    }

    function renderStatPanel(panel) {
      const layer = document.getElementById("stat-panel");
      const active = !!(panel && panel.kind);
      layer.className = `stat-panel ${active ? panel.kind : "hidden"}`;
      if (!active) return;
      setText("stat-panel-title", panel.title || "Race Update");
      setText("stat-panel-subtitle", panel.subtitle || "");
      const rows = document.getElementById("stat-panel-rows");
      rows.innerHTML = "";
      for (const row of (panel.rows || []).slice(0, 6)) {
        const item = document.createElement("div");
        item.className = "stat-panel-row";
        item.innerHTML = `
          <span class="stat-panel-label">${escapeHtml(row.label || "")}</span>
          <span class="stat-panel-value">${escapeHtml(row.value || "")}</span>
          <span class="stat-panel-detail">${escapeHtml(row.detail || "")}</span>
        `;
        rows.appendChild(item);
      }
    }

    function renderLapHistory(history) {
      const bar = document.getElementById("lap-history");
      const active = !!(history && history.length);
      bar.classList.toggle("hidden", !active);
      if (!active) return;
      const maxSegments = 80;
      const step = Math.max(1, Math.ceil(history.length / maxSegments));
      const compacted = [];
      for (let index = 0; index < history.length; index += step) {
        const chunk = history.slice(index, index + step);
        const status = chunk.some((lap) => lap.status === "caution")
          ? "caution"
          : chunk.some((lap) => lap.status === "green")
            ? "green"
            : "pending";
        compacted.push({ lap: chunk[0].lap, status });
      }
      bar.innerHTML = "";
      for (const lap of compacted) {
        const segment = document.createElement("span");
        segment.className = `lap-history-segment ${lap.status || "pending"}`;
        segment.title = `Lap ${lap.lap}: ${lap.status || "pending"}`;
        bar.appendChild(segment);
      }
    }

    function renderBrandGraphic(graphics, sessionType) {
      const img = document.getElementById("brand-graphic");
      const src = pickRotatingGraphic(graphics || [], 4.5);
      img.classList.toggle("hidden", !src);
      img.src = src || "";
    }

    function renderDriverCard(driver) {
      const card = document.getElementById("driver-card");
      const hasDriver = !!(driver && (driver.driver_name || driver.car_number));
      card.classList.toggle("hidden", !hasDriver);
      if (!hasDriver) return;
      setText("driver-card-number", driver.car_number || "?");
      setText("driver-card-name", driver.driver_name || "Unknown Driver");
      setText("driver-card-story", driver.story || "Featured driver");
      const image = document.getElementById("driver-card-image");
      const imageUrl = driver.car_image_url || "";
      card.classList.toggle("no-image", !imageUrl);
      image.classList.toggle("hidden", !imageUrl);
      image.style.backgroundImage = imageUrl ? `url("${cssEscapeUrl(imageUrl)}")` : "";
    }

    function buildTrackLine(state) {
      const pieces = [];
      if (state.track_name) pieces.push(state.track_name);
      if (state.session_type) pieces.push(state.session_type);
      return pieces.join(" • ") || "Waiting for iRacing";
    }

    function buildLapLine(state) {
      if (isTimedSession(state.session_type)) {
        const remaining = Number(state.session_time_remaining || 0);
        if (remaining > 0) return `${sessionLabel(state.session_type)} ${formatClock(remaining)}`;
        return sessionLabel(state.session_type);
      }
      if (state.total_laps) {
        const lap = state.lap || 0;
        const total = state.total_laps;
        const toGo = Math.max(total - lap, 0);
        if (lap >= Math.ceil(total / 2) && toGo > 0) {
          return `${toGo} to go`;
        }
        return `Lap ${lap} / ${total}`;
      }
      if (state.lap) return `Lap ${state.lap}`;
      return "Lap --";
    }

    function buildSessionCenterLine(state) {
      if (!isTimedSession(state.session_type)) return "";
      const remaining = Number(state.session_time_remaining || 0);
      const label = sessionLabel(state.session_type);
      return remaining > 0 ? `${label}  ${formatClock(remaining)}` : label;
    }

    function isTimedSession(sessionType) {
      const text = String(sessionType || "").toLowerCase();
      return text.includes("practice") || text.includes("qual");
    }

    function sessionLabel(sessionType) {
      const text = String(sessionType || "");
      if (text.toLowerCase().includes("qual")) return "Qualifying";
      if (text.toLowerCase().includes("practice")) return "Practice";
      return text || "Session";
    }

    function formatClock(seconds) {
      seconds = Math.max(0, Math.floor(Number(seconds) || 0));
      const hours = Math.floor(seconds / 3600);
      const minutes = Math.floor((seconds % 3600) / 60);
      const secs = seconds % 60;
      if (hours > 0) {
        return `${hours}:${String(minutes).padStart(2, "0")}:${String(secs).padStart(2, "0")}`;
      }
      return `${minutes}:${String(secs).padStart(2, "0")}`;
    }

    function setText(id, text) {
      const element = document.getElementById(id);
      element.textContent = text || "";
      element.classList.toggle("hidden", !text);
    }

    function escapeHtml(value) {
      return String(value)
        .replace(/&/g, "&amp;")
        .replace(/</g, "&lt;")
        .replace(/>/g, "&gt;")
        .replace(/"/g, "&quot;")
        .replace(/'/g, "&#039;");
    }

    function cssEscapeUrl(value) {
      return String(value).replace(/"/g, "%22").replace(/\\/g, "/");
    }

    function pickRotatingGraphic(graphics, seconds) {
      if (!graphics || !graphics.length) return "";
      const index = Math.floor(Date.now() / (seconds * 1000)) % graphics.length;
      return graphics[index];
    }

    refreshOverlay();
    setInterval(refreshOverlay, 1000);
  </script>
</body>
</html>
"""
