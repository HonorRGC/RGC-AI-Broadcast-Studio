from dataclasses import dataclass, field
from typing import Any


@dataclass
class TelemetrySnapshot:
    timestamp: float = 0.0
    lap: int = 0
    total_laps: int = 0
    session_type: str = "Race"
    session_flags: int = 0
    track_info: dict[str, Any] = field(default_factory=dict)
    results: list[dict[str, Any]] = field(default_factory=list)
    driver_lookup: dict[Any, dict[str, Any]] = field(default_factory=dict)
    pit_road_status: list[Any] = field(default_factory=list)
    track_surface: list[Any] = field(default_factory=list)
    track_surface_material: list[Any] = field(default_factory=list)
    lap_dist_pct: list[Any] = field(default_factory=list)
    est_time: list[Any] = field(default_factory=list)

    @classmethod
    def from_dict(cls, data):
        fields = cls.__dataclass_fields__
        return cls(**{key: data[key] for key in fields if key in data})

    @classmethod
    def from_telemetry(cls, telemetry, timestamp=0.0):
        return cls(
            timestamp=timestamp,
            lap=telemetry.get_lap(),
            total_laps=telemetry.get_total_laps(),
            session_type=telemetry.get_session_type(),
            session_flags=telemetry.get_session_flags(),
            track_info=telemetry.get_track_info(),
            results=telemetry.get_results(),
            driver_lookup=telemetry.get_driver_lookup(),
            pit_road_status=telemetry.get_car_idx_on_pit_road(),
            track_surface=telemetry.get_car_idx_track_surface(),
            track_surface_material=telemetry.get_car_idx_track_surface_material(),
            lap_dist_pct=telemetry.get_car_idx_lap_dist_pct(),
            est_time=telemetry.get_car_idx_est_time(),
        )

    def to_dict(self):
        return {key: getattr(self, key) for key in self.__dataclass_fields__}

    def race_lap(self):
        laps = [self._safe_int(self.lap)]
        for car in self.results:
            laps.append(self._safe_int(car.get("LapsComplete", car.get("Lap", 0))))
        return max(laps, default=0)

    @staticmethod
    def _safe_int(value):
        try:
            return int(value)
        except (TypeError, ValueError):
            return 0
