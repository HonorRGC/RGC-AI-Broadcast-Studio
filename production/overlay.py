import json
import mimetypes
import socket
import subprocess
import threading
import time
from dataclasses import dataclass, field
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path
from typing import Any
from urllib.parse import parse_qs, quote, unquote, urlparse
from urllib.request import urlopen

from config import (
    OVERLAY_BRAND_GRAPHICS,
    OVERLAY_EVENT_TITLE,
    OVERLAY_LEADERBOARD_STYLE,
    OVERLAY_RACE_SPONSOR,
    OVERLAY_SERIES_LOGO,
    OVERLAY_SERIES_NAME,
    RACE_SPONSOR_LOGOS,
    SPONSOR_READ_CAUSE_NAME,
)
from production.sim_racing_apps import (
    build_sim_racing_apps_car_debug_info,
    build_sim_racing_apps_car_render_info,
    sim_racing_apps_session_car_count,
)
from production.multiclass import build_multiclass_context


MAX_IRACING_RENDER_BYTES = 5 * 1024 * 1024


def is_safe_iracing_render_url(url):
    parsed = urlparse(str(url or ""))
    host = (parsed.hostname or "").lower()
    return (
        parsed.scheme == "http"
        and host in ("127.0.0.1", "localhost")
        and parsed.path
        in (
            "/pk_car.png",
            "/pk_helmet.png",
            "/SIMRacingApps/iRacing/pk_car.png",
            "/SIMRacingApps/iRacing/pk_helmet.png",
        )
    )


def proxied_iracing_render_url(url):
    text = str(url or "").strip()
    if not is_safe_iracing_render_url(text):
        return text
    return f"/iracing-render?url={quote(text, safe='')}"


def sanitize_driver_number_style(style):
    clean = {}
    if not isinstance(style, dict):
        return clean
    for key in ("color", "background", "outline"):
        value = str(style.get(key) or "").strip().lower()
        if is_safe_hex_color(value):
            clean[key] = value
    font_family = str(style.get("font_family") or "").strip()
    if font_family and all(ch.isalnum() or ch in " ,_-'\"" for ch in font_family):
        clean["font_family"] = font_family[:60]
    font_style = str(style.get("font_style") or "").strip().lower()
    if font_style == "italic":
        clean["font_style"] = "italic"
    return clean


def is_safe_hex_color(value):
    if len(value) not in (4, 7) or not value.startswith("#"):
        return False
    return all(ch in "0123456789abcdef" for ch in value[1:])


@dataclass
class OverlayEventConfig:
    title: str = OVERLAY_EVENT_TITLE
    sponsor: str = OVERLAY_RACE_SPONSOR
    cause: str = SPONSOR_READ_CAUSE_NAME
    series: str = OVERLAY_SERIES_NAME
    leaderboard_style: str = OVERLAY_LEADERBOARD_STYLE
    graphics: list[str] = field(default_factory=lambda: list(OVERLAY_BRAND_GRAPHICS))
    sponsor_graphics: list[str] = field(default_factory=lambda: list(RACE_SPONSOR_LOGOS))
    series_logo: str = OVERLAY_SERIES_LOGO


@dataclass
class LeaderboardEntry:
    position: int
    car_idx: int
    car_number: str
    driver_name: str
    number_style: dict[str, str] = field(default_factory=dict)
    laps_complete: int = 0
    interval: str = ""
    fastest_lap: str = ""
    class_id: str = ""
    class_name: str = ""
    class_position: int = 0
    class_size: int = 0
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
            "number_style": dict(self.number_style or {}),
            "laps_complete": self.laps_complete,
            "interval": self.interval,
            "fastest_lap": self.fastest_lap,
            "class_id": self.class_id,
            "class_name": self.class_name,
            "class_position": self.class_position,
            "class_size": self.class_size,
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
    car_idx: int = -1
    car_number: str = ""
    driver_name: str = ""
    story: str = ""
    country: str = ""
    car_image_url: str = ""
    number_style: dict[str, str] = field(default_factory=dict)
    position: int = 0
    class_name: str = ""
    class_position: int = 0
    class_size: int = 0
    starting_position: int = 0
    position_delta: int = 0
    interval: str = ""
    speed: str = ""
    expires_at: float = 0.0

    def to_dict(self):
        return {
            "car_idx": self.car_idx,
            "car_number": self.car_number,
            "driver_name": self.driver_name,
            "story": self.story,
            "country": self.country,
            "car_image_url": self.car_image_url,
            "number_style": dict(self.number_style or {}),
            "position": self.position,
            "class_name": self.class_name,
            "class_position": self.class_position,
            "class_size": self.class_size,
            "starting_position": self.starting_position,
            "position_delta": self.position_delta,
            "interval": self.interval,
            "speed": self.speed,
        }


