from dataclasses import dataclass, field
from typing import Any, Dict, List


@dataclass
class TelemetrySnapshot:
    timestamp: float = 0.0
    lap: int = 0
    total_laps: int = 0
    session_flags: int = 0

    track_info: Dict[str, Any] = field(default_factory=dict)
    results: List[Dict[str, Any]] = field(default_factory=list)
    driver_lookup: Dict[Any, Dict[str, Any]] = field(default_factory=dict)

    pit_road_status: List[Any] = field(default_factory=list)
    track_surface: List[Any] = field(default_factory=list)
    track_surface_material: List[Any] = field(default_factory=list)
    lap_dist_pct: List[Any] = field(default_factory=list)
    est_time: List[Any] = field(default_factory=list)

    @classmethod
    def from_dict(cls, data):
        return cls(
            timestamp=data.get("timestamp", 0.0),
            lap=data.get("lap", 0),
            total_laps=data.get("total_laps", 0),
            session_flags=data.get("session_flags", 0),
            track_info=data.get("track_info", {}) or {},
            results=data.get("results", []) or [],
            driver_lookup=data.get("driver_lookup", {}) or {},
            pit_road_status=data.get("pit_road_status", []) or [],
            track_surface=data.get("track_surface", []) or [],
            track_surface_material=data.get("track_surface_material", []) or [],
            lap_dist_pct=data.get("lap_dist_pct", []) or [],
            est_time=data.get("est_time", []) or [],
        )

    def to_dict(self):
        return {
            "timestamp": self.timestamp,
            "lap": self.lap,
            "total_laps": self.total_laps,
            "session_flags": self.session_flags,
            "track_info": self.track_info,
            "results": self.results,
            "driver_lookup": self.driver_lookup,
            "pit_road_status": self.pit_road_status,
            "track_surface": self.track_surface,
            "track_surface_material": self.track_surface_material,
            "lap_dist_pct": self.lap_dist_pct,
            "est_time": self.est_time,
        }

    def get_race_lap(self):
        laps = [self.safe_int(self.lap)]

        for car in self.results:
            laps.append(self.safe_int(car.get("LapsComplete", 0)))

        return max(laps) if laps else 0

    def get_track_name(self):
        return self.track_info.get("track_name", "Unknown Track")

    def get_driver_count(self):
        return len(self.results)

    def safe_int(self, value):
        try:
            return int(value)
        except Exception:
            return 0