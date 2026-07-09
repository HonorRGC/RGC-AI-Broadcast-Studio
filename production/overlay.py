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

    def to_dict(self):
        return {
            "position": self.position,
            "car_idx": self.car_idx,
            "car_number": self.car_number,
            "driver_name": self.driver_name,
            "laps_complete": self.laps_complete,
            "interval": self.interval,
            "fastest_lap": self.fastest_lap,
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

        leaderboard = []
        for car in valid_results:
            car_idx = car.get("CarIdx")
            driver = (driver_lookup or {}).get(car_idx, {})
            raw_position = self.safe_int(car.get("Position"), len(leaderboard) + 1)
            display_position = raw_position + 1 if zero_based else raw_position
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
                    ),
                    fastest_lap=self.format_lap_time(self.best_lap_value(car)),
                )
            )
        return self.visible_leaderboard_window(leaderboard)

    def format_entry_metric(self, car, display_position, session_type, leader_laps=0):
        if self.is_timed_session(session_type):
            return self.format_lap_time(self.best_lap_value(car))
        laps_down = self.laps_down(car, leader_laps)
        if laps_down > 0:
            lap_word = "lap" if laps_down == 1 else "laps"
            return f"-{laps_down} {lap_word}"
        return "" if display_position == 1 else self.format_interval(car)

    def laps_down(self, car, leader_laps=0):
        for key in ("LapsBehind", "LapsDown"):
            value = self.safe_int(car.get(key), 0)
            if value > 0:
                return value
        car_laps = self.safe_int(car.get("LapsComplete", car.get("Lap", 0)))
        if leader_laps > 0 and car_laps > 0:
            return max(leader_laps - car_laps, 0)
        return 0

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
        self.httpd = None
        self.thread = None
        self.static_dir = Path(__file__).resolve().parent / "static"

    @property
    def url(self):
        return f"http://{self.host}:{self.port}/overlay"

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

    def clear_special_presentation(self):
        with self.lock:
            self.special_presentation = None

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
        return True

    def current_state_dict(self):
        with self.lock:
            return self.state.to_dict()

    def make_handler(self):
        server = self

        class Handler(BaseHTTPRequestHandler):
            def do_GET(self):
                if self.path in ("/", "/overlay"):
                    self.send_text(OVERLAY_HTML, "text/html; charset=utf-8")
                    return

                if self.path == "/overlay/state":
                    self.send_json(server.current_state_dict())
                    return

                if self.path.startswith("/assets/"):
                    self.send_asset(self.path.removeprefix("/assets/"))
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

            def log_message(self, *_):
                return

        return Handler


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

    .ceremony-logo {
      width: 210px;
      height: 116px;
      object-fit: contain;
      filter: drop-shadow(0 10px 18px rgba(0, 0, 0, 0.62));
    }

    .ceremony-title {
      font-size: 40px;
      font-weight: 950;
      letter-spacing: 0.05em;
    }

    .ceremony-subtitle {
      margin-top: 14px;
      color: var(--rgc-muted);
      font-size: 18px;
      font-weight: 800;
      letter-spacing: 0.08em;
    }

    .special-presentation.crank_it_up {
      left: 24px;
      right: 24px;
      top: auto;
      bottom: 34px;
      height: 190px;
      justify-content: space-between;
      gap: 34px;
    }

    .crank-speaker {
      display: none;
      flex: 0 0 170px;
      width: 170px;
      height: 142px;
      border-radius: 18px;
      background:
        radial-gradient(circle at 50% 28%, #272f3d 0 19px, #050608 20px 38px, transparent 39px),
        radial-gradient(circle at 50% 73%, #2d394b 0 38px, #050608 39px 64px, transparent 65px),
        linear-gradient(145deg, rgba(49, 57, 70, 0.99), rgba(5, 6, 8, 0.98));
      border: 4px solid rgba(255, 255, 255, 0.30);
      box-shadow: 0 0 34px rgba(165, 20, 30, 0.62), inset 0 0 18px rgba(255, 255, 255, 0.10);
      animation: speakerPulse 0.42s infinite alternate;
      position: relative;
    }

    .crank-speaker::before,
    .crank-speaker::after {
      content: "";
      position: absolute;
      left: 50%;
      transform: translateX(-50%);
      border-radius: 50%;
      border: 3px solid rgba(255, 255, 255, 0.22);
      box-shadow: inset 0 0 18px rgba(255, 255, 255, 0.10);
    }

    .crank-speaker::before {
      top: 18px;
      width: 48px;
      height: 48px;
    }

    .crank-speaker::after {
      bottom: 17px;
      width: 84px;
      height: 84px;
    }

    .special-presentation.crank_it_up .crank-speaker {
      display: block;
    }

    .special-presentation.crank_it_up .ceremony-card {
      display: block;
      width: auto;
      min-width: 520px;
      padding: 24px 44px;
      text-align: center;
      border-left: 0;
      border-bottom: 6px solid var(--rgc-red);
      background: linear-gradient(90deg, rgba(7, 9, 13, 0.92), rgba(36, 12, 18, 0.9), rgba(7, 9, 13, 0.92));
    }

    .special-presentation.crank_it_up .ceremony-logo {
      display: none;
    }

    .special-presentation.crank_it_up .ceremony-title {
      font-size: 58px;
      letter-spacing: 0.08em;
      text-shadow: 0 0 22px rgba(255, 255, 255, 0.28);
    }

    .special-presentation.crank_it_up .ceremony-subtitle {
      color: #ffffff;
      opacity: 0.82;
    }

    @keyframes speakerPulse {
      from {
        transform: scale(0.98);
        filter: brightness(0.9);
      }
      to {
        transform: scale(1.04);
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
      if (!active) return;
      setText("ceremony-title", presentation.title || "Please Rise");
      setText("ceremony-subtitle", presentation.subtitle || "Presented by RGC Motorsports");
      const logo = document.getElementById("ceremony-logo");
      const graphics = presentation.graphics || [];
      const src = pickRotatingGraphic(graphics, 3.5);
      logo.classList.toggle("hidden", !src);
      logo.src = src || "";
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
      const isRace = String(sessionType || "").toLowerCase().includes("race");
      const src = isRace ? pickRotatingGraphic(graphics || [], 4.5) : "";
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
