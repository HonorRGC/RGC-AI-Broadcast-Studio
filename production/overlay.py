import json
import threading
from dataclasses import dataclass, field
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from typing import Any

from config import (
    OVERLAY_EVENT_TITLE,
    OVERLAY_RACE_SPONSOR,
    OVERLAY_SERIES_NAME,
)


@dataclass
class OverlayEventConfig:
    title: str = OVERLAY_EVENT_TITLE
    sponsor: str = OVERLAY_RACE_SPONSOR
    series: str = OVERLAY_SERIES_NAME


@dataclass
class LeaderboardEntry:
    position: int
    car_idx: int
    car_number: str
    driver_name: str
    laps_complete: int = 0
    interval: str = ""

    def to_dict(self):
        return {
            "position": self.position,
            "car_idx": self.car_idx,
            "car_number": self.car_number,
            "driver_name": self.driver_name,
            "laps_complete": self.laps_complete,
            "interval": self.interval,
        }


@dataclass
class OverlayState:
    event: OverlayEventConfig = field(default_factory=OverlayEventConfig)
    session_type: str = "Unknown"
    track_name: str = ""
    lap: int = 0
    total_laps: int = 0
    leaderboard: list[LeaderboardEntry] = field(default_factory=list)

    def to_dict(self):
        return {
            "event": {
                "title": self.event.title,
                "sponsor": self.event.sponsor,
                "series": self.event.series,
            },
            "session_type": self.session_type,
            "track_name": self.track_name,
            "lap": self.lap,
            "total_laps": self.total_laps,
            "leaderboard": [entry.to_dict() for entry in self.leaderboard],
        }


class OverlayStateBuilder:
    def __init__(self, event_config=None, max_entries=20):
        self.event_config = event_config or OverlayEventConfig()
        self.max_entries = int(max_entries)

    def build_from_telemetry(self, telemetry):
        results = telemetry.get_results()
        driver_lookup = telemetry.get_driver_lookup()
        track_info = telemetry.get_track_info()
        session_type_reader = getattr(telemetry, "get_session_type", None)
        session_type = session_type_reader() if session_type_reader else "Unknown"

        return OverlayState(
            event=self.event_config,
            session_type=session_type,
            track_name=(track_info or {}).get("track_name", ""),
            lap=self.best_race_lap(results, telemetry.get_lap()),
            total_laps=self.safe_int(telemetry.get_total_laps()),
            leaderboard=self.build_leaderboard(results, driver_lookup),
        )

    def best_race_lap(self, results, telemetry_lap=0):
        laps = [self.safe_int(telemetry_lap)]
        for car in results or []:
            laps.append(self.safe_int(car.get("LapsComplete", car.get("Lap", 0))))
        return max(laps, default=0)

    def build_leaderboard(self, results, driver_lookup):
        valid_results = [
            dict(car)
            for car in results or []
            if car.get("CarIdx") is not None
        ]
        zero_based = any(self.safe_int(car.get("Position"), 999) == 0 for car in valid_results)
        valid_results.sort(key=lambda car: self.safe_int(car.get("Position"), 999))

        leaderboard = []
        for car in valid_results[: self.max_entries]:
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
                    interval="" if display_position == 1 else self.format_interval(car),
                )
            )
        return leaderboard

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
        self.httpd = None
        self.thread = None

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
            self.state = state

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
      left: 50%;
      top: 24px;
      transform: translateX(-50%);
      min-width: 760px;
      max-width: 1120px;
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

    .event-title {
      font-size: 28px;
      font-weight: 800;
      text-transform: uppercase;
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
    }

    .leaderboard {
      position: absolute;
      left: 24px;
      top: 124px;
      width: 330px;
      background: var(--rgc-panel);
      box-shadow: 0 14px 34px rgba(0, 0, 0, 0.40);
      border-left: 5px solid var(--rgc-red);
    }

    .leaderboard-header {
      display: grid;
      grid-template-columns: 1fr auto;
      gap: 10px;
      padding: 12px 14px;
      background: var(--rgc-dark);
      border-bottom: 1px solid var(--rgc-line);
      text-transform: uppercase;
      font-weight: 800;
    }

    .lap {
      color: var(--rgc-muted);
      font-size: 13px;
      align-self: center;
    }

    .row {
      display: grid;
      grid-template-columns: 40px 54px 1fr auto;
      gap: 8px;
      align-items: center;
      min-height: 32px;
      padding: 5px 12px;
      border-bottom: 1px solid rgba(255, 255, 255, 0.08);
      font-size: 15px;
    }

    .row:nth-child(even) {
      background: rgba(255, 255, 255, 0.035);
    }

    .pos {
      color: #fff;
      font-weight: 900;
      font-size: 17px;
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

    .hidden {
      display: none;
    }
  </style>
</head>
<body>
  <section class="top-banner">
    <div>
      <div id="event-title" class="event-title">RGC AI Broadcast</div>
      <div id="series" class="event-meta"></div>
    </div>
    <div class="event-meta">
      <span id="track">Waiting for iRacing</span>
      <span id="sponsor" class="sponsor"></span>
    </div>
  </section>

  <section class="leaderboard">
    <div class="leaderboard-header">
      <span>Leaderboard</span>
      <span id="lap" class="lap">Lap --</span>
    </div>
    <div id="leaderboard-rows"></div>
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

      const rows = document.getElementById("leaderboard-rows");
      rows.innerHTML = "";
      for (const entry of (state.leaderboard || []).slice(0, 20)) {
        const row = document.createElement("div");
        row.className = "row";
        row.innerHTML = `
          <span class="pos">${entry.position}</span>
          <span class="num">${escapeHtml(entry.car_number || "?")}</span>
          <span class="name">${escapeHtml(entry.driver_name || "Unknown")}</span>
          <span class="gap">${escapeHtml(entry.interval || "")}</span>
        `;
        rows.appendChild(row);
      }
    }

    function buildTrackLine(state) {
      const pieces = [];
      if (state.track_name) pieces.push(state.track_name);
      if (state.session_type) pieces.push(state.session_type);
      return pieces.join(" • ") || "Waiting for iRacing";
    }

    function buildLapLine(state) {
      if (state.total_laps) return `Lap ${state.lap || 0} / ${state.total_laps}`;
      if (state.lap) return `Lap ${state.lap}`;
      return "Lap --";
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

    refreshOverlay();
    setInterval(refreshOverlay, 1000);
  </script>
</body>
</html>
"""