@dataclass
class SpecialPresentation:
    kind: str = ""
    title: str = ""
    subtitle: str = ""
    graphics: list[str] = field(default_factory=list)
    video_url: str = ""
    expires_at: float = 0.0

    def to_dict(self):
        return {
            "kind": self.kind,
            "title": self.title,
            "subtitle": self.subtitle,
            "graphics": list(self.graphics),
            "video_url": self.video_url,
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
class ProducerPitRoadRow:
    car_idx: int = 0
    car_number: str = ""
    driver_name: str = ""
    status: str = ""
    last_pit_lap: int = 0
    laps_since_pit: int = 0
    pit_lane_seconds: float = 0.0
    pit_stop_seconds: float = 0.0
    service_guess: str = ""
    position_summary: str = ""

    def to_dict(self):
        return {
            "car_idx": self.car_idx,
            "car_number": self.car_number,
            "driver_name": self.driver_name,
            "status": self.status,
            "last_pit_lap": self.last_pit_lap,
            "laps_since_pit": self.laps_since_pit,
            "pit_lane_seconds": self.pit_lane_seconds,
            "pit_stop_seconds": self.pit_stop_seconds,
            "service_guess": self.service_guess,
            "position_summary": self.position_summary,
        }


@dataclass
class ProducerControlRoomItem:
    id: int = 0
    kind: str = ""
    title: str = ""
    message: str = ""
    status: str = "open"
    car_idx: int = 0
    car_number: str = ""
    driver_name: str = ""
    session_type: str = ""
    session_lap: int = 0
    camera_group: str = ""
    replay_session_num: int | None = None
    replay_session_time: float | None = None
    created_by: str = ""
    created_at: float = 0.0

    def to_dict(self):
        return {
            "id": self.id,
            "kind": self.kind,
            "title": self.title,
            "message": self.message,
            "status": self.status,
            "car_idx": self.car_idx,
            "car_number": self.car_number,
            "driver_name": self.driver_name,
            "session_type": self.session_type,
            "session_lap": self.session_lap,
            "camera_group": self.camera_group,
            "replay_session_num": self.replay_session_num,
            "replay_session_time": self.replay_session_time,
            "created_by": self.created_by,
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
    producer_leaderboard: list[LeaderboardEntry] = field(default_factory=list)
    lap_history: list[dict[str, Any]] = field(default_factory=list)

    def to_dict(self):
        return {
            "event": {
                "title": self.event.title,
                "sponsor": self.event.sponsor,
                "cause": self.event.cause,
                "series": self.event.series,
                "leaderboard_style": self.event.leaderboard_style,
                "graphics": list(self.event.graphics),
                "sponsor_graphics": list(self.event.sponsor_graphics),
                "series_logo": self.event.series_logo,
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
            "producer_leaderboard": [
                entry.to_dict() for entry in self.producer_leaderboard
            ],
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
        self.starting_positions_by_car_idx = {}
        self.number_style_by_car_idx = {}

    def build_from_telemetry(self, telemetry):
        results = telemetry.get_results()
        driver_lookup = telemetry.get_driver_lookup()
        track_info = telemetry.get_track_info()
        session_type_reader = getattr(telemetry, "get_session_type", None)
        session_type = session_type_reader() if session_type_reader else "Unknown"

        lap = self.best_race_lap(results, telemetry.get_lap())
        raw_caution = self.is_caution(telemetry)
        caution = (
            raw_caution
            and self.is_race_session(session_type)
            and self.safe_int(lap) > 0
        )
        green = self.is_green(telemetry, session_type=session_type, lap=lap, caution=caution)
        self.update_starting_position_memory(
            telemetry,
            results,
            session_type=session_type,
            lap=lap,
            green=green,
        )

        full_leaderboard = self.build_leaderboard(results, driver_lookup, session_type)
        if full_leaderboard:
            self.last_leaderboard = full_leaderboard
        elif self.is_race_session(session_type) and self.last_leaderboard:
            full_leaderboard = self.last_leaderboard

        leaderboard = self.visible_leaderboard_window(full_leaderboard)

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
            producer_leaderboard=full_leaderboard,
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
        multiclass = build_multiclass_context(valid_results, driver_lookup)

        leaderboard = []
        for car in valid_results:
            car_idx = car.get("CarIdx")
            driver = (driver_lookup or {}).get(car_idx, {})
            driver_info = dict(driver or {})
            driver_info.setdefault("car_idx", car_idx)
            driver_info.setdefault("CarIdx", car_idx)
            raw_position = self.safe_int(car.get("Position"), len(leaderboard) + 1)
            display_position = raw_position + 1 if zero_based else raw_position
            starting_position = self.starting_position(car, car_idx)
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
            class_position = multiclass.positions.get(car_idx)
            render_info = build_sim_racing_apps_car_render_info(driver_info)
            number_style = self.stable_number_style(
                car_idx,
                render_info.get("number_style", {}),
            )
            leaderboard.append(
                LeaderboardEntry(
                    position=display_position,
                    car_idx=car_idx,
                    car_number=str(driver.get("number") or "?"),
                    driver_name=str(driver.get("name") or f"Car {car_idx}"),
                    number_style=number_style,
                    laps_complete=self.safe_int(
                        car.get("LapsComplete", car.get("Lap", 0))
                    ),
                    class_id=getattr(class_position, "class_id", ""),
                    class_name=getattr(class_position, "class_name", ""),
                    class_position=getattr(class_position, "class_position", 0),
                    class_size=getattr(class_position, "class_size", 0),
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
        return leaderboard

    def stable_number_style(self, car_idx, style):
        sanitized = sanitize_driver_number_style(style)
        try:
            key = int(car_idx)
        except (TypeError, ValueError):
            return sanitized
        if sanitized:
            self.number_style_by_car_idx[key] = sanitized
            return sanitized
        return dict(self.number_style_by_car_idx.get(key, {}))

    def update_starting_position_memory(
        self,
        telemetry,
        results,
        session_type="Race",
        lap=0,
        green=False,
    ):
        if not self.is_race_session(session_type):
            return

        self.merge_starting_positions(
            self.starting_position_lookup_from_results(results, explicit_only=True),
            overwrite=True,
        )

        grid_reader = getattr(telemetry, "get_starting_grid", None)
        grid = grid_reader() if grid_reader else []
        if grid and (self.safe_int(lap) <= 1 or not green):
            self.merge_starting_positions(
                self.starting_position_lookup_from_results(grid, explicit_only=False),
                overwrite=False,
            )

        qualifying_reader = getattr(telemetry, "get_qualifying_results", None)
        qualifying = qualifying_reader() if qualifying_reader else []
        if qualifying:
            self.merge_starting_positions(
                self.starting_position_lookup_from_results(
                    qualifying,
                    explicit_only=False,
                ),
                overwrite=False,
            )

        if not self.starting_positions_by_car_idx and self.safe_int(lap) <= 1:
            self.merge_starting_positions(
                self.starting_position_lookup_from_results(
                    results,
                    explicit_only=False,
                ),
                overwrite=False,
            )

    def merge_starting_positions(self, lookup, overwrite=False):
        for car_idx, position in (lookup or {}).items():
            if car_idx is None or position <= 0:
                continue
            if overwrite or car_idx not in self.starting_positions_by_car_idx:
                self.starting_positions_by_car_idx[car_idx] = position

    def starting_position_lookup_from_results(self, results, explicit_only=False):
        valid_results = [
            dict(car)
            for car in results or []
            if car.get("CarIdx") is not None
        ]
        if not valid_results:
            return {}

        lookup = {}
        zero_based = any(
            self.safe_int(car.get("Position"), 999) == 0 for car in valid_results
        )
        valid_results.sort(key=lambda car: self.safe_int(car.get("Position"), 999))
        for index, car in enumerate(valid_results, start=1):
            car_idx = car.get("CarIdx")
            explicit = self.explicit_starting_position(car)
            if explicit > 0:
                lookup[car_idx] = explicit
                continue
            if explicit_only:
                continue
            raw_position = self.safe_int(car.get("Position"), index)
            lookup[car_idx] = raw_position + 1 if zero_based else raw_position
        return lookup

    def starting_position(self, car, car_idx=None):
        explicit = self.explicit_starting_position(car)
        if explicit > 0:
            return explicit
        try:
            return self.starting_positions_by_car_idx.get(car_idx, 0)
        except TypeError:
            return 0

    def explicit_starting_position(self, car):
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
            return f"{name} has {incidents} possible incident markers; treat that as a watch item until race control confirms it."
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
                return f"+{value:.2f}"
        if "Gap" in car and car.get("Gap") not in (None, ""):
            value = self.safe_float(car.get("Gap"))
            if value > 0:
                return f"+{value:.2f}"
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
        self.pit_road_rows = []
        self.producer_notes = []
        self.incident_reviews = []
        self.interview_queue = []
        self.director_suggestions = []
        self.race_control_audit = []
        self.race_event_log = []
        self._next_control_room_item_id = 1
        self.pending_commands = []
        self.control_state = {
            "auto_camera": True,
            "openai": False,
            "elevenlabs": False,
            "broadcaster_volume": 65,
            "music_volume": 65,
            "leaderboard_style": self.normalize_leaderboard_style(
                self.state_builder.event_config.leaderboard_style
            ),
        }
        self.camera_control = {
            "holder_id": "",
            "holder_name": "",
            "claimed_at": 0.0,
        }
        self.httpd = None
        self.thread = None
        self.static_dir = Path(__file__).resolve().parent / "static"
        self.paint_preview_dir = self.default_paint_preview_dir()

    @property
    def url(self):
        return f"http://{self.display_host}:{self.port}/overlay"

    @property
    def producer_url(self):
        return f"http://{self.display_host}:{self.port}/producer"

    @property
    def producer_share_url(self):
        return f"http://{self.share_host}:{self.port}/producer"

    @property
    def display_host(self):
        if str(self.host or "").strip() in ("", "0.0.0.0", "::"):
            return "127.0.0.1"
        return self.host

    @property
    def share_host(self):
        if str(self.host or "").strip() in ("", "0.0.0.0", "::"):
            return self.best_remote_helper_ip()
        return self.host

    @staticmethod
    def best_remote_helper_ip():
        return OverlayServer.tailscale_ip() or OverlayServer.local_lan_ip()

    @staticmethod
    def tailscale_ip():
        try:
            result = subprocess.run(
                ["tailscale", "ip", "-4"],
                capture_output=True,
                text=True,
                timeout=1.0,
                check=False,
            )
        except (OSError, subprocess.TimeoutExpired):
            return ""
        if result.returncode != 0:
            return ""
        for line in result.stdout.splitlines():
            ip = line.strip()
            if ip.startswith("100."):
                return ip
        return ""

    @staticmethod
    def local_lan_ip():
        try:
            with socket.socket(socket.AF_INET, socket.SOCK_DGRAM) as sock:
                sock.connect(("8.8.8.8", 80))
                return sock.getsockname()[0]
        except OSError:
            try:
                return socket.gethostbyname(socket.gethostname())
            except OSError:
                return "127.0.0.1"

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
            self.apply_runtime_overrides(state)
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
                if self.special_presentation.kind == "crank_it_up":
                    state.featured_driver = None
            else:
                self.special_presentation = None
            if self.stat_panel and self.stat_panel.expires_at > time.monotonic():
                state.stat_panel = self.stat_panel
            else:
                self.stat_panel = None
            self.state = state

    @staticmethod
    def normalize_leaderboard_style(value):
        style = str(value or "side").strip().lower()
        if style in ("ticker", "scroll", "top"):
            return "ticker"
        if style in ("flo", "flo_top", "flo-top", "top_grid"):
            return "flo"
        return "side"

    def apply_runtime_overrides(self, state):
        state.event.leaderboard_style = self.normalize_leaderboard_style(
            self.control_state.get("leaderboard_style")
            or state.event.leaderboard_style
        )

    def current_leaderboard_style(self):
        with self.lock:
            return self.normalize_leaderboard_style(
                self.control_state.get("leaderboard_style")
                or self.state.event.leaderboard_style
            )

    def set_leaderboard_style(self, style):
        normalized = self.normalize_leaderboard_style(style)
        with self.lock:
            self.control_state["leaderboard_style"] = normalized
            self.state.event.leaderboard_style = normalized
        return normalized

    def show_featured_driver(
        self,
        car_number,
        driver_name,
        car_idx=-1,
        story="",
        country="",
        duration=10.0,
        car_image_url="",
        position=0,
        class_name="",
        class_position=0,
        class_size=0,
        starting_position=0,
        position_delta=0,
        interval="",
        speed="",
        number_style=None,
    ):
        with self.lock:
            if (
                self.special_presentation
                and self.special_presentation.kind == "crank_it_up"
                and self.special_presentation.expires_at > time.monotonic()
            ):
                self.featured_driver = None
                self.state.featured_driver = None
                return
            self.featured_driver = FeaturedDriver(
                car_idx=self.state_builder.safe_int(car_idx, -1),
                car_number=str(car_number or ""),
                driver_name=str(driver_name or ""),
                story=str(story or ""),
                country=str(country or ""),
                car_image_url=proxied_iracing_render_url(car_image_url),
                number_style=sanitize_driver_number_style(number_style),
                position=self.state_builder.safe_int(position),
                class_name=str(class_name or ""),
                class_position=self.state_builder.safe_int(class_position),
                class_size=self.state_builder.safe_int(class_size),
                starting_position=self.state_builder.safe_int(starting_position),
                position_delta=self.state_builder.safe_int(position_delta),
                interval=str(interval or ""),
                speed=str(speed or ""),
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
        video_url="",
    ):
        with self.lock:
            if str(kind or "") == "crank_it_up":
                self.featured_driver = None
                self.state.featured_driver = None
            self.special_presentation = SpecialPresentation(
                kind=str(kind or ""),
                title=str(title or ""),
                subtitle=str(subtitle or ""),
                graphics=list(graphics or self.state_builder.event_config.graphics),
                video_url=str(video_url or ""),
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

    def set_pit_road_rows(self, rows):
        with self.lock:
            self.pit_road_rows = [
                row
                if isinstance(row, ProducerPitRoadRow)
                else ProducerPitRoadRow(
                    car_idx=self.state_builder.safe_int((row or {}).get("car_idx")),
                    car_number=str((row or {}).get("car_number", "")),
                    driver_name=str((row or {}).get("driver_name", "")),
                    status=str((row or {}).get("status", "")),
                    last_pit_lap=self.state_builder.safe_int(
                        (row or {}).get("last_pit_lap")
                    ),
                    laps_since_pit=self.state_builder.safe_int(
                        (row or {}).get("laps_since_pit")
                    ),
                    pit_lane_seconds=float((row or {}).get("pit_lane_seconds") or 0.0),
                    pit_stop_seconds=float((row or {}).get("pit_stop_seconds") or 0.0),
                    service_guess=str((row or {}).get("service_guess", "")),
                    position_summary=str((row or {}).get("position_summary", "")),
                )
                for row in (rows or [])
            ][:12]

    def add_control_room_item(
        self,
        collection_name,
        kind,
        title="",
        message="",
        status="open",
        car_idx=0,
        car_number="",
        driver_name="",
        session_type="",
        session_lap=0,
        camera_group="",
        replay_session_num=None,
        replay_session_time=None,
        created_by="",
        limit=30,
    ):
        item = ProducerControlRoomItem(
            id=self._next_control_room_item_id,
            kind=str(kind or ""),
            title=str(title or ""),
            message=str(message or ""),
            status=str(status or "open"),
            car_idx=self.state_builder.safe_int(car_idx),
            car_number=str(car_number or ""),
            driver_name=str(driver_name or ""),
            session_type=str(session_type or ""),
            session_lap=self.state_builder.safe_int(session_lap),
            camera_group=str(camera_group or ""),
            replay_session_num=(
                self.state_builder.safe_int(replay_session_num)
                if replay_session_num is not None
                else None
            ),
            replay_session_time=(
                float(replay_session_time)
                if replay_session_time not in (None, "")
                else None
            ),
            created_by=str(created_by or ""),
            created_at=time.time(),
        )
        self._next_control_room_item_id += 1
        collection = getattr(self, collection_name)
        collection.insert(0, item)
        setattr(self, collection_name, collection[:limit])
        return item

    def add_producer_note(self, message, payload=None):
        payload = payload or {}
        with self.lock:
            return self.add_control_room_item(
                "producer_notes",
                "note",
                "Producer Note",
                message,
                status="open",
                car_idx=payload.get("car_idx", 0),
                car_number=payload.get("car_number", ""),
                driver_name=payload.get("driver_name", ""),
                created_by=payload.get("producer_name", ""),
                limit=40,
            )

    def add_incident_review(self, message, payload=None):
        payload = payload or {}
        with self.lock:
            return self.add_control_room_item(
                "incident_reviews",
                "incident_review",
                "Incident Review",
                message,
                status="needs review",
                car_idx=payload.get("car_idx", 0),
                car_number=payload.get("car_number", ""),
                driver_name=payload.get("driver_name", ""),
                created_by=payload.get("producer_name", ""),
                limit=30,
            )

    def add_interview_queue_item(self, payload=None):
        payload = payload or {}
        with self.lock:
            return self.add_control_room_item(
                "interview_queue",
                "interview",
                "Interview Queue",
                payload.get("message", "") or "Queued for interview.",
                status="queued",
                car_idx=payload.get("car_idx", 0),
                car_number=payload.get("car_number", ""),
                driver_name=payload.get("driver_name", ""),
                created_by=payload.get("producer_name", ""),
                limit=20,
            )

    def add_race_control_audit(self, message, payload=None):
        payload = payload or {}
        with self.lock:
            audit_item = self.add_control_room_item(
                "race_control_audit",
                "race_control",
                "Race Control",
                message,
                status="sent" if payload.get("ok", True) else "failed",
                car_idx=payload.get("car_idx", 0),
                car_number=payload.get("car_number", ""),
                driver_name=payload.get("driver_name", ""),
                created_by=payload.get("producer_name", ""),
                limit=50,
            )
            self.add_control_room_item(
                "race_event_log",
                "race_control",
                "Race Control",
                message,
                status=audit_item.status,
                car_idx=payload.get("car_idx", 0),
                car_number=payload.get("car_number", ""),
                driver_name=payload.get("driver_name", ""),
                created_by=payload.get("producer_name", ""),
                limit=100,
            )
            return audit_item

    def add_race_event_log(self, title, message, payload=None, kind="race_event", status="logged"):
        payload = payload or {}
        with self.lock:
            return self.add_control_room_item(
                "race_event_log",
                kind,
                title,
                message,
                status=status,
                car_idx=payload.get("car_idx", 0),
                car_number=payload.get("car_number", ""),
                driver_name=payload.get("driver_name", ""),
                session_type=payload.get("session_type", ""),
                session_lap=payload.get("session_lap", 0),
                camera_group=payload.get("camera_group", ""),
                replay_session_num=payload.get("replay_session_num"),
                replay_session_time=payload.get("replay_session_time"),
                created_by=payload.get("producer_name", "") or payload.get("created_by", ""),
                limit=100,
            )

    def update_control_room_item_status(self, collection_name, item_id, status):
        item_id = self.state_builder.safe_int(item_id)
        with self.lock:
            for item in getattr(self, collection_name):
                if item.id == item_id:
                    item.status = str(status or item.status)
                    return item
        return None

    def update_race_event_log_item(self, item_id, status=None, note=None, producer_name=""):
        item_id = self.state_builder.safe_int(item_id)
        clean_note = str(note or "").strip()
        with self.lock:
            for item in self.race_event_log:
                if item.id != item_id:
                    continue
                if status:
                    item.status = str(status)
                if clean_note:
                    item.message = f"{item.message} | Review note: {clean_note}"
                    item.created_by = str(producer_name or item.created_by or "")
                return item
        return None

    def set_director_suggestions(self, rows):
        with self.lock:
            self.director_suggestions = [
                ProducerControlRoomItem(
                    id=index + 1,
                    kind=str((row or {}).get("kind", "suggestion")),
                    title=str((row or {}).get("title", "")),
                    message=str((row or {}).get("message", "")),
                    status=str((row or {}).get("status", "suggested")),
                    car_idx=self.state_builder.safe_int((row or {}).get("car_idx")),
                    car_number=str((row or {}).get("car_number", "")),
                    driver_name=str((row or {}).get("driver_name", "")),
                    session_type=str((row or {}).get("session_type", "")),
                    session_lap=self.state_builder.safe_int((row or {}).get("session_lap")),
                    camera_group=str((row or {}).get("camera_group", "")),
                    replay_session_num=(row or {}).get("replay_session_num"),
                    replay_session_time=(row or {}).get("replay_session_time"),
                    created_by="RGC Director",
                    created_at=time.time(),
                )
                for index, row in enumerate((rows or [])[:8])
            ]

    def set_control_state(self, **updates):
        with self.lock:
            self.control_state.update(updates)

    def claim_camera_control(self, client_id, producer_name="Producer"):
        client_id = str(client_id or "").strip()
        if not client_id:
            return False, "Camera control needs a producer name first."
        producer_name = str(producer_name or "Producer").strip()[:40] or "Producer"
        now = time.time()
        with self.lock:
            holder_id = self.camera_control.get("holder_id", "")
            holder_name = self.camera_control.get("holder_name", "Producer")
            if holder_id and holder_id != client_id:
                return False, f"Camera control is held by {holder_name}."
            self.camera_control = {
                "holder_id": client_id,
                "holder_name": producer_name,
                "claimed_at": now,
            }
        return True, f"{producer_name} has camera control."

    def release_camera_control(self, client_id):
        client_id = str(client_id or "").strip()
        with self.lock:
            holder_id = self.camera_control.get("holder_id", "")
            holder_name = self.camera_control.get("holder_name", "Producer")
            if not holder_id:
                return True, "Camera control is already open."
            if holder_id != client_id:
                return False, f"Camera control is held by {holder_name}."
            self.camera_control = {
                "holder_id": "",
                "holder_name": "",
                "claimed_at": 0.0,
            }
        return True, "Camera control released."

    def camera_control_allows(self, client_id):
        client_id = str(client_id or "").strip()
        with self.lock:
            holder_id = self.camera_control.get("holder_id", "")
        return not holder_id or holder_id == client_id

    def camera_control_holder_name(self):
        with self.lock:
            return self.camera_control.get("holder_name", "") or "another producer"

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
            self.apply_runtime_overrides(self.state)
            data = self.state.to_dict()
            data["producer_feed"] = [item.to_dict() for item in self.producer_feed]
            data["control_state"] = dict(self.control_state)
            data["camera_control"] = dict(self.camera_control)
            data["producer_url"] = self.producer_url
            data["producer_share_url"] = self.producer_share_url
            data["pit_road"] = [row.to_dict() for row in self.pit_road_rows]
            data["producer_notes"] = [item.to_dict() for item in self.producer_notes]
            data["incident_reviews"] = [item.to_dict() for item in self.incident_reviews]
            data["interview_queue"] = [item.to_dict() for item in self.interview_queue]
            data["director_suggestions"] = [
                item.to_dict() for item in self.director_suggestions
            ]
            data["race_control_audit"] = [
                item.to_dict() for item in self.race_control_audit
            ]
            data["race_event_log"] = [item.to_dict() for item in self.race_event_log]
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

                if self.path == "/overlay/debug/sim-racing-apps":
                    self.send_json(server.sim_racing_apps_debug_state())
                    return

                if self.path.startswith("/assets/"):
                    self.send_asset(self.path.removeprefix("/assets/"))
                    return

                if self.path.startswith("/paint-previews/"):
                    self.send_paint_preview(self.path.removeprefix("/paint-previews/"))
                    return

                if self.path.startswith("/iracing-render"):
                    self.send_iracing_render_proxy()
                    return

                self.send_error(404)

            def do_POST(self):
                if self.path == "/overlay/clear-special-presentation":
                    server.clear_special_presentation()
                    self.send_json({"ok": True})
                    return

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

            def send_iracing_render_proxy(self):
                query = parse_qs(urlparse(self.path).query)
                target = str((query.get("url") or [""])[0])
                if not is_safe_iracing_render_url(target):
                    self.send_error(400)
                    return
                try:
                    with urlopen(target, timeout=2.0) as response:
                        body = response.read(MAX_IRACING_RENDER_BYTES + 1)
                        content_type = response.headers.get("Content-Type") or "image/png"
                except OSError:
                    self.send_error(502)
                    return
                if len(body) > MAX_IRACING_RENDER_BYTES:
                    self.send_error(502)
                    return
                if not str(content_type).lower().startswith("image/"):
                    content_type = "image/png"

                self.send_response(200)
                self.send_header("Content-Type", content_type)
                self.send_header("Cache-Control", "no-store")
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

    def sim_racing_apps_debug_state(self):
        with self.lock:
            state = self.state.to_dict()
        leaderboard = list(state.get("producer_leaderboard") or state.get("leaderboard") or [])
        featured = dict(state.get("featured_driver") or {})
        drivers = []
        if featured:
            drivers.append(
                {
                    "source": "featured_driver",
                    "car_idx": featured.get("car_idx"),
                    "number": featured.get("car_number"),
                    "name": featured.get("driver_name"),
                }
            )
        for entry in leaderboard[:10]:
            drivers.append(
                {
                    "source": f"P{entry.get('position')}",
                    "car_idx": entry.get("car_idx"),
                    "number": entry.get("car_number"),
                    "name": entry.get("driver_name"),
                    "overlay_number_style": entry.get("number_style") or {},
                }
            )
        return {
            "sim_racing_apps_cars": sim_racing_apps_session_car_count(),
            "drivers": [
                {
                    **driver,
                    "sim_racing_apps": build_sim_racing_apps_car_debug_info(
                        {
                            "car_idx": driver.get("car_idx"),
                            "number": driver.get("number"),
                            "name": driver.get("name"),
                        }
                    ),
                }
                for driver in drivers
                if driver.get("name") or driver.get("number")
            ],
        }


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
      grid-template-columns: 1.2fr 1.5fr auto;
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

    .producer-share {
      display: grid;
      gap: 7px;
      justify-self: stretch;
    }

    .producer-share-row,
    .camera-lock-row {
      display: flex;
      gap: 8px;
      align-items: center;
      flex-wrap: wrap;
    }

    .share-link {
      color: #dbe9ff;
      font-weight: 800;
      font-size: 13px;
      word-break: break-all;
    }

    .producer-name-input {
      min-width: 160px;
      border: 1px solid #2e3b4d;
      border-radius: 10px;
      background: #0b111b;
      color: var(--text);
      padding: 8px 10px;
      font-weight: 700;
    }

    .camera-status {
      color: var(--muted);
      font-size: 12px;
      font-weight: 800;
      text-transform: uppercase;
      letter-spacing: 0.06em;
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
      grid-template-columns: minmax(520px, 0.82fr) minmax(820px, 1.5fr);
      gap: 12px;
      align-items: start;
    }

    .left-rail {
      display: grid;
      gap: 12px;
      align-content: start;
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
      overflow: visible;
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
      padding: 12px;
      display: grid;
      grid-template-columns: repeat(2, minmax(0, 1fr));
      gap: 10px;
    }

    .driver-title {
      display: grid;
      grid-template-columns: 90px 1fr;
      gap: 12px;
      align-items: center;
      grid-column: 1 / -1;
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
      grid-template-columns: repeat(5, minmax(0, 1fr));
      gap: 8px;
      grid-column: 1 / -1;
    }

    .detail-item {
      padding: 8px;
      background: rgba(255, 255, 255, 0.05);
      border: 1px solid rgba(255, 255, 255, 0.08);
      border-radius: 12px;
    }

    .detail-item .value {
      font-size: 20px;
    }

    .story-box {
      padding: 12px;
      border-radius: 14px;
      border: 1px solid rgba(83, 167, 255, 0.28);
      background: rgba(83, 167, 255, 0.09);
      color: #dcecff;
      line-height: 1.35;
      grid-column: 1 / -1;
    }

    .button-row {
      display: grid;
      grid-template-columns: repeat(2, minmax(0, 1fr));
      gap: 10px;
    }

    .button-row.control-grid {
      grid-template-columns: repeat(5, minmax(0, 1fr));
      gap: 8px;
    }

    .audio-control-row {
      margin-top: 12px;
      display: grid;
      grid-template-columns: auto minmax(120px, 1fr);
      gap: 8px 12px;
      align-items: center;
      color: var(--muted);
      font-size: 12px;
      font-weight: 800;
      text-transform: uppercase;
    }

    .audio-control-row input[type="range"] {
      width: 100%;
      accent-color: var(--blue);
    }

    .camera-shot-row {
      display: grid;
      grid-template-columns: minmax(150px, 0.8fr) repeat(4, minmax(0, 1fr));
      gap: 8px;
      grid-column: 1 / -1;
    }

    .camera-shot-select {
      border: 1px solid #2e3b4d;
      border-radius: 12px;
      background: #0b111b;
      color: var(--text);
      padding: 9px 10px;
      font-weight: 900;
    }

    .replay-deck-row {
      display: grid;
      grid-template-columns: repeat(6, minmax(0, 1fr));
      gap: 8px;
      grid-column: 1 / -1;
    }

    button {
      border: 0;
      border-radius: 12px;
      padding: 9px 10px;
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
    .control-button:disabled {
      cursor: not-allowed;
      opacity: 0.45;
      background: #344052;
    }

    .race-admin-status {
      margin-bottom: 9px;
      padding: 8px 10px;
      border-radius: 10px;
      background: rgba(143, 46, 55, 0.22);
      color: #ffd3d8;
      font-size: 12px;
      font-weight: 900;
      text-transform: uppercase;
      letter-spacing: 0.06em;
    }

    .race-admin-status.on {
      background: rgba(31, 117, 80, 0.22);
      color: #bdf8d8;
    }

    .panel {
      padding: 10px;
      background: rgba(255, 255, 255, 0.045);
      border: 1px solid rgba(255, 255, 255, 0.08);
      border-radius: 14px;
    }

    .panel.full,
    .panel.wide,
    .button-row.primary-actions {
      grid-column: 1 / -1;
    }

    .panel.priority {
      min-height: 142px;
    }

    .panel.director-suggestions {
      min-height: 210px;
    }

    .panel.director-suggestions .control-room-list {
      max-height: 175px;
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
      max-height: 230px;
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

    .pit-road-list {
      display: grid;
      gap: 8px;
      max-height: 210px;
      overflow: auto;
    }

    .pit-road-row {
      display: grid;
      grid-template-columns: 58px 1fr auto;
      gap: 8px;
      align-items: start;
      padding: 9px 10px;
      border-radius: 10px;
      background: rgba(255, 255, 255, 0.045);
      border-left: 4px solid var(--yellow);
    }

    .pit-road-row.pitting {
      border-left-color: var(--green);
      animation: pulse 0.8s infinite alternate;
    }

    .pit-road-main {
      color: #fff;
      font-weight: 900;
      text-transform: uppercase;
      letter-spacing: 0.03em;
    }

    .pit-road-meta,
    .pit-road-service {
      margin-top: 2px;
      color: var(--muted);
      font-size: 12px;
      line-height: 1.25;
    }

    .pit-road-service {
      color: #dbe5f4;
    }

    .producer-textarea {
      width: 100%;
      min-height: 58px;
      resize: vertical;
      border: 1px solid #2e3b4d;
      border-radius: 12px;
      background: #0b111b;
      color: var(--text);
      padding: 10px 12px;
      font: inherit;
      line-height: 1.35;
      margin-bottom: 10px;
    }

    .control-room-list {
      display: grid;
      gap: 8px;
      max-height: 190px;
      overflow: auto;
    }

    .panel.priority .control-room-list {
      max-height: 132px;
    }

    .control-room-item {
      padding: 9px 10px;
      border-radius: 10px;
      background: rgba(255, 255, 255, 0.045);
      border-left: 4px solid var(--blue);
    }

    .control-room-item.note { border-left-color: var(--green); }
    .control-room-item.incident_review { border-left-color: var(--yellow); }
    .control-room-item.interview { border-left-color: #c78cff; }
    .control-room-item.race_control { border-left-color: var(--red); }
    .control-room-item.incident { border-left-color: var(--red); }
    .control-room-item.pass { border-left-color: var(--green); }
    .control-room-item.pit { border-left-color: var(--yellow); }
    .control-room-item.penalty { border-left-color: #c78cff; }
    .control-room-item.replay { border-left-color: var(--blue); }

    .event-log-table {
      max-height: 470px;
      overflow: auto;
      border: 1px solid rgba(255, 255, 255, 0.10);
      border-radius: 12px;
      background: rgba(0, 0, 0, 0.22);
    }

    .event-log-row {
      display: grid;
      grid-template-columns: 126px 82px 62px minmax(150px, 0.9fr) minmax(360px, 1.8fr) 104px;
      gap: 8px;
      align-items: center;
      padding: 7px 9px;
      border-bottom: 1px solid rgba(255, 255, 255, 0.08);
      font-size: 12px;
    }

    .event-log-row.header {
      position: sticky;
      top: 0;
      z-index: 2;
      background: #313743;
      color: #cbd5e1;
      font-weight: 950;
      text-transform: uppercase;
      letter-spacing: 0.05em;
    }

    .event-log-row:not(.header) {
      cursor: pointer;
      background: rgba(255, 255, 255, 0.035);
    }

    .event-log-row:not(.header):hover {
      background: rgba(43, 115, 255, 0.16);
    }

    .event-log-row.incident {
      background: rgba(130, 21, 32, 0.62);
      color: #fff;
    }

    .event-log-row.pass,
    .event-log-row.lead_change {
      background: rgba(21, 90, 55, 0.38);
    }

    .event-log-row.pit {
      background: rgba(116, 82, 22, 0.42);
    }

    .event-log-row.penalty {
      background: rgba(92, 58, 132, 0.42);
    }

    .event-log-row.replay {
      background: rgba(22, 55, 120, 0.46);
    }

    .event-log-cell {
      min-width: 0;
      overflow: hidden;
      text-overflow: ellipsis;
      white-space: nowrap;
    }

    .event-log-driver,
    .event-log-desc {
      font-weight: 800;
      color: #fff;
    }

    .event-log-camera {
      display: flex;
      gap: 5px;
      align-items: center;
      justify-content: flex-end;
      flex-wrap: wrap;
    }

    .event-log-camera-label {
      color: #fff;
      font-weight: 900;
      min-width: 38px;
      text-align: right;
    }

    .control-room-title {
      color: #fff;
      font-size: 12px;
      font-weight: 950;
      text-transform: uppercase;
      letter-spacing: 0.06em;
    }

    .control-room-message {
      margin-top: 3px;
      color: #dbe5f4;
      line-height: 1.3;
    }

    .control-room-meta {
      margin-top: 4px;
      color: var(--muted);
      font-size: 11px;
      text-transform: uppercase;
      letter-spacing: 0.05em;
    }

    .mini-button-row {
      display: flex;
      gap: 7px;
      flex-wrap: wrap;
      margin-top: 8px;
    }

    .mini-button {
      padding: 7px 9px;
      border-radius: 9px;
      font-size: 11px;
      cursor: pointer;
      opacity: 1;
      background: #294b73;
    }

    .mini-button.warn { background: #8b6a1c; }
    .mini-button.good { background: #1f7550; }

    @keyframes pulse {
      from { filter: brightness(1); }
      to { filter: brightness(1.28); }
    }

    @media (max-width: 1050px) {
      .grid { grid-template-columns: repeat(2, minmax(150px, 1fr)); }
      .main { grid-template-columns: 1fr; }
      .left-rail { grid-template-columns: 1fr; }
      .driver-detail { grid-template-columns: 1fr; }
      .detail-grid { grid-template-columns: repeat(2, minmax(0, 1fr)); }
      .button-row.control-grid { grid-template-columns: repeat(2, minmax(0, 1fr)); }
      .camera-shot-row { grid-template-columns: repeat(2, minmax(0, 1fr)); }
      .replay-deck-row { grid-template-columns: repeat(2, minmax(0, 1fr)); }
      .rows { overflow: visible; }
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
      <div class="producer-share">
        <div>
          <div class="label">Helper Link</div>
          <div class="share-link" id="producer-share-link">Start the broadcast to get the link.</div>
        </div>
        <div class="producer-share-row">
          <input class="producer-name-input" id="producer-name-input" placeholder="Producer name" />
          <button class="control-button" id="take-camera-control-button">Take Camera Control</button>
          <button class="control-button warn" id="release-camera-control-button">Release</button>
        </div>
        <div class="camera-status" id="camera-control-status">Camera control is open.</div>
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
      <div class="left-rail">
        <section class="leaderboard">
          <div class="section-head">
            <h2>Live Leaderboard</h2>
            <span class="hint">Click a driver for notes</span>
          </div>
          <div class="rows" id="leaderboard-rows"></div>
        </section>

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
      </div>

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
          <div class="detail-item"><div class="label">Possible Incidents</div><div class="value" id="detail-incidents">--</div></div>
          <div class="detail-item"><div class="label">Fastest Lap</div><div class="value" id="detail-fastest">--</div></div>
          <div class="detail-item"><div class="label">Last Pit</div><div class="value" id="detail-last-pit">--</div></div>
          <div class="detail-item"><div class="label">Pit Time</div><div class="value" id="detail-pit-time">--</div></div>
        </div>

        <div class="story-box" id="story-box">
          Producer note: pick a driver from the leaderboard. This panel is built to become the broadcaster control room.
        </div>

        <div class="panel full priority director-suggestions">
          <h3>Director Suggestions</h3>
          <div class="small">Live booth cues with race data, story ideas, and camera targets.</div>
          <div class="control-room-list" id="director-suggestions-list" style="margin-top: 8px;">
            <div class="small">Suggested camera/story targets will appear here.</div>
          </div>
        </div>

        <div class="panel full priority" id="featured-panel">
          <h3>Current Broadcast Focus</h3>
          <div class="small">No featured driver on the overlay right now.</div>
        </div>

        <div class="panel wide">
          <h3>Pit Road / Strategy</h3>
          <div class="pit-road-list" id="pit-road-list">
            <div class="small">Pit stop data will appear after cars visit pit road.</div>
          </div>
        </div>

        <div class="button-row primary-actions">
          <button class="control-button" id="follow-driver-button">Move Camera to Driver</button>
          <button class="control-button" id="leader-camera-button">Back to Leader</button>
        </div>

        <div class="camera-shot-row">
          <select class="camera-shot-select" id="manual-camera-group-select" title="Manual camera shot">
            <option value="TV1">TV1</option>
            <option value="Far Chase">Far Chase</option>
            <option value="Rear Chase">Rear Chase</option>
            <option value="Cockpit">Cockpit</option>
          </select>
          <button class="control-button camera-shot-button" data-camera-group="TV1">TV1</button>
          <button class="control-button camera-shot-button" data-camera-group="Far Chase">Far Chase</button>
          <button class="control-button camera-shot-button" data-camera-group="Rear Chase">Rear Chase</button>
          <button class="control-button camera-shot-button" data-camera-group="Cockpit">Cockpit</button>
        </div>

        <div class="replay-deck-row">
          <button class="control-button warn" id="rewind-button">Reverse Speed</button>
          <button class="control-button warn" id="slow-motion-button">Slow Motion</button>
          <button class="control-button warn" id="pause-replay-button">Pause</button>
          <button class="control-button warn" id="play-replay-button">Play</button>
          <button class="control-button warn" id="fast-forward-button">Fast Forward Speed</button>
          <button class="control-button" id="return-live-button">Return Live</button>
        </div>

        <div class="panel full">
          <h3>Manual Show Features</h3>
          <div class="small">Use these when the race needs energy, a sponsor hit, or a manual commercial break.</div>
          <div class="button-row control-grid" style="margin-top: 10px;">
            <button class="control-button warn" id="manual-crank-it-up-button">Play Crank It Up</button>
            <button class="control-button" id="manual-sponsor-button">Play Sponsor / Commercial</button>
          </div>
        </div>

        <div class="panel full">
          <h3>Control Room Toggles</h3>
          <div class="button-row control-grid">
            <button class="control-button" id="auto-camera-button">Auto Camera</button>
            <button class="control-button" id="openai-button">OpenAI</button>
            <button class="control-button" id="elevenlabs-button">ElevenLabs</button>
            <button class="control-button" id="leaderboard-style-button">Leaderboard: Side</button>
            <button class="control-button danger" id="race-admin-button">Race Admin: OFF</button>
          </div>
          <div class="audio-control-row">
            <label>Broadcasters <span id="broadcaster-volume-label">65%</span></label>
            <input id="broadcaster-volume-slider" type="range" min="0" max="100" value="65" />
            <label>Music <span id="music-volume-label">65%</span></label>
            <input id="music-volume-slider" type="range" min="0" max="100" value="65" />
          </div>
        </div>

        <div class="panel full">
          <h3>Race Control</h3>
          <div class="race-admin-status" id="race-admin-status">Race Admin Mode is OFF</div>
          <div class="small">Commands use the selected driver when needed. Broadcaster PC must be an iRacing hosted-session admin.</div>
          <div class="button-row control-grid" style="margin-top: 10px;">
            <button class="control-button danger race-control-button" data-race-action="throw_yellow" data-dangerous="true">Throw Caution</button>
            <button class="control-button warn race-control-button" data-race-action="extend_caution">Extend Caution +1</button>
            <button class="control-button warn race-control-button" data-race-action="one_to_green">Set One-To-Green</button>
            <button class="control-button danger race-control-button" data-race-action="clear_all" data-dangerous="true">Clear All</button>
          </div>
          <div class="button-row control-grid" style="margin-top: 8px;">
            <button class="control-button race-control-button" data-race-action="clear_penalty" data-driver-required="true">Clear Penalty</button>
            <button class="control-button race-control-button" data-race-action="eol" data-driver-required="true">EOL</button>
            <button class="control-button warn race-control-button" data-race-action="drive_through" data-driver-required="true">Drive Through</button>
            <button class="control-button warn race-control-button" data-race-action="timed_black" data-driver-required="true">Timed Black</button>
            <button class="control-button race-control-button" data-race-action="waveby" data-driver-required="true">Wave Around</button>
            <button class="control-button danger race-control-button" data-race-action="dq" data-driver-required="true" data-dangerous="true">DQ</button>
            <button class="control-button danger race-control-button" data-race-action="remove" data-driver-required="true" data-dangerous="true">Remove</button>
          </div>
        </div>

        <div class="panel full">
          <h3>Producer Notes</h3>
          <textarea class="producer-textarea" id="producer-note-input" placeholder="Type a booth note, race-control reminder, or driver story..."></textarea>
          <div class="button-row">
            <button class="control-button" id="add-producer-note-button">Add Note</button>
            <button class="control-button" id="add-driver-note-button">Note Selected Driver</button>
          </div>
          <div class="control-room-list" id="producer-notes-list" style="margin-top: 10px;">
            <div class="small">Manual notes will appear here.</div>
          </div>
        </div>

        <div class="panel">
          <h3>Interview Queue</h3>
          <div class="small">Manual for now. Discord bot hookup can use this same queue later.</div>
          <div class="button-row" style="margin-top: 10px;">
            <button class="control-button" id="queue-interview-button">Queue Selected Driver</button>
            <button class="control-button" id="queue-top-three-button">Queue Top 3</button>
          </div>
          <div class="control-room-list" id="interview-queue-list" style="margin-top: 10px;">
            <div class="small">Interview queue will appear here.</div>
          </div>
        </div>

        <div class="panel wide">
          <h3>Race Event Log</h3>
          <div class="small">Automatic race events. Click Review to jump replay back, or Note to mark an event for admin/recap follow-up.</div>
          <div class="event-log-table" id="race-event-log-list" style="margin-top: 10px;">
            <div class="small">Race events will appear here.</div>
          </div>
        </div>

        <div class="panel">
          <h3>Race Control Audit</h3>
          <div class="control-room-list" id="race-control-audit-list">
            <div class="small">Admin command details sent from Producer Assist will appear here.</div>
          </div>
        </div>

        <div class="panel">
          <h3>Discord Setup</h3>
          <div class="small">Prepared for later: bot token, server ID, booth channel, waiting room, and interview channel will live in Studio settings.</div>
          <div class="small" id="discord-status" style="margin-top: 6px;">Discord bot is not connected yet.</div>
        </div>

      </aside>
    </main>
  </div>

  <script>
    let selectedCarIdx = null;
    let lastState = null;
    const PRODUCER_CLIENT_KEY = "rgcProducerClientId";
    const PRODUCER_NAME_KEY = "rgcProducerName";

    function producerClientId() {
      let clientId = localStorage.getItem(PRODUCER_CLIENT_KEY);
      if (!clientId) {
        clientId = (window.crypto && window.crypto.randomUUID)
          ? window.crypto.randomUUID()
          : `producer-${Date.now()}-${Math.random().toString(16).slice(2)}`;
        localStorage.setItem(PRODUCER_CLIENT_KEY, clientId);
      }
      return clientId;
    }

    function currentProducerName() {
      const input = document.getElementById("producer-name-input");
      const name = (input && input.value ? input.value : localStorage.getItem(PRODUCER_NAME_KEY) || "Producer").trim();
      return name || "Producer";
    }

    function initProducerIdentity() {
      producerClientId();
      const input = document.getElementById("producer-name-input");
      input.value = localStorage.getItem(PRODUCER_NAME_KEY) || "Producer";
      input.addEventListener("change", () => {
        localStorage.setItem(PRODUCER_NAME_KEY, currentProducerName());
      });
      input.addEventListener("blur", () => {
        localStorage.setItem(PRODUCER_NAME_KEY, currentProducerName());
      });
    }

    function text(id, value) {
      document.getElementById(id).textContent = value;
    }

    function escapeHtml(value) {
      return String(value ?? "")
        .replace(/&/g, "&amp;")
        .replace(/</g, "&lt;")
        .replace(/>/g, "&gt;")
        .replace(/"/g, "&quot;");
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

    function formatPositionDelta(value) {
      const number = Number(value || 0);
      if (!Number.isFinite(number)) return "--";
      if (number === 0) return "Even";
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

    function formatPitRoadSeconds(value) {
      const number = Number(value || 0);
      if (!Number.isFinite(number) || number <= 0) return "--";
      return `${number.toFixed(1)}s`;
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
      const leaderboard = state.producer_leaderboard || state.leaderboard || [];
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
          <div class="small">${driver.class_position ? `${escapeHtml(driver.class_name || "Class")} ${ordinal(driver.class_position)}` : formatDelta(driver.position_delta)}</div>
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
      const leaderboard = state.producer_leaderboard || state.leaderboard || [];
      return leaderboard.find(driver => driverKey(driver) === selectedCarIdx) || leaderboard[0] || null;
    }

    function renderDriverDetail(state) {
      const driver = selectedDriver(state);
      if (!driver) return;
      text("detail-number", `#${driver.car_number || "--"}`);
      text("detail-name", driver.driver_name || "Unknown Driver");
      const classLine = driver.class_position ? `${driver.class_name || "Class"} ${ordinal(driver.class_position)} of ${driver.class_size || "--"}` : "";
      text("detail-subtitle", [state.session_type || "Session", state.track_name || "the track", classLine].filter(Boolean).join(" • "));
      text("detail-position", ordinal(driver.position));
      text("detail-start", driver.starting_position ? ordinal(driver.starting_position) : "--");
      text("detail-delta", driver.starting_position ? formatPositionDelta(driver.position_delta) : "--");
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
        driver.starting_position ? `Started ${ordinal(driver.starting_position)}; ${formatPositionDelta(driver.position_delta)} from the start.` : "",
        driver.laps_led ? `Laps led: ${driver.laps_led}.` : "",
        driver.interval ? `Interval shown: ${driver.interval}.` : "",
        driver.fastest_lap ? `Fastest lap: ${driver.fastest_lap}.` : "",
        driver.class_position ? `Class position: ${ordinal(driver.class_position)} in ${driver.class_name || "class"}.` : "",
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

    function renderPitRoad(state) {
      const list = document.getElementById("pit-road-list");
      const rows = state.pit_road || [];
      list.innerHTML = "";
      if (!rows.length) {
        list.innerHTML = '<div class="small">Pit stop data will appear after cars visit pit road.</div>';
        return;
      }
      for (const row of rows.slice(0, 10)) {
        const node = document.createElement("div");
        node.className = `pit-road-row ${row.status === "On pit road" ? "pitting" : ""}`;
        const lapText = row.status === "On pit road"
          ? "Pitting"
          : row.last_pit_lap > 0
            ? `Lap ${row.last_pit_lap}`
            : "--";
        const tireText = row.laps_since_pit > 0 ? `${row.laps_since_pit} laps since stop` : "";
        node.innerHTML = `
          <div class="num">#${row.car_number || "--"}</div>
          <div>
            <div class="pit-road-main">${row.driver_name || "Unknown Driver"}</div>
            <div class="pit-road-meta">${lapText}${tireText ? " • " + tireText : ""}${row.position_summary ? " • " + row.position_summary : ""}</div>
            <div class="pit-road-service">${row.service_guess || "Service unknown"}</div>
          </div>
          <div class="small">Stop ${formatPitRoadSeconds(row.pit_stop_seconds)}<br/>Lane ${formatPitRoadSeconds(row.pit_lane_seconds)}</div>
        `;
        list.appendChild(node);
      }
    }

    function formatClock(timestamp) {
      const value = Number(timestamp || 0);
      if (!Number.isFinite(value) || value <= 0) return "";
      try {
        return new Date(value * 1000).toLocaleTimeString([], { hour: "numeric", minute: "2-digit", second: "2-digit" });
      } catch (error) {
        return "";
      }
    }

    function driverLine(item) {
      if (!item) return "";
      const number = item.car_number ? `#${item.car_number}` : "";
      const name = item.driver_name || "";
      return [number, name].filter(Boolean).join(" ");
    }

    function renderControlRoomList(listId, items, emptyText, actions = []) {
      const list = document.getElementById(listId);
      if (!list) return;
      list.innerHTML = "";
      const rows = items || [];
      if (!rows.length) {
        list.innerHTML = `<div class="small">${emptyText}</div>`;
        return;
      }
      for (const item of rows) {
        const node = document.createElement("div");
        node.className = `control-room-item ${item.kind || "note"}`;
        const title = document.createElement("div");
        title.className = "control-room-title";
        title.textContent = item.title || item.kind || "Control Room";
        const message = document.createElement("div");
        message.className = "control-room-message";
        message.textContent = item.message || "";
        const meta = document.createElement("div");
        meta.className = "control-room-meta";
        const metaPieces = [
          driverLine(item),
          item.status ? `Status: ${item.status}` : "",
          item.created_by ? `By ${item.created_by}` : "",
          formatClock(item.created_at)
        ].filter(Boolean);
        meta.textContent = metaPieces.join(" • ");
        node.appendChild(title);
        node.appendChild(message);
        node.appendChild(meta);
        const visibleActions = actions.filter(action => action.show ? action.show(item) : true);
        if (visibleActions.length) {
          const actionRow = document.createElement("div");
          actionRow.className = "mini-button-row";
          for (const action of visibleActions) {
            const button = document.createElement("button");
            button.className = `mini-button ${action.className || ""}`;
            button.textContent = action.label;
            button.addEventListener("click", () => action.handler(item));
            actionRow.appendChild(button);
          }
          node.appendChild(actionRow);
        }
        list.appendChild(node);
      }
    }

    function renderRaceEventLog(items) {
      const list = document.getElementById("race-event-log-list");
      if (!list) return;
      const rows = items || [];
      if (!rows.length) {
        list.innerHTML = `<div class="small">Race events will appear here.</div>`;
        return;
      }
      list.innerHTML = `
        <div class="event-log-row header">
          <div>Time</div>
          <div>Session</div>
          <div>Lap</div>
          <div>Driver</div>
          <div>Description</div>
          <div>Camera</div>
        </div>
      `;
      for (const item of rows) {
        const row = document.createElement("div");
        row.className = `event-log-row ${item.kind || "race_event"}`;
        row.title = item.message || "";
        row.innerHTML = `
          <div class="event-log-cell">${escapeHtml(formatClock(item.created_at) || "--")}</div>
          <div class="event-log-cell">${escapeHtml(item.session_type || "--")}</div>
          <div class="event-log-cell">${escapeHtml(item.session_lap || "--")}</div>
          <div class="event-log-cell event-log-driver">${escapeHtml(driverLine(item) || "--")}</div>
          <div class="event-log-cell event-log-desc">${escapeHtml(eventLogDescription(item))}</div>
          <div class="event-log-cell event-log-camera">
            <span class="event-log-camera-label">${escapeHtml(item.camera_group || "TV1")}</span>
          </div>
        `;
        if (item.replay_session_num !== undefined && item.replay_session_num !== null && item.replay_session_time !== undefined && item.replay_session_time !== null) {
          row.addEventListener("click", () => reviewRaceEvent(item));
          const cell = row.querySelector(".event-log-camera");
          const button = document.createElement("button");
          button.className = "mini-button";
          button.textContent = "Review";
          button.addEventListener("click", event => {
            event.stopPropagation();
            reviewRaceEvent(item);
          });
          cell.appendChild(button);
        }
        const cell = row.querySelector(".event-log-camera");
        const noteButton = document.createElement("button");
        noteButton.className = "mini-button warn";
        noteButton.textContent = "Note";
        noteButton.addEventListener("click", event => {
          event.stopPropagation();
          noteRaceEvent(item);
        });
        cell.appendChild(noteButton);
        list.appendChild(row);
      }
    }

    function eventLogDescription(item) {
      const status = item.status && item.status !== "logged" ? `[${item.status}] ` : "";
      return `${status}${item.message || item.title || ""}`;
    }

    function reviewRaceEvent(item) {
      if (!item || item.replay_session_num === undefined || item.replay_session_time === undefined) return;
      sendProducerCommand("race_event_review", {
        car_idx: item.car_idx,
        car_number: item.car_number || "",
        driver_name: item.driver_name || "",
        session_lap: item.session_lap || 0,
        replay_session_num: item.replay_session_num,
        replay_session_time: item.replay_session_time,
        pre_roll_seconds: 15
      });
    }

    function noteRaceEvent(item) {
      if (!item) return;
      const defaultDriver = driverLine(item) || "this event";
      const note = prompt("Review note for this race event:", `Review ${defaultDriver}`);
      if (note === null) return;
      sendProducerCommand("race_event_note", {
        item_id: item.id,
        status: "needs review",
        note
      });
    }

    function renderControlRoomPanels(state) {
      renderControlRoomList(
        "director-suggestions-list",
        state.director_suggestions || [],
        "Suggested camera/story targets will appear here."
      );
      renderControlRoomList(
        "producer-notes-list",
        state.producer_notes || [],
        "Manual notes will appear here.",
        [
          {
            label: "Done",
            className: "good",
            show: item => item.status !== "done",
            handler: item => sendProducerCommand("producer_note_mark", { item_id: item.id, status: "done" })
          }
        ]
      );
      renderControlRoomList(
        "interview-queue-list",
        state.interview_queue || [],
        "Interview queue will appear here.",
        [
          {
            label: "Interviewed",
            className: "good",
            show: item => item.status !== "interviewed",
            handler: item => sendProducerCommand("interview_mark", { item_id: item.id, status: "interviewed" })
          },
          {
            label: "Skip",
            className: "warn",
            show: item => item.status !== "skipped",
            handler: item => sendProducerCommand("interview_mark", { item_id: item.id, status: "skipped" })
          }
        ]
      );
      renderRaceEventLog(state.race_event_log || []);
      renderControlRoomList(
        "race-control-audit-list",
        state.race_control_audit || [],
        "Admin command details sent from Producer Assist will appear here."
      );
    }

    function controlEnabled(state, key) {
      return Boolean((state.control_state || {})[key]);
    }

    function currentLeaderboardStyle(state) {
      const controlStyle = (state.control_state || {}).leaderboard_style;
      const eventStyle = (state.event || {}).leaderboard_style;
      const style = String(controlStyle || eventStyle || "side").toLowerCase().trim();
      if (["ticker", "scroll", "top"].includes(style)) return "ticker";
      if (["flo", "flo_top", "flo-top", "top_grid"].includes(style)) return "flo";
      return "side";
    }

    function renderProducerShare(state) {
      const link = state.producer_share_url || state.producer_url || window.location.href;
      text("producer-share-link", link);
    }

    function cameraControlHeldByOther(state) {
      const holder = (state || {}).camera_control || {};
      return Boolean(holder.holder_id && holder.holder_id !== producerClientId());
    }

    function selectedManualCameraGroup() {
      const select = document.getElementById("manual-camera-group-select");
      return select ? select.value || "TV1" : "TV1";
    }

    function sendManualDriverCamera(groupName = null) {
      const driver = selectedDriver(lastState || {});
      if (!driver) return;
      const group = groupName || selectedManualCameraGroup();
      const select = document.getElementById("manual-camera-group-select");
      if (select) select.value = group;
      sendProducerCommand("camera_follow_driver", {
        car_idx: driver.car_idx,
        group_name: group
      });
    }

    function renderCameraControl(state) {
      const holder = (state || {}).camera_control || {};
      const mine = Boolean(holder.holder_id && holder.holder_id === producerClientId());
      const heldByOther = cameraControlHeldByOther(state);
      const takeButton = document.getElementById("take-camera-control-button");
      const releaseButton = document.getElementById("release-camera-control-button");
      const followButton = document.getElementById("follow-driver-button");
      const leaderButton = document.getElementById("leader-camera-button");
      const cameraShotSelect = document.getElementById("manual-camera-group-select");
      const status = document.getElementById("camera-control-status");
      if (mine) {
        status.textContent = `You have camera control as ${holder.holder_name || currentProducerName()}.`;
        takeButton.textContent = "Camera Control: Mine";
        takeButton.className = "control-button good";
      } else if (heldByOther) {
        status.textContent = `${holder.holder_name || "Another producer"} has camera control.`;
        takeButton.textContent = "Camera Control Taken";
        takeButton.className = "control-button danger";
      } else {
        status.textContent = "Camera control is open.";
        takeButton.textContent = "Take Camera Control";
        takeButton.className = "control-button";
      }
      takeButton.disabled = heldByOther || mine;
      releaseButton.disabled = !mine;
      followButton.disabled = heldByOther;
      leaderButton.disabled = heldByOther;
      if (cameraShotSelect) cameraShotSelect.disabled = heldByOther;
      for (const button of document.querySelectorAll(".camera-shot-button")) {
        button.disabled = heldByOther;
      }
    }

    function renderControlButtons(state) {
      const autoButton = document.getElementById("auto-camera-button");
      const openAiButton = document.getElementById("openai-button");
      const elevenButton = document.getElementById("elevenlabs-button");
      const leaderboardButton = document.getElementById("leaderboard-style-button");
      const raceAdminButton = document.getElementById("race-admin-button");
      const broadcasterSlider = document.getElementById("broadcaster-volume-slider");
      const musicSlider = document.getElementById("music-volume-slider");
      const autoOn = controlEnabled(state, "auto_camera");
      const openAiOn = controlEnabled(state, "openai");
      const elevenOn = controlEnabled(state, "elevenlabs");
      const raceAdminOn = controlEnabled(state, "race_admin");
      const leaderboardStyle = currentLeaderboardStyle(state);
      autoButton.textContent = autoOn ? "Auto Camera: ON" : "Auto Camera: OFF";
      openAiButton.textContent = openAiOn ? "OpenAI: ON" : "OpenAI: OFF";
      elevenButton.textContent = elevenOn ? "ElevenLabs: ON" : "ElevenLabs: OFF";
      raceAdminButton.textContent = raceAdminOn ? "Race Admin: ON" : "Race Admin: OFF";
      leaderboardButton.textContent =
        leaderboardStyle === "ticker" ? "Leaderboard: Ticker" :
        leaderboardStyle === "flo" ? "Leaderboard: Flo Top" :
        "Leaderboard: Side";
      autoButton.className = `control-button ${autoOn ? "good" : "danger"}`;
      openAiButton.className = `control-button ${openAiOn ? "good" : "danger"}`;
      elevenButton.className = `control-button ${elevenOn ? "good" : "danger"}`;
      raceAdminButton.className = `control-button ${raceAdminOn ? "good" : "danger"}`;
      leaderboardButton.className = `control-button ${leaderboardStyle !== "side" ? "good" : ""}`;
      renderAudioSliders(state, broadcasterSlider, musicSlider);
      renderRaceControl(state);
    }

    function renderAudioSliders(state, broadcasterSlider, musicSlider) {
      const control = state.control_state || {};
      setVolumeSlider(broadcasterSlider, "broadcaster-volume-label", control.broadcaster_volume ?? 65);
      setVolumeSlider(musicSlider, "music-volume-label", control.music_volume ?? 65);
    }

    function setVolumeSlider(slider, labelId, value) {
      if (!slider) return;
      const volume = Math.max(0, Math.min(100, Number(value || 0)));
      if (document.activeElement !== slider) slider.value = String(volume);
      text(labelId, `${Math.round(volume)}%`);
    }

    function renderRaceControl(state) {
      const enabled = controlEnabled(state, "race_admin");
      const status = document.getElementById("race-admin-status");
      status.textContent = enabled ? "Race Admin Mode is ON" : "Race Admin Mode is OFF";
      status.className = `race-admin-status ${enabled ? "on" : ""}`;
      const driver = selectedDriver(state || {});
      for (const button of document.querySelectorAll(".race-control-button")) {
        const driverRequired = button.dataset.driverRequired === "true";
        button.disabled = !enabled || (driverRequired && !driver);
      }
    }

    function raceControlPayload(action, driver, driverRequired = false) {
      const payload = { action };
      if (driverRequired && driver) {
        payload.car_idx = driver.car_idx;
        payload.car_number = driver.car_number || "";
        payload.driver_name = driver.driver_name || "";
      }
      if (action === "timed_black") {
        const rawSeconds = prompt("Black flag penalty seconds:", "15");
        if (rawSeconds === null) return null;
        payload.seconds = Number(rawSeconds) || 15;
      }
      return payload;
    }

    function confirmRaceControl(button, action, driver) {
      if (button.dataset.dangerous !== "true") return true;
      const driverText = button.dataset.driverRequired === "true" && driver ? ` for #${driver.car_number || "--"} ${driver.driver_name || ""}` : "";
      return confirm(`Send race-control command "${button.textContent}"${driverText}?`);
    }

    async function sendProducerCommand(command, payload = {}) {
      try {
        const finalPayload = {
          ...payload,
          client_id: producerClientId(),
          producer_name: currentProducerName()
        };
        await fetch("/producer/command", {
          method: "POST",
          headers: { "Content-Type": "application/json" },
          body: JSON.stringify({ command, payload: finalPayload })
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
      renderPitRoad(state);
      renderControlRoomPanels(state);
      renderProducerFeed(state);
      renderProducerShare(state);
      renderCameraControl(state);
      renderControlButtons(state);
    }

    document.getElementById("take-camera-control-button").addEventListener("click", () => {
      sendProducerCommand("camera_claim");
    });
    document.getElementById("release-camera-control-button").addEventListener("click", () => {
      sendProducerCommand("camera_release");
    });
    document.getElementById("follow-driver-button").addEventListener("click", () => {
      sendManualDriverCamera();
    });
    for (const button of document.querySelectorAll(".camera-shot-button")) {
      button.addEventListener("click", () => {
        sendManualDriverCamera(button.dataset.cameraGroup || "TV1");
      });
    }
    document.getElementById("leader-camera-button").addEventListener("click", () => {
      sendProducerCommand("camera_follow_leader");
    });
    document.getElementById("manual-crank-it-up-button").addEventListener("click", () => {
      sendProducerCommand("producer_crank_it_up");
    });
    document.getElementById("manual-sponsor-button").addEventListener("click", () => {
      sendProducerCommand("producer_sponsor_commercial");
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
    document.getElementById("race-admin-button").addEventListener("click", () => {
      const on = controlEnabled(lastState || {}, "race_admin");
      sendProducerCommand(on ? "race_admin_off" : "race_admin_on");
    });
    document.getElementById("leaderboard-style-button").addEventListener("click", () => {
      const style = currentLeaderboardStyle(lastState || {});
      const nextCommand =
        style === "side" ? "leaderboard_ticker" :
        style === "ticker" ? "leaderboard_flo" :
        "leaderboard_side";
      sendProducerCommand(nextCommand);
    });
    setupVolumeSlider("broadcaster-volume-slider", "broadcaster-volume-label", "broadcaster");
    setupVolumeSlider("music-volume-slider", "music-volume-label", "music");
    for (const button of document.querySelectorAll(".race-control-button")) {
      button.addEventListener("click", () => {
        const action = button.dataset.raceAction;
        const driver = selectedDriver(lastState || {});
        if (button.dataset.driverRequired === "true" && !driver) {
          alert("Select a driver from the leaderboard first.");
          return;
        }
        if (!confirmRaceControl(button, action, driver)) return;
        const payload = raceControlPayload(action, driver, button.dataset.driverRequired === "true");
        if (!payload) return;
        sendProducerCommand("race_control", payload);
      });
    }

    function setupVolumeSlider(sliderId, labelId, target) {
      const slider = document.getElementById(sliderId);
      if (!slider) return;
      const send = () => {
        const volume = Math.max(0, Math.min(100, Number(slider.value || 0)));
        text(labelId, `${Math.round(volume)}%`);
        sendProducerCommand("set_audio_volume", { target, volume });
      };
      slider.addEventListener("input", () => {
        text(labelId, `${Math.round(Number(slider.value || 0))}%`);
      });
      slider.addEventListener("change", send);
      slider.addEventListener("pointerup", send);
    }
    document.getElementById("add-producer-note-button").addEventListener("click", () => {
      const input = document.getElementById("producer-note-input");
      const message = (input.value || "").trim();
      if (!message) return;
      sendProducerCommand("producer_note_add", { message });
      input.value = "";
    });
    document.getElementById("add-driver-note-button").addEventListener("click", () => {
      const driver = selectedDriver(lastState || {});
      const input = document.getElementById("producer-note-input");
      const message = (input.value || "").trim();
      if (!driver || !message) {
        alert("Select a driver and type a note first.");
        return;
      }
      sendProducerCommand("producer_note_add", {
        message,
        car_idx: driver.car_idx,
        car_number: driver.car_number || "",
        driver_name: driver.driver_name || ""
      });
      input.value = "";
    });
    document.getElementById("queue-interview-button").addEventListener("click", () => {
      const driver = selectedDriver(lastState || {});
      if (!driver) {
        alert("Select a driver from the leaderboard first.");
        return;
      }
      sendProducerCommand("interview_queue_add", {
        message: `Queued for post-race interview from ${ordinal(driver.position)}.`,
        car_idx: driver.car_idx,
        car_number: driver.car_number || "",
        driver_name: driver.driver_name || ""
      });
    });
    document.getElementById("queue-top-three-button").addEventListener("click", () => {
      const leaderboard = (lastState || {}).leaderboard || [];
      for (const driver of leaderboard.slice(0, 3)) {
        sendProducerCommand("interview_queue_add", {
          message: `Top-three interview queue from ${ordinal(driver.position)}.`,
          car_idx: driver.car_idx,
          car_number: driver.car_number || "",
          driver_name: driver.driver_name || ""
        });
      }
    });
    document.getElementById("return-live-button").addEventListener("click", () => {
      sendProducerCommand("replay_return_live");
    });
    document.getElementById("pause-replay-button").addEventListener("click", () => {
      sendProducerCommand("replay_pause");
    });
    document.getElementById("play-replay-button").addEventListener("click", () => {
      sendProducerCommand("replay_normal_speed");
    });
    document.getElementById("rewind-button").addEventListener("click", () => {
      sendProducerCommand("replay_reverse");
    });
    document.getElementById("slow-motion-button").addEventListener("click", () => {
      sendProducerCommand("replay_slow_motion");
    });
    document.getElementById("fast-forward-button").addEventListener("click", () => {
      sendProducerCommand("replay_fast_play");
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

    initProducerIdentity();
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
      height: 84px;
      display: grid;
      grid-template-columns: minmax(205px, 315px) minmax(360px, 1fr) minmax(320px, 430px);
      align-items: center;
      gap: 22px;
      padding: 0 26px;
      background:
        linear-gradient(90deg, rgba(215, 25, 32, 0.18), transparent 28%, rgba(255, 255, 255, 0.06) 52%, transparent 75%),
        linear-gradient(90deg, rgba(7, 9, 13, 0.97), rgba(24, 30, 42, 0.93));
      border-bottom: 4px solid var(--rgc-red);
      box-shadow: 0 14px 34px rgba(0, 0, 0, 0.42), inset 0 1px 0 rgba(255, 255, 255, 0.10);
      letter-spacing: 0.02em;
    }

    .session-center {
      position: absolute;
      left: 50%;
      top: 116px;
      transform: translateX(-50%);
      width: auto;
      min-width: 264px;
      max-width: 520px;
      box-sizing: border-box;
      padding: 8px 14px;
      border-radius: 999px;
      background: linear-gradient(90deg, rgba(215, 25, 32, 0.92), rgba(7, 9, 13, 0.88));
      border: 1px solid rgba(255, 255, 255, 0.26);
      box-shadow: 0 0 22px rgba(215, 25, 32, 0.34);
      color: #ffffff;
      text-align: center;
      font-size: 18px;
      font-weight: 950;
      text-transform: uppercase;
      letter-spacing: 0.07em;
      white-space: nowrap;
      z-index: 21;
    }

    body.leaderboard-ticker-mode .session-center {
      top: 176px;
    }

    body.leaderboard-flo-mode .top-banner {
      top: 12px;
      height: 40px;
      grid-template-columns: 1fr;
      padding: 0 18px;
    }

    body.leaderboard-flo-mode .title-side,
    body.leaderboard-flo-mode .title-right,
    body.leaderboard-flo-mode #series {
      display: none;
    }

    body.leaderboard-flo-mode .event-title {
      font-size: 21px;
      letter-spacing: 0.08em;
    }

    body.leaderboard-flo-mode .session-center {
      top: 188px;
    }

    .caution-status {
      position: absolute;
      left: 50%;
      top: 118px;
      transform: translateX(-50%);
      box-sizing: border-box;
      min-width: 250px;
      padding: 9px 28px;
      border-radius: 999px;
      background:
        linear-gradient(90deg, rgba(255, 212, 0, 0.96), rgba(255, 235, 90, 0.96));
      color: #141414;
      border: 2px solid rgba(20, 20, 20, 0.38);
      box-shadow:
        0 0 26px rgba(255, 212, 0, 0.54),
        0 10px 26px rgba(0, 0, 0, 0.35);
      text-align: center;
      font-size: 20px;
      font-weight: 950;
      text-transform: uppercase;
      letter-spacing: 0.12em;
      z-index: 24;
      pointer-events: none;
      animation: cautionStatusPulse 0.95s infinite alternate ease-in-out;
    }

    body.leaderboard-ticker-mode .caution-status {
      top: 176px;
    }

    body.leaderboard-flo-mode .caution-status {
      top: 204px;
    }

    @keyframes cautionStatusPulse {
      from {
        filter: brightness(0.96);
        box-shadow: 0 0 18px rgba(255, 212, 0, 0.44), 0 10px 26px rgba(0, 0, 0, 0.35);
      }
      to {
        filter: brightness(1.10);
        box-shadow: 0 0 34px rgba(255, 212, 0, 0.76), 0 10px 26px rgba(0, 0, 0, 0.35);
      }
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
      font-size: 27px;
      font-weight: 950;
      text-transform: uppercase;
      white-space: nowrap;
      letter-spacing: 0.045em;
      text-shadow: 0 2px 8px rgba(0, 0, 0, 0.66);
    }

    .title-side {
      display: grid;
      align-items: center;
      gap: 4px;
      min-width: 0;
    }

    .title-center {
      min-width: 0;
      text-align: center;
      display: flex;
      flex-direction: column;
      align-items: center;
      justify-content: center;
      gap: 4px;
    }

    .title-right {
      min-width: 0;
      display: flex;
      flex-direction: column;
      align-items: flex-end;
      justify-content: center;
      gap: 4px;
    }

    .brand-graphic {
      max-width: 220px;
      max-height: 58px;
      object-fit: contain;
      filter: drop-shadow(0 8px 14px rgba(0, 0, 0, 0.62));
      opacity: 0.98;
    }

    .cause-line {
      color: #ffffff;
      font-size: 11px;
      font-weight: 950;
      letter-spacing: 0.08em;
      text-transform: uppercase;
      padding: 4px 9px;
      border-radius: 999px;
      background: rgba(7, 9, 13, 0.62);
      border: 1px solid rgba(255, 255, 255, 0.18);
      box-shadow: 0 0 16px rgba(255, 255, 255, 0.10);
      max-width: 220px;
      overflow: hidden;
      text-overflow: ellipsis;
      white-space: nowrap;
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
      font-size: 12px;
      padding-right: 0;
      margin-top: 2px;
      opacity: 0.88;
      max-width: 100%;
      overflow: hidden;
      text-overflow: ellipsis;
    }

    .track-pill {
      color: #ffffff;
      font-weight: 950;
      font-size: 17px;
      max-width: 100%;
      overflow: hidden;
      text-overflow: ellipsis;
      padding: 6px 14px;
      border-radius: 999px;
      background: rgba(255, 255, 255, 0.08);
      border: 1px solid rgba(255, 255, 255, 0.16);
      box-shadow: inset 0 1px 0 rgba(255, 255, 255, 0.08);
    }

    .leaderboard {
      position: absolute;
      left: 24px;
      top: 134px;
      width: 264px;
      background:
        linear-gradient(180deg, rgba(255, 255, 255, 0.07), transparent 18%),
        var(--rgc-panel);
      box-shadow: 0 14px 34px rgba(0, 0, 0, 0.40);
      border-left: 5px solid var(--rgc-red);
      border-top: 1px solid rgba(255, 255, 255, 0.12);
    }

    body.leaderboard-ticker-mode .leaderboard {
      display: none;
    }

    body.leaderboard-flo-mode .leaderboard {
      display: none;
    }

    .leaderboard-header {
      display: grid;
      grid-template-columns: 1fr auto;
      gap: 8px;
      padding: 8px 10px;
      background:
        linear-gradient(90deg, rgba(215, 25, 32, 0.22), transparent 72%),
        var(--rgc-dark);
      border-bottom: 4px solid var(--rgc-line);
      text-transform: uppercase;
      font-weight: 800;
      letter-spacing: 0.055em;
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
      gap: 0;
      height: 11px;
      margin: 7px 8px 8px;
      padding: 0;
      background: rgba(0, 0, 0, 0.28);
      border: 1px solid rgba(255, 255, 255, 0.12);
      border-bottom: 1px solid rgba(255, 255, 255, 0.08);
      max-width: 100%;
      box-sizing: border-box;
      overflow: hidden;
      border-radius: 999px;
    }

    .lap-history-segment {
      height: 100%;
      flex: 0 1 auto;
      min-width: 0;
      border-radius: 0;
      background: rgba(255, 255, 255, 0.18);
    }

    .leaderboard-series {
      padding: 7px 10px 8px;
      background: linear-gradient(90deg, rgba(215, 25, 32, 0.22), rgba(255, 255, 255, 0.04));
      border-top: 1px solid rgba(255, 255, 255, 0.12);
      color: #ffffff;
      font-size: 11px;
      font-weight: 900;
      letter-spacing: 0.08em;
      text-transform: uppercase;
      white-space: nowrap;
      overflow: hidden;
      text-overflow: ellipsis;
    }

    .ticker-leaderboard {
      position: absolute;
      left: 24px;
      right: 24px;
      top: 118px;
      height: 50px;
      display: grid;
      grid-template-columns: auto auto minmax(0, 1fr);
      align-items: center;
      gap: 12px;
      padding: 0 16px;
      background:
        linear-gradient(90deg, rgba(255, 255, 255, 0.06), transparent 36%, rgba(255, 255, 255, 0.05) 62%, transparent),
        linear-gradient(90deg, rgba(7, 9, 13, 0.97), rgba(24, 30, 42, 0.93));
      border-left: 0;
      border-bottom: 2px solid rgba(255, 255, 255, 0.16);
      box-shadow: 0 12px 30px rgba(0, 0, 0, 0.38);
      overflow: hidden;
      text-transform: uppercase;
    }

    .ticker-leaderboard.hidden {
      display: none;
    }

    .flo-leaderboard {
      position: absolute;
      left: 24px;
      right: 24px;
      top: 62px;
      height: 116px;
      display: grid;
      grid-template-columns: 210px minmax(0, 1fr) 210px;
      background:
        linear-gradient(90deg, rgba(255, 255, 255, 0.08), transparent 35%, rgba(255, 255, 255, 0.05) 65%, transparent),
        linear-gradient(90deg, rgba(7, 9, 13, 0.96), rgba(24, 30, 42, 0.92));
      border: 1px solid rgba(255, 255, 255, 0.22);
      border-bottom: 3px solid rgba(255, 255, 255, 0.18);
      box-shadow: 0 14px 34px rgba(0, 0, 0, 0.44);
      overflow: visible;
      z-index: 22;
      text-transform: uppercase;
    }

    .flo-leaderboard.hidden {
      display: none;
    }

    .flo-leaderboard.caution {
      border-color: #ffd400;
      border-bottom-color: #ffd400;
      box-shadow:
        0 14px 34px rgba(0, 0, 0, 0.44),
        0 0 28px rgba(255, 212, 0, 0.52),
        inset 0 0 0 2px rgba(255, 212, 0, 0.74);
    }

    .flo-brand,
    .flo-series {
      position: relative;
      display: grid;
      align-items: center;
      justify-items: center;
      align-content: center;
      gap: 4px;
      padding: 9px 14px;
      background:
        linear-gradient(180deg, rgba(255, 255, 255, 0.08), rgba(0, 0, 0, 0.20)),
        rgba(7, 9, 13, 0.92);
      color: #fff;
      min-width: 0;
      border-left: 1px solid rgba(255, 255, 255, 0.16);
      border-right: 1px solid rgba(255, 255, 255, 0.16);
    }

    .flo-brand img,
    .flo-series img {
      max-width: 184px;
      max-height: 72px;
      object-fit: contain;
      filter:
        drop-shadow(0 7px 12px rgba(0, 0, 0, 0.70))
        drop-shadow(0 0 12px rgba(255, 255, 255, 0.12));
    }

    .flo-series-text {
      color: #ffffff;
      font-size: 12px;
      font-weight: 950;
      letter-spacing: 0.07em;
      text-align: center;
      line-height: 1.1;
      max-width: 184px;
      overflow: hidden;
      text-overflow: ellipsis;
      text-shadow: 0 2px 8px rgba(0, 0, 0, 0.62);
    }

    .flo-lap-box {
      position: absolute;
      left: 0;
      top: 100%;
      display: grid;
      grid-template-columns: auto 62px;
      align-items: stretch;
      height: 36px;
      border: 1px solid rgba(255, 255, 255, 0.20);
      box-shadow: 0 8px 18px rgba(0, 0, 0, 0.36);
    }

    .flo-lap-label {
      display: flex;
      align-items: center;
      padding: 0 16px;
      background: rgba(7, 9, 13, 0.94);
      color: #fff;
      font-size: 15px;
      font-weight: 950;
      letter-spacing: 0.05em;
      white-space: nowrap;
    }

    .flo-lap-value {
      display: flex;
      align-items: center;
      justify-content: center;
      background: #15c85f;
      color: #06110a;
      font-size: 22px;
      font-weight: 950;
      min-width: 62px;
    }

    .flo-leaderboard.caution .flo-lap-value {
      background: #ffd400;
      color: #16130a;
    }

    .flo-grid {
      display: grid;
      grid-template-rows: 1fr 1fr 1fr;
      min-width: 0;
    }

    .flo-row {
      display: grid;
      grid-template-columns: repeat(5, minmax(0, 1fr));
      min-width: 0;
    }

    .flo-row-cycle {
      position: relative;
      box-shadow:
        inset 0 3px 0 rgba(255, 255, 255, 0.78),
        inset 0 -3px 0 rgba(7, 9, 13, 0.38);
    }

    .flo-row-cycle::before {
      content: "CYCLE";
      position: absolute;
      left: 0;
      bottom: -18px;
      padding: 3px 9px;
      background: rgba(255, 255, 255, 0.92);
      color: #111;
      font-size: 10px;
      font-weight: 950;
      letter-spacing: 0.12em;
      border-radius: 0 0 5px 5px;
    }

    .flo-entry {
      display: grid;
      grid-template-columns: auto auto minmax(0, 1fr) auto;
      gap: 8px;
      align-items: center;
      min-width: 0;
      padding: 0 11px;
      border-left: 1px solid rgba(255, 255, 255, 0.20);
      border-bottom: 1px solid rgba(255, 255, 255, 0.16);
      background: linear-gradient(180deg, rgba(255, 255, 255, 0.08), rgba(0, 0, 0, 0.20));
    }

    .flo-row-cycle .flo-entry {
      background:
        linear-gradient(180deg, rgba(255, 255, 255, 1), rgba(214, 224, 232, 0.98));
      color: #111;
      border-left-color: rgba(0, 0, 0, 0.30);
      border-bottom-color: rgba(0, 0, 0, 0.22);
      box-shadow:
        inset 0 1px 0 rgba(255, 255, 255, 0.95),
        inset 0 0 0 1px rgba(255, 255, 255, 0.28);
    }

    .flo-position {
      min-width: 29px;
      height: 25px;
      display: flex;
      align-items: center;
      justify-content: center;
      background: rgba(255, 255, 255, 0.08);
      border: 1px solid rgba(255, 255, 255, 0.26);
      color: #fff;
      font-size: 15px;
      font-weight: 950;
    }

    .flo-row-cycle .flo-position {
      background: #05070b;
      border-color: rgba(0, 0, 0, 0.55);
      color: #fff;
    }

    .flo-number {
      color: #dfe5ef;
      font-size: 14px;
      font-weight: 950;
      white-space: nowrap;
    }

    .flo-row-cycle .flo-number,
    .flo-row-cycle .flo-name,
    .flo-row-cycle .flo-gap {
      color: #111;
    }

    .flo-name {
      min-width: 0;
      overflow: hidden;
      text-overflow: ellipsis;
      white-space: nowrap;
      color: #fff;
      font-size: 17px;
      font-weight: 950;
      letter-spacing: 0.04em;
    }

    .flo-gap {
      color: var(--rgc-muted);
      font-size: 11px;
      font-weight: 900;
      white-space: nowrap;
    }

    .ticker-leaderboard.green {
      border-bottom-color: #15c85f;
      box-shadow: inset 0 -9px 16px rgba(21, 200, 95, 0.20), 0 12px 30px rgba(0, 0, 0, 0.38);
    }

    .ticker-leaderboard.caution {
      border-bottom-color: #ffd400;
    }

    .ticker-label {
      font-size: 14px;
      font-weight: 950;
      letter-spacing: 0.08em;
      color: #fff;
      white-space: nowrap;
      padding: 7px 11px;
      border-radius: 999px;
      background: rgba(255, 255, 255, 0.10);
      box-shadow: inset 0 1px 0 rgba(255, 255, 255, 0.14);
    }

    .ticker-window {
      min-width: 0;
      overflow: hidden;
      white-space: nowrap;
    }

    .ticker-track {
      display: inline-flex;
      align-items: center;
      gap: 24px;
      min-width: max-content;
      animation: tickerScroll 62s linear infinite;
    }

    .ticker-item {
      display: inline-flex;
      align-items: center;
      gap: 7px;
      font-size: 14px;
      font-weight: 800;
      color: var(--rgc-text);
      white-space: nowrap;
    }

    .ticker-reset {
      display: inline-flex;
      align-items: center;
      gap: 8px;
      padding: 4px 13px;
      border-radius: 999px;
      background: linear-gradient(90deg, rgba(215, 25, 32, 0.90), rgba(255, 255, 255, 0.16));
      border: 1px solid rgba(255, 255, 255, 0.30);
      color: #ffffff;
      font-size: 12px;
      font-weight: 950;
      letter-spacing: 0.12em;
    }

    .ticker-reset::before,
    .ticker-reset::after {
      content: "";
      width: 28px;
      height: 2px;
      background: rgba(255, 255, 255, 0.72);
    }

    .ticker-pos {
      color: #ffffff;
      font-weight: 950;
      font-size: 15px;
      min-width: 30px;
      text-align: right;
      padding: 0;
      border-radius: 0;
      background: transparent;
      border: 0;
    }

    .ticker-num {
      background: #fff;
      color: #111;
      border: 1px solid rgba(0, 0, 0, 0.55);
      border-radius: 3px;
      padding: 1px 5px;
      font-weight: 950;
    }

    .ticker-gap {
      color: var(--rgc-muted);
      font-size: 14px;
      font-weight: 900;
      min-width: 50px;
      text-align: right;
    }

    @keyframes tickerScroll {
      from { transform: translateX(0); }
      to { transform: translateX(-50%); }
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
      border: 1px solid rgba(0, 0, 0, 0.55);
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
      grid-template-columns: 104px minmax(0, 178px) 1fr;
      background: linear-gradient(90deg, rgba(7, 9, 13, 0.96), rgba(24, 30, 42, 0.92));
      border-left: 6px solid var(--rgc-red);
      box-shadow: 0 14px 34px rgba(0, 0, 0, 0.42);
      text-transform: uppercase;
      overflow: hidden;
    }

    .driver-card-position-rank {
      display: flex;
      flex-direction: column;
      align-items: center;
      justify-content: center;
      background: linear-gradient(180deg, #f4f7fb, #b9c1ce);
      color: #10131a;
      border-right: 1px solid rgba(0, 0, 0, 0.45);
    }

    .driver-card-position-rank .rank {
      font-weight: 950;
      font-size: 40px;
      line-height: 0.95;
      letter-spacing: -0.05em;
    }

    .driver-card-position-rank .label {
      margin-top: 6px;
      font-size: 11px;
      font-weight: 900;
      letter-spacing: 0.14em;
      color: rgba(16, 19, 26, 0.72);
    }

    .driver-card-image {
      position: relative;
      min-height: 74px;
      background: radial-gradient(circle at 50% 36%, rgba(255, 255, 255, 0.10), rgba(0, 0, 0, 0.34) 65%),
        linear-gradient(135deg, rgba(15, 20, 30, 0.95), rgba(5, 7, 12, 0.96));
      border-left: 1px solid rgba(0, 0, 0, 0.32);
      border-right: 1px solid rgba(255, 255, 255, 0.12);
      overflow: hidden;
    }

    .driver-card-image img {
      width: 100%;
      height: 100%;
      min-height: 74px;
      object-fit: contain;
      object-position: center;
      display: block;
      filter: drop-shadow(0 8px 10px rgba(0, 0, 0, 0.42));
    }

    .driver-card-image.image-failed img,
    .driver-card-image.image-loading img,
    .driver-card-image.no-source img {
      display: none;
    }

    .driver-card-number {
      position: absolute;
      left: 8px;
      bottom: 7px;
      min-width: 44px;
      padding: 3px 9px;
      border-radius: 8px;
      border: 2px solid rgba(0, 0, 0, 0.48);
      background: rgba(255, 255, 255, 0.94);
      color: #111;
      font-weight: 950;
      font-size: 22px;
      line-height: 1;
      text-align: center;
      box-shadow: 0 7px 14px rgba(0, 0, 0, 0.36);
    }

    .driver-card-image.image-failed .driver-card-number,
    .driver-card-image.image-loading .driver-card-number,
    .driver-card-image.no-source .driver-card-number {
      position: absolute;
      inset: 0;
      display: flex;
      align-items: center;
      justify-content: center;
      border-radius: 0;
      padding: 0;
      min-width: 0;
      background: transparent;
      color: rgba(255, 255, 255, 0.95);
      font-size: 42px;
      border: 0;
      text-shadow: 0 4px 14px rgba(0, 0, 0, 0.66);
      box-shadow: none;
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

    .driver-card-country {
      margin-top: 1px;
      color: #f4d06f;
      font-size: 12px;
      font-weight: 900;
      letter-spacing: 0.12em;
      white-space: nowrap;
      overflow: hidden;
      text-overflow: ellipsis;
      display: flex;
      align-items: center;
      gap: 6px;
    }

    .driver-card-flag {
      width: 21px;
      height: 14px;
      object-fit: cover;
      border-radius: 2px;
      box-shadow: 0 0 0 1px rgba(255, 255, 255, 0.24), 0 2px 6px rgba(0, 0, 0, 0.42);
      flex: 0 0 auto;
    }

    .driver-card-country-text {
      overflow: hidden;
      text-overflow: ellipsis;
    }

    .driver-card-position {
      margin-top: 2px;
      color: #fff;
      font-size: 14px;
      font-weight: 900;
      letter-spacing: 0.08em;
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

    .studio-stamp {
      position: absolute;
      left: 18px;
      bottom: 18px;
      width: 74px;
      height: 74px;
      padding: 5px;
      box-sizing: border-box;
      border-radius: 18px;
      background: rgba(4, 6, 10, 0.42);
      border: 1px solid rgba(255, 255, 255, 0.14);
      box-shadow:
        0 10px 22px rgba(0, 0, 0, 0.34),
        inset 0 1px 0 rgba(255, 255, 255, 0.08);
      opacity: 0.78;
      z-index: 18;
      pointer-events: none;
    }

    .studio-stamp img {
      width: 100%;
      height: 100%;
      display: block;
      object-fit: contain;
      filter: drop-shadow(0 4px 8px rgba(0, 0, 0, 0.44));
    }

    body.leaderboard-ticker-mode .studio-stamp,
    body.leaderboard-flo-mode .studio-stamp {
      left: 20px;
      bottom: 16px;
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

    .stat-panel.points_standings {
      width: 540px;
      bottom: 42px;
      border-left-color: #39a7ff;
      background: linear-gradient(90deg, rgba(7, 11, 19, 0.97), rgba(18, 36, 58, 0.95));
    }

    .stat-panel.pit_update {
      border-left-color: #ffd400;
    }

    .stat-panel.race_end_cap {
      right: 34px;
      bottom: 74px;
      transform: none;
      width: 520px;
      border-left-color: #ffffff;
      box-shadow: 0 18px 42px rgba(0, 0, 0, 0.50), 0 0 24px rgba(255, 255, 255, 0.10);
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

    .stat-panel.points_standings .stat-panel-title {
      font-size: 21px;
    }

    .stat-panel.points_standings .stat-panel-row {
      padding: 5px 12px;
      grid-template-columns: minmax(0, 1fr) 58px;
      gap: 8px;
    }

    .stat-panel.points_standings .stat-panel-label {
      font-size: 12px;
    }

    .stat-panel.points_standings .stat-panel-value {
      font-size: 14px;
      color: #9ed8ff;
    }

    .stat-panel.points_standings .stat-panel-detail {
      font-size: 10px;
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
      left: auto;
      right: 48px;
      top: 166px;
      width: 264px;
      height: 264px;
      justify-content: flex-end;
    }

    body.leaderboard-ticker-mode .special-presentation.race_sponsors {
      left: auto;
      right: 48px;
      top: 226px;
      width: 264px;
      height: 264px;
    }

    body.leaderboard-flo-mode .special-presentation.race_sponsors {
      left: auto;
      right: 48px;
      top: 242px;
      width: 264px;
      height: 264px;
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

    body.leaderboard-ticker-mode .special-presentation.sponsor_bug {
      top: 224px;
    }

    body.leaderboard-flo-mode .special-presentation.sponsor_bug {
      top: 242px;
    }

    .special-presentation.sponsor_commercial {
      inset: 0;
      width: auto;
      height: auto;
      z-index: 80;
      background: #000;
      justify-content: center;
      animation: none;
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
      grid-template-columns: 1fr;
      gap: 10px;
      width: 264px;
      height: 264px;
      padding: 18px;
      border-left-width: 4px;
      border-top: 4px solid var(--rgc-red);
      background: linear-gradient(90deg, rgba(7, 9, 13, 0.88), rgba(24, 30, 42, 0.78));
      text-align: center;
      justify-items: center;
      align-content: center;
    }

    .special-presentation.sponsor_bug .ceremony-card {
      grid-template-columns: 118px 1fr;
      gap: 14px;
      width: 360px;
      padding: 10px 14px;
      border-left-width: 4px;
      background: linear-gradient(90deg, rgba(7, 9, 13, 0.92), rgba(24, 30, 42, 0.82));
    }

    .special-presentation.sponsor_commercial .ceremony-card {
      position: absolute;
      left: 50%;
      bottom: 34px;
      transform: translateX(-50%);
      grid-template-columns: 82px 1fr;
      gap: 14px;
      width: min(520px, calc(100% - 80px));
      padding: 10px 16px;
      background: linear-gradient(90deg, rgba(7, 9, 13, 0.76), rgba(24, 30, 42, 0.62));
      border-left-width: 4px;
      z-index: 2;
    }

    .ceremony-logo {
      width: 210px;
      height: 116px;
      object-fit: contain;
      filter: drop-shadow(0 10px 18px rgba(0, 0, 0, 0.62));
    }

    .special-presentation.race_sponsors .ceremony-logo {
      width: 186px;
      height: 112px;
    }

    .special-presentation.sponsor_bug .ceremony-logo {
      width: 112px;
      height: 62px;
    }

    .special-presentation.sponsor_commercial .ceremony-logo {
      width: 76px;
      height: 46px;
    }

    .ceremony-title {
      font-size: 40px;
      font-weight: 950;
      letter-spacing: 0.05em;
    }

    .special-presentation.race_sponsors .ceremony-title {
      font-size: 22px;
      letter-spacing: 0.04em;
    }

    .special-presentation.sponsor_bug .ceremony-title {
      font-size: 18px;
      letter-spacing: 0.035em;
    }

    .special-presentation.sponsor_commercial .ceremony-title {
      font-size: 20px;
      letter-spacing: 0.04em;
    }

    .ceremony-subtitle {
      margin-top: 14px;
      color: var(--rgc-muted);
      font-size: 18px;
      font-weight: 800;
      letter-spacing: 0.08em;
    }

    .special-presentation.race_sponsors .ceremony-subtitle {
      margin-top: 5px;
      font-size: 12px;
      letter-spacing: 0.06em;
      line-height: 1.25;
    }

    .special-presentation.sponsor_bug .ceremony-subtitle {
      margin-top: 4px;
      font-size: 11px;
      letter-spacing: 0.05em;
    }

    .special-presentation.sponsor_commercial .ceremony-subtitle {
      margin-top: 3px;
      font-size: 11px;
      letter-spacing: 0.05em;
    }

    .commercial-video {
      display: none;
      position: absolute;
      inset: 0;
      width: 100%;
      height: 100%;
      object-fit: contain;
      background: #000;
    }

    .special-presentation.sponsor_commercial .commercial-video {
      display: block;
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
      <div id="cause-line" class="cause-line hidden"></div>
    </div>
    <div class="title-center">
      <div id="event-title" class="event-title">RGC AI Broadcast</div>
      <div id="series" class="event-meta"></div>
    </div>
    <div class="event-meta title-right">
      <span id="track" class="track-pill">Waiting for iRacing</span>
      <span id="sponsor" class="sponsor"></span>
    </div>
  </section>

  <div id="session-center" class="session-center hidden"></div>
  <div id="caution-status" class="caution-status hidden">Under Caution</div>

  <section id="leaderboard" class="leaderboard">
    <div class="leaderboard-header">
      <span>Leaderboard</span>
      <span id="lap" class="lap">Lap --</span>
    </div>
    <div id="lap-history" class="lap-history hidden"></div>
    <div id="leaderboard-rows"></div>
    <div id="leaderboard-series" class="leaderboard-series hidden"></div>
  </section>

  <section id="ticker-leaderboard" class="ticker-leaderboard hidden">
    <div id="ticker-label" class="ticker-label">Leaderboard</div>
    <div id="ticker-lap" class="lap">Lap --</div>
    <div class="ticker-window">
      <div id="ticker-track" class="ticker-track"></div>
    </div>
  </section>

  <section id="flo-leaderboard" class="flo-leaderboard hidden">
    <div class="flo-brand">
      <img id="flo-sponsor-logo" alt="" />
      <div class="flo-lap-box">
        <div id="flo-lap-label" class="flo-lap-label">Lap</div>
        <div id="flo-lap-value" class="flo-lap-value">--</div>
      </div>
    </div>
    <div class="flo-grid">
      <div id="flo-row-top" class="flo-row flo-row-top"></div>
      <div id="flo-row-second" class="flo-row flo-row-second"></div>
      <div id="flo-row-cycle" class="flo-row flo-row-cycle"></div>
    </div>
    <div class="flo-series">
      <img id="flo-series-logo" alt="" />
      <div id="flo-series-text" class="flo-series-text"></div>
    </div>
  </section>

  <section id="driver-card" class="driver-card hidden">
    <div class="driver-card-position-rank">
      <div id="driver-card-position-rank" class="rank">P--</div>
      <div class="label">Position</div>
    </div>
    <div id="driver-card-image" class="driver-card-image no-source">
      <img id="driver-card-car-img" alt="" />
      <div id="driver-card-number" class="driver-card-number"></div>
    </div>
    <div class="driver-card-info">
      <div id="driver-card-name" class="driver-card-name"></div>
      <div id="driver-card-position" class="driver-card-position"></div>
      <div id="driver-card-story" class="driver-card-story"></div>
      <div id="driver-card-country" class="driver-card-country"></div>
    </div>
  </section>

  <section id="stat-panel" class="stat-panel hidden">
    <div class="stat-panel-header">
      <div id="stat-panel-title" class="stat-panel-title"></div>
      <div id="stat-panel-subtitle" class="stat-panel-subtitle"></div>
    </div>
    <div id="stat-panel-rows"></div>
  </section>

  <div class="studio-stamp" aria-label="RGC AI Broadcast Studio">
    <img src="/static/rgc_ai_broadcast_stamp.png" alt="RGC AI Broadcast" />
  </div>

  <section id="special-presentation" class="special-presentation hidden">
    <div class="crank-speaker crank-speaker-left"></div>
    <video id="commercial-video" class="commercial-video" playsinline></video>
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
      setText("cause-line", event.cause || "");
      document.getElementById("cause-line").classList.toggle("hidden", !(event.cause || "").trim());
      setText("lap", buildLapLine(state));
      setText("ticker-lap", buildLapLine(state));
      setText("session-center", buildSessionCenterLine(state));
      setLeaderboardSeries(event.series || "");
      const leaderboardStyle = normalizeLeaderboardStyle(event.leaderboard_style);
      document.body.classList.toggle("leaderboard-ticker-mode", leaderboardStyle === "ticker");
      document.body.classList.toggle("leaderboard-flo-mode", leaderboardStyle === "flo");
      document.getElementById("top-banner").classList.toggle("caution", !!state.caution);
      document.getElementById("caution-status").classList.toggle("hidden", !state.caution);
      document.getElementById("leaderboard").classList.toggle("green", !!state.green);
      document.getElementById("leaderboard").classList.toggle("caution", !!state.caution);
      document.getElementById("ticker-leaderboard").classList.toggle("green", !!state.green);
      document.getElementById("ticker-leaderboard").classList.toggle("caution", !!state.caution);
      document.getElementById("flo-leaderboard").classList.toggle("green", !!state.green);
      document.getElementById("flo-leaderboard").classList.toggle("caution", !!state.caution);
      renderBrandGraphic(event.graphics || [], state.session_type);
      renderLapHistory(state.lap_history || []);
      renderTickerLeaderboard(state.producer_leaderboard || state.leaderboard || [], leaderboardStyle);
      renderFloLeaderboard(state, leaderboardStyle);
      renderSpecialPresentation(state.special_presentation);
      renderDriverCard(shouldHideDriverCardForPresentation(state.special_presentation) ? null : state.featured_driver);
      renderStatPanel(state.stat_panel);

      const rows = document.getElementById("leaderboard-rows");
      rows.innerHTML = "";
      for (const [index, entry] of (state.leaderboard || []).slice(0, 20).entries()) {
        const row = document.createElement("div");
        row.className = "row";
        if (index === 14) row.classList.add("cycle-divider");
        row.innerHTML = `
          <span class="pos">${entry.position}</span>
          <span class="num" style="${numberStyleAttribute(entry.number_style || {})}">${escapeHtml(entry.car_number || "?")}</span>
          <span class="name">${escapeHtml(entry.driver_name || "Unknown")}</span>
          <span class="gap">${escapeHtml(entry.class_position ? `${entry.class_name || "CLS"} ${ordinal(entry.class_position)}` : entry.interval || "")}</span>
        `;
        rows.appendChild(row);
      }
    }

    function normalizeLeaderboardStyle(value) {
      const style = String(value || "side").toLowerCase().trim();
      if (["ticker", "scroll", "top"].includes(style)) return "ticker";
      if (["flo", "flo_top", "flo-top", "top_grid"].includes(style)) return "flo";
      return "side";
    }

    function setLeaderboardSeries(series) {
      const element = document.getElementById("leaderboard-series");
      const label = String(series || "").trim();
      element.classList.toggle("hidden", !label);
      element.textContent = label;
      setText("ticker-label", "Leaderboard");
    }

    function renderTickerLeaderboard(leaderboard, leaderboardStyle) {
      const layer = document.getElementById("ticker-leaderboard");
      const track = document.getElementById("ticker-track");
      const active = leaderboardStyle === "ticker" && leaderboard.length;
      setText("ticker-label", "Leaderboard");
      layer.classList.toggle("hidden", !active);
      if (!active) {
        track.innerHTML = "";
        return;
      }

      const items = leaderboard.slice(0, 40).map((entry) => `
        <span class="ticker-item">
          <span class="ticker-pos">P${escapeHtml(entry.position || "")}</span>
          <span class="ticker-num" style="${numberStyleAttribute(entry.number_style || {})}">${escapeHtml(entry.car_number || "?")}</span>
          <span>${escapeHtml(entry.driver_name || "Unknown")}</span>
          <span class="ticker-gap">${escapeHtml(entry.class_position ? `${entry.class_name || "CLS"} ${ordinal(entry.class_position)}` : entry.interval || "")}</span>
        </span>
      `).join("");
      const resetMarker = `<span class="ticker-reset">Back to Leader</span>`;
      track.innerHTML = items + resetMarker + items;
    }

    function renderFloLeaderboard(state, leaderboardStyle) {
      const layer = document.getElementById("flo-leaderboard");
      const leaderboard = state.producer_leaderboard || state.leaderboard || [];
      const active = leaderboardStyle === "flo" && leaderboard.length;
      layer.classList.toggle("hidden", !active);
      if (!active) {
        document.getElementById("flo-row-top").innerHTML = "";
        document.getElementById("flo-row-second").innerHTML = "";
        document.getElementById("flo-row-cycle").innerHTML = "";
        return;
      }

      const event = state.event || {};
      const sponsorLogo = pickRotatingGraphic(event.sponsor_graphics || event.graphics || [], 4.5);
      const seriesLogo = event.series_logo || "";
      const sponsorImage = document.getElementById("flo-sponsor-logo");
      const seriesImage = document.getElementById("flo-series-logo");
      sponsorImage.classList.toggle("hidden", !sponsorLogo);
      sponsorImage.src = sponsorLogo || "";
      seriesImage.classList.toggle("hidden", !seriesLogo);
      seriesImage.src = seriesLogo || "";
      setText("flo-series-text", event.series || event.sponsor || "RGC AI");
      renderFloLapBox(state);

      const topFive = leaderboard.slice(0, 5);
      const secondFive = leaderboard.slice(5, 10);
      const rest = leaderboard.slice(10);
      const chunkCount = Math.max(1, Math.ceil(rest.length / 5));
      const chunkIndex = rest.length > 5 ? Math.floor(Date.now() / 6000) % chunkCount : 0;
      const cyclingFive = rest.slice(chunkIndex * 5, chunkIndex * 5 + 5);
      document.getElementById("flo-row-top").innerHTML = topFive.map(renderFloEntry).join("");
      document.getElementById("flo-row-second").innerHTML = secondFive.map(renderFloEntry).join("");
      document.getElementById("flo-row-cycle").innerHTML = cyclingFive.map(renderFloEntry).join("");
    }

    function renderFloEntry(entry) {
      return `
        <div class="flo-entry">
          <span class="flo-position">${escapeHtml(entry.position || "")}</span>
          <span class="flo-number" style="${numberStyleAttribute(entry.number_style || {})}">${escapeHtml(entry.car_number || "?")}</span>
          <span class="flo-name">${escapeHtml(lastNameOrName(entry.driver_name || "Unknown"))}</span>
          <span class="flo-gap">${escapeHtml(entry.class_position ? `${entry.class_name || "CLS"} ${ordinal(entry.class_position)}` : entry.interval || "")}</span>
        </div>
      `;
    }

    function lastNameOrName(name) {
      const clean = String(name || "").trim();
      if (!clean) return "Unknown";
      const parts = clean.split(/\s+/).filter(Boolean);
      return parts.length > 1 ? parts[parts.length - 1] : clean;
    }

    function renderFloLapBox(state) {
      const label = document.getElementById("flo-lap-label");
      const value = document.getElementById("flo-lap-value");
      if (isTimedSession(state.session_type)) {
        label.textContent = sessionLabel(state.session_type);
        value.textContent = formatClock(Number(state.session_time_remaining || 0));
        return;
      }
      const total = Number(state.total_laps || 0);
      const lap = Number(state.lap || 0);
      if (total > 0) {
        const toGo = Math.max(total - lap, 0);
        if (lap >= Math.ceil(total / 2) && toGo > 0) {
          label.textContent = "Laps To Go";
          value.textContent = String(toGo);
          return;
        }
        label.textContent = "Lap";
        value.textContent = `${lap}/${total}`;
        return;
      }
      label.textContent = "Lap";
      value.textContent = lap ? String(lap) : "--";
    }

    function numberStyleAttribute(style) {
      const safe = style || {};
      const pieces = [];
      if (safe.color) pieces.push(`color:${safe.color}`);
      if (safe.background) pieces.push(`background:${safe.background}`);
      if (safe.outline) {
        pieces.push(`border-color:${safe.outline}`);
        pieces.push(`text-shadow:-1px -1px 0 ${safe.outline},1px -1px 0 ${safe.outline},-1px 1px 0 ${safe.outline},1px 1px 0 ${safe.outline}`);
      }
      if (safe.font_family) pieces.push(`font-family:${safe.font_family}, Arial, sans-serif`);
      if (safe.font_style) pieces.push(`font-style:${safe.font_style}`);
      return pieces.join(";");
    }

    let commercialClearRequested = false;

    function renderSpecialPresentation(presentation) {
      const layer = document.getElementById("special-presentation");
      const active = !!(presentation && presentation.kind);
      layer.classList.toggle("hidden", !active);
      layer.classList.toggle("crank_it_up", active && presentation.kind === "crank_it_up");
      layer.classList.toggle("race_sponsors", active && presentation.kind === "race_sponsors");
      layer.classList.toggle("sponsor_bug", active && presentation.kind === "sponsor_bug");
      layer.classList.toggle("sponsor_commercial", active && presentation.kind === "sponsor_commercial");
      if (!active) {
        setCrankSideGraphic("crank-speaker-left", "");
        setCrankSideGraphic("crank-speaker-right", "");
        setCommercialVideo("");
        return;
      }
      setText("ceremony-title", presentation.title || "Please Rise");
      setText("ceremony-subtitle", presentation.subtitle || "Presented by RGC Motorsports");
      const logo = document.getElementById("ceremony-logo");
      const graphics = presentation.graphics || [];
      const isCrank = presentation.kind === "crank_it_up";
      const isCommercial = presentation.kind === "sponsor_commercial";
      const src = isCrank ? String(graphics[0] || "") : pickRotatingGraphic(graphics, isCommercial ? 999 : 3.5);
      const sideSrc = isCrank ? (graphics[1] || graphics[0] || "") : "";
      setCrankSideGraphic("crank-speaker-left", sideSrc);
      setCrankSideGraphic("crank-speaker-right", sideSrc);
      setCommercialVideo(isCommercial ? presentation.video_url : "");
      logo.classList.toggle("hidden", !src);
      logo.src = src || "";
    }

    function shouldHideDriverCardForPresentation(presentation) {
      return !!(presentation && presentation.kind === "crank_it_up");
    }

    function setCommercialVideo(src) {
      const video = document.getElementById("commercial-video");
      if (!video) return;
      const nextSrc = String(src || "");
      if (!nextSrc) {
        if (video.getAttribute("src")) {
          video.pause();
          video.removeAttribute("src");
          video.load();
        }
        commercialClearRequested = false;
        return;
      }
      if (video.getAttribute("src") !== nextSrc) {
        video.setAttribute("src", nextSrc);
        video.currentTime = 0;
        commercialClearRequested = false;
        const playPromise = video.play();
        if (playPromise && typeof playPromise.catch === "function") {
          playPromise.catch((error) => console.warn("Commercial video autoplay failed", error));
        }
      }
    }

    function clearCommercialPresentationFromVideo() {
      if (commercialClearRequested) return;
      commercialClearRequested = true;
      fetch("/overlay/clear-special-presentation", { method: "POST" })
        .catch((error) => console.warn("Could not clear commercial presentation", error));
    }

    function installCommercialVideoHandlers() {
      const video = document.getElementById("commercial-video");
      if (!video || video.dataset.handlersInstalled === "1") return;
      video.dataset.handlersInstalled = "1";
      video.addEventListener("ended", clearCommercialPresentationFromVideo);
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
      const maxRows = panel.kind === "points_standings" ? 20 : 7;
      for (const row of (panel.rows || []).slice(0, maxRows)) {
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
      const compacted = compactLapHistoryRuns(history);
      bar.innerHTML = "";
      for (const lap of compacted) {
        const segment = document.createElement("span");
        segment.className = `lap-history-segment ${lap.status || "pending"}`;
        segment.style.flexGrow = String(lap.count || 1);
        segment.title = lap.start === lap.end
          ? `Lap ${lap.start}: ${lap.status || "pending"}`
          : `Laps ${lap.start}-${lap.end}: ${lap.status || "pending"}`;
        bar.appendChild(segment);
      }
    }

    function compactLapHistoryRuns(history) {
      const runs = [];
      for (const lap of history || []) {
        const status = lap.status || "pending";
        const currentLap = Number(lap.lap || 0);
        const last = runs[runs.length - 1];
        if (last && last.status === status && currentLap === last.end + 1) {
          last.end = currentLap;
          last.count += 1;
        } else {
          runs.push({ start: currentLap, end: currentLap, status, count: 1 });
        }
      }
      return runs;
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
      applyDriverCardNumberStyle(driver.number_style || {});
      setText("driver-card-name", driver.driver_name || "Unknown Driver");
      renderDriverCardCountry(driver);
      setText("driver-card-position-rank", buildDriverCardRankLine(driver));
      setText("driver-card-position", buildDriverCardPositionLine(driver));
      setText("driver-card-story", cleanDriverCardStory(driver));
      renderDriverCardImage(driver.car_image_url || "", driver);
    }

    function applyDriverCardNumberStyle(style) {
      const number = document.getElementById("driver-card-number");
      const outline = style.outline || "";
      number.style.color = style.color || "";
      number.style.background = style.background || "";
      number.style.borderColor = outline || "";
      number.style.fontFamily = style.font_family ? `${style.font_family}, Arial, sans-serif` : "";
      number.style.fontStyle = style.font_style || "";
      number.style.textShadow = outline
        ? `-1px -1px 0 ${outline}, 1px -1px 0 ${outline}, -1px 1px 0 ${outline}, 1px 1px 0 ${outline}, 0 4px 14px rgba(0,0,0,.66)`
        : "";
    }

    function cleanDriverCardStory(driver) {
      const story = String(driver.story || "").trim();
      if (!story) return "";
      const driverName = String(driver.driver_name || "").trim().toLowerCase();
      const country = String(driver.country || "").trim().toLowerCase();
      const normalized = story.toLowerCase();
      if (normalized === driverName || normalized === country) return "";
      return story;
    }

    function formatDriverCountry(driver) {
      const country = String(driver.country || "").trim();
      if (!country) return "";
      const flag = countryFlag(country);
      return flag ? `${flag} ${country}` : country;
    }

    function renderDriverCardCountry(driver) {
      const element = document.getElementById("driver-card-country");
      const country = String(driver.country || "").trim();
      if (!country) {
        element.innerHTML = "";
        element.classList.add("hidden");
        return;
      }
      const code = countryCodeFromNameOrCode(country);
      const flagHtml = code
        ? `<img class="driver-card-flag" src="https://flagcdn.com/w40/${code.toLowerCase()}.png" alt="${escapeHtml(code)} flag" onerror="this.remove()">`
        : "";
      element.innerHTML = `${flagHtml}<span class="driver-card-country-text">${escapeHtml(country)}</span>`;
      element.classList.remove("hidden");
    }

    function countryCodeFromNameOrCode(country) {
      const normalized = String(country || "").toLowerCase().replace(/\./g, "").trim();
      if (!normalized) return "";
      const compactCode = normalized.replace(/[^a-z]/g, "").toUpperCase();
      if (/^[A-Z]{2}$/.test(compactCode)) return compactCode;
      const byName = {
        "argentina": "AR",
        "australia": "AU",
        "austria": "AT",
        "belgium": "BE",
        "brazil": "BR",
        "canada": "CA",
        "chile": "CL",
        "china": "CN",
        "colombia": "CO",
        "czech republic": "CZ",
        "czechia": "CZ",
        "denmark": "DK",
        "finland": "FI",
        "france": "FR",
        "germany": "DE",
        "hungary": "HU",
        "india": "IN",
        "ireland": "IE",
        "italy": "IT",
        "japan": "JP",
        "mexico": "MX",
        "netherlands": "NL",
        "new zealand": "NZ",
        "norway": "NO",
        "poland": "PL",
        "portugal": "PT",
        "south africa": "ZA",
        "south korea": "KR",
        "spain": "ES",
        "sweden": "SE",
        "switzerland": "CH",
        "united kingdom": "GB",
        "england": "GB",
        "scotland": "GB",
        "wales": "GB",
        "united states": "US",
        "united states of america": "US",
        "usa": "US",
        "us": "US",
      };
      const code = byName[normalized];
      return code || "";
    }

    function flagEmojiFromCode(code) {
      const clean = String(code || "").trim().toUpperCase();
      if (!/^[A-Z]{2}$/.test(clean)) return "";
      return String.fromCodePoint(
        0x1F1E6 + clean.charCodeAt(0) - 65,
        0x1F1E6 + clean.charCodeAt(1) - 65
      );
    }

    function countryFlag(country) {
      const normalized = String(country || "").toLowerCase().replace(/\./g, "").trim();
      if (!normalized) return "";
      const mappedCode = countryCodeFromNameOrCode(normalized);
      if (mappedCode) return flagEmojiFromCode(mappedCode);
      if (normalized.includes("united states") || /\busa?\b/.test(normalized)) return "🇺🇸";
      if (normalized.includes("canada")) return "🇨🇦";
      if (normalized.includes("united kingdom") || normalized.includes("england") || normalized.includes("scotland") || normalized.includes("wales")) return "🇬🇧";
      const byName = {
        "argentina": "🇦🇷",
        "australia": "🇦🇺",
        "belgium": "🇧🇪",
        "brazil": "🇧🇷",
        "denmark": "🇩🇰",
        "finland": "🇫🇮",
        "france": "🇫🇷",
        "germany": "🇩🇪",
        "ireland": "🇮🇪",
        "italy": "🇮🇹",
        "japan": "🇯🇵",
        "mexico": "🇲🇽",
        "netherlands": "🇳🇱",
        "new zealand": "🇳🇿",
        "norway": "🇳🇴",
        "spain": "🇪🇸",
        "sweden": "🇸🇪",
      };
      return byName[normalized] || "";
    }

    function renderDriverCardImage(imageUrl, driver = {}) {
      const imageShell = document.getElementById("driver-card-image");
      const image = document.getElementById("driver-card-car-img");
      imageShell.classList.toggle("no-source", !imageUrl);
      if (!imageUrl) {
        imageShell.classList.remove("image-failed", "image-loading");
        image.dataset.currentSrc = "";
        image.dataset.currentKey = "";
        image.removeAttribute("src");
        return;
      }
      const imageKey = `${imageUrl}|${driver.car_idx || ""}|${driver.car_number || ""}|${driver.driver_name || ""}`;
      if (image.dataset.currentKey === imageKey) return;
      image.dataset.currentSrc = imageUrl;
      image.dataset.currentKey = imageKey;
      imageShell.classList.remove("image-failed");
      imageShell.classList.add("image-loading");
      image.removeAttribute("src");
      const cacheBustedUrl = imageUrl.startsWith("/iracing-render")
        ? `${imageUrl}&rgc_card_key=${encodeURIComponent(imageKey)}`
        : imageUrl;
      image.onload = () => {
        if (image.dataset.currentKey !== imageKey) return;
        imageShell.classList.remove("image-failed", "image-loading", "no-source");
      };
      image.onerror = () => {
        if (image.dataset.currentKey !== imageKey) return;
        imageShell.classList.remove("image-loading");
        imageShell.classList.add("image-failed");
        image.removeAttribute("src");
      };
      image.src = cacheBustedUrl;
    }

    function buildDriverCardRankLine(driver) {
      const position = Number(driver.position || 0);
      return position > 0 ? `P${position}` : "P--";
    }

    function buildDriverCardPositionLine(driver) {
      const pieces = [];
      const start = Number(driver.starting_position || 0);
      const delta = Number(driver.position_delta || 0);
      const classPosition = Number(driver.class_position || 0);
      if (classPosition > 0) {
        pieces.push(`${driver.class_name || "Class"} ${ordinal(classPosition)}${driver.class_size ? ` of ${driver.class_size}` : ""}`);
      }
      if (start > 0) pieces.push(`Started ${ordinal(start)}`);
      if (start > 0 && delta !== 0) {
        const sign = delta > 0 ? "+" : "";
        const word = Math.abs(delta) === 1 ? "spot" : "spots";
        pieces.push(`${sign}${delta} ${word}`);
      }
      if (driver.interval) pieces.push(driver.interval);
      return pieces.join(" • ");
    }

    function buildTrackLine(state) {
      return state.track_name || "Waiting for iRacing";
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

    function ordinal(n) {
      const value = Number(n || 0);
      if (!value) return "--";
      const mod100 = value % 100;
      if (mod100 >= 11 && mod100 <= 13) return `${value}th`;
      const suffix = value % 10 === 1 ? "st" : value % 10 === 2 ? "nd" : value % 10 === 3 ? "rd" : "th";
      return `${value}${suffix}`;
    }

    function pickRotatingGraphic(graphics, seconds) {
      if (!graphics || !graphics.length) return "";
      const index = Math.floor(Date.now() / (seconds * 1000)) % graphics.length;
      return graphics[index];
    }

    installCommercialVideoHandlers();
    refreshOverlay();
    setInterval(refreshOverlay, 1000);
  </script>
</body>
</html>
"""
