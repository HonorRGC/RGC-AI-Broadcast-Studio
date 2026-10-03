from __future__ import annotations

import json
from dataclasses import asdict, dataclass, field
from datetime import datetime
from pathlib import Path


SCORING_SCHEMA_VERSION = 1
LEAGUE_SCHEMA_VERSION = 1
RESULTS_SCHEMA_VERSION = 1


@dataclass(frozen=True)
class ScoringRule:
    name: str
    points: float
    enabled: bool = True

    @classmethod
    def from_dict(cls, data):
        return cls(
            name=str((data or {}).get("name", "")).strip(),
            points=float((data or {}).get("points", 0) or 0),
            enabled=bool((data or {}).get("enabled", True)),
        )


@dataclass(frozen=True)
class PointsAdjustment:
    amount: float
    reason: str


@dataclass
class ScoringSystem:
    name: str = "Custom League Points"
    finish_points: dict[int, float] = field(default_factory=dict)
    bonus_rules: list[ScoringRule] = field(default_factory=list)
    penalty_rules: list[ScoringRule] = field(default_factory=list)

    def validate(self):
        errors = []
        if not self.name.strip():
            errors.append("Scoring system name is required.")
        if not self.finish_points:
            errors.append("Add at least one finishing-position points value.")
        for position, points in self.finish_points.items():
            if int(position) < 1:
                errors.append(f"Finishing position must be 1 or greater: {position}.")
            if float(points) < 0:
                errors.append(f"Finishing points cannot be negative for P{position}.")
        for group_name, rules in (("bonus", self.bonus_rules), ("penalty", self.penalty_rules)):
            names = set()
            for rule in rules:
                key = rule.name.casefold().strip()
                if not key:
                    errors.append(f"Every {group_name} rule needs a name.")
                elif key in names:
                    errors.append(f"Duplicate {group_name} rule: {rule.name}.")
                names.add(key)
                if rule.points < 0:
                    errors.append(f"{group_name.title()} rule points must be zero or greater: {rule.name}.")
        return errors

    def calculate(self, position, bonus_names=(), penalty_names=(), adjustments=()):
        position = int(position or 0)
        finish = float(self.finish_points.get(position, 0))
        selected_bonuses = {str(name).casefold().strip() for name in bonus_names}
        selected_penalties = {str(name).casefold().strip() for name in penalty_names}
        bonus_items = [
            PointsAdjustment(float(rule.points), rule.name)
            for rule in self.bonus_rules
            if rule.enabled and rule.name.casefold().strip() in selected_bonuses
        ]
        penalty_items = [
            PointsAdjustment(-float(rule.points), rule.name)
            for rule in self.penalty_rules
            if rule.enabled and rule.name.casefold().strip() in selected_penalties
        ]
        manual_items = [
            item if isinstance(item, PointsAdjustment) else PointsAdjustment(float(item[0]), str(item[1]))
            for item in adjustments
        ]
        total = finish + sum(item.amount for item in bonus_items + penalty_items + manual_items)
        return {
            "position": position,
            "finish_points": finish,
            "bonuses": [asdict(item) for item in bonus_items],
            "penalties": [asdict(item) for item in penalty_items],
            "adjustments": [asdict(item) for item in manual_items],
            "total": total,
        }

    def to_dict(self):
        return {
            "schema_version": SCORING_SCHEMA_VERSION,
            "name": self.name,
            "finish_points": {str(position): points for position, points in sorted(self.finish_points.items())},
            "bonus_rules": [asdict(rule) for rule in self.bonus_rules],
            "penalty_rules": [asdict(rule) for rule in self.penalty_rules],
        }

    @classmethod
    def from_dict(cls, data):
        data = data or {}
        return cls(
            name=str(data.get("name") or "Custom League Points"),
            finish_points={int(position): float(points) for position, points in (data.get("finish_points") or {}).items()},
            bonus_rules=[ScoringRule.from_dict(rule) for rule in data.get("bonus_rules") or []],
            penalty_rules=[ScoringRule.from_dict(rule) for rule in data.get("penalty_rules") or []],
        )


def default_scoring_system():
    finish_points = {1: 40, 2: 35}
    finish_points.update({position: max(1, 37 - position) for position in range(3, 41)})
    return ScoringSystem(
        name="Custom League Points",
        finish_points=finish_points,
        bonus_rules=[
            ScoringRule("Pole", 1),
            ScoringRule("Fastest Lap", 1),
            ScoringRule("Led a Lap", 1),
            ScoringRule("Most Laps Led", 1),
            ScoringRule("Incident Free", 1),
        ],
        penalty_rules=[
            ScoringRule("Avoidable Contact", 5),
            ScoringRule("Unsafe Driving", 10),
            ScoringRule("Post-Race Penalty", 5),
        ],
    )


def save_scoring_system(path, scoring):
    path = Path(path)
    errors = scoring.validate()
    if errors:
        raise ValueError("\n".join(errors))
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(scoring.to_dict(), indent=2) + "\n", encoding="utf-8")
    return path


def load_scoring_system(path):
    path = Path(path)
    if not path.exists():
        return default_scoring_system()
    return ScoringSystem.from_dict(json.loads(path.read_text(encoding="utf-8")))


@dataclass
class LeagueProfile:
    name: str = ""
    short_name: str = ""
    season_name: str = ""
    iracing_league_id: int | None = None
    description: str = ""

    def to_dict(self):
        return {"schema_version": LEAGUE_SCHEMA_VERSION, **asdict(self)}

    @classmethod
    def from_dict(cls, data):
        data = data or {}
        league_id = data.get("iracing_league_id")
        return cls(
            name=str(data.get("name") or ""),
            short_name=str(data.get("short_name") or ""),
            season_name=str(data.get("season_name") or ""),
            iracing_league_id=int(league_id) if str(league_id or "").isdigit() else None,
            description=str(data.get("description") or ""),
        )


@dataclass
class ScheduleEvent:
    round_number: int
    event_date: str = ""
    track_name: str = ""
    configuration: str = ""
    laps: int | None = None
    status: str = "Scheduled"
    notes: str = ""
    event_name: str = ""
    car_type: str = ""
    duration_minutes: int | None = None
    practice_time: str = ""
    qualifying_time: str = ""
    race_time: str = ""

    def validate(self):
        if self.round_number < 1:
            raise ValueError("Round number must be 1 or greater.")
        if not self.track_name.strip():
            raise ValueError("Track name is required.")
        if self.event_date:
            try:
                datetime.strptime(self.event_date, "%m-%d-%Y")
            except ValueError as error:
                raise ValueError("Race date must use month-day-year, such as 10-03-2026.") from error
        if self.laps is not None and self.laps < 1:
            raise ValueError("Laps must be 1 or greater.")
        if self.duration_minutes is not None and self.duration_minutes < 1:
            raise ValueError("Timed race minutes must be 1 or greater.")
        if self.laps is None and self.duration_minutes is None:
            raise ValueError("Enter either race laps or timed-race minutes.")
        for title, value in (("Practice", self.practice_time), ("Qualifying", self.qualifying_time), ("Race start", self.race_time)):
            if value:
                try:
                    datetime.strptime(value.upper().replace(" ", ""), "%I:%M%p")
                except ValueError as error:
                    raise ValueError(f"{title} time must look like 6:30 PM.") from error

    @classmethod
    def from_dict(cls, data):
        laps = (data or {}).get("laps")
        event_date = str((data or {}).get("event_date") or "")
        if event_date:
            try:
                event_date = datetime.strptime(event_date, "%Y-%m-%d").strftime("%m-%d-%Y")
            except ValueError:
                pass
        return cls(
            round_number=int((data or {}).get("round_number") or 1),
            event_date=event_date,
            track_name=str((data or {}).get("track_name") or ""),
            configuration=str((data or {}).get("configuration") or ""),
            laps=int(laps) if str(laps or "").isdigit() else None,
            status=str((data or {}).get("status") or "Scheduled"),
            notes=str((data or {}).get("notes") or ""),
            event_name=str((data or {}).get("event_name") or ""),
            car_type=str((data or {}).get("car_type") or ""),
            duration_minutes=(
                int((data or {}).get("duration_minutes"))
                if str((data or {}).get("duration_minutes") or "").isdigit()
                else None
            ),
            practice_time=str((data or {}).get("practice_time") or ""),
            qualifying_time=str((data or {}).get("qualifying_time") or ""),
            race_time=str((data or {}).get("race_time") or ""),
        )


def save_league_profile(path, profile):
    path = Path(path)
    if not profile.name.strip():
        raise ValueError("League name is required.")
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(profile.to_dict(), indent=2) + "\n", encoding="utf-8")
    return path


def load_league_profile(path):
    path = Path(path)
    return LeagueProfile.from_dict(json.loads(path.read_text(encoding="utf-8"))) if path.exists() else LeagueProfile()


def save_schedule(path, events):
    path = Path(path)
    events = sorted(events, key=lambda event: event.round_number)
    seen = set()
    for event in events:
        event.validate()
        if event.round_number in seen:
            raise ValueError(f"Round {event.round_number} is listed more than once.")
        seen.add(event.round_number)
    path.parent.mkdir(parents=True, exist_ok=True)
    payload = {"schema_version": LEAGUE_SCHEMA_VERSION, "events": [asdict(event) for event in events]}
    path.write_text(json.dumps(payload, indent=2) + "\n", encoding="utf-8")
    return path


def load_schedule(path):
    path = Path(path)
    if not path.exists():
        return []
    data = json.loads(path.read_text(encoding="utf-8"))
    return [ScheduleEvent.from_dict(item) for item in data.get("events") or []]


def active_iracing_league_snapshot(ir=None):
    """Read league/event identity from the locally running simulator; no web login is used."""
    owns_sdk = ir is None
    if owns_sdk:
        import irsdk
        ir = irsdk.IRSDK()
        if not ir.startup():
            raise RuntimeError("iRacing is not running or no active session is available.")
    try:
        weekend = ir["WeekendInfo"] or {}
        session_info = ir["SessionInfo"] or {}
        league_id = weekend.get("LeagueID")
        sessions = session_info.get("Sessions") or []
        race = next((item for item in sessions if str(item.get("SessionName", "")).casefold() == "race"), None)
        current = race or (sessions[-1] if sessions else {})
        laps = current.get("SessionLaps")
        if isinstance(laps, str) and not laps.isdigit():
            laps = None
        return {
            "league_id": int(league_id) if str(league_id or "").isdigit() and int(league_id) > 0 else None,
            "league_name": str(weekend.get("LeagueName") or weekend.get("SeriesName") or "").strip(),
            "season_name": str(weekend.get("SeasonName") or weekend.get("SeriesName") or "").strip(),
            "track_name": str(weekend.get("TrackDisplayName") or weekend.get("TrackName") or "").strip(),
            "configuration": str(weekend.get("TrackConfigName") or "").strip(),
            "laps": int(laps) if str(laps or "").isdigit() and int(laps) > 0 else None,
        }
    finally:
        if owns_sdk:
            ir.shutdown()


@dataclass
class RaceResultEntry:
    position: int
    name: str
    car_number: str = ""
    starting_position: int | None = None
    laps_completed: int = 0
    laps_led: int = 0
    fastest_lap: float | None = None
    incidents: int | None = None
    status: str = ""
    points: float = 0
    team_name: str = ""
    country_code: str = ""
    average_lap: float | None = None
    interval: str = ""
    position_points: float = 0
    bonus_points: float = 0
    penalty_points: float = 0
    stage_points: float = 0
    time_penalty_seconds: float = 0
    lap_penalty_laps: int = 0
    manual_adjustment: float = 0
    adjustment_reason: str = ""

    @classmethod
    def from_dict(cls, data):
        data = data or {}
        return cls(
            position=int(data.get("position") or 0), name=str(data.get("name") or ""),
            car_number=str(data.get("car_number") or ""),
            starting_position=int(data["starting_position"]) if data.get("starting_position") is not None else None,
            laps_completed=int(data.get("laps_completed") or 0), laps_led=int(data.get("laps_led") or 0),
            fastest_lap=float(data["fastest_lap"]) if data.get("fastest_lap") is not None else None,
            incidents=int(data["incidents"]) if data.get("incidents") is not None else None,
            status=str(data.get("status") or ""), points=float(data.get("points") or 0),
            team_name=str(data.get("team_name") or ""),
            country_code=str(data.get("country_code") or ""),
            average_lap=float(data["average_lap"]) if data.get("average_lap") is not None else None,
            interval=str(data.get("interval") or ""),
            position_points=float(data.get("position_points") or 0),
            bonus_points=float(data.get("bonus_points") or 0),
            penalty_points=float(data.get("penalty_points") or 0),
            stage_points=float(data.get("stage_points") or 0),
            time_penalty_seconds=float(data.get("time_penalty_seconds") or 0),
            lap_penalty_laps=int(data.get("lap_penalty_laps") or 0),
            manual_adjustment=float(data.get("manual_adjustment") or 0),
            adjustment_reason=str(data.get("adjustment_reason") or ""),
        )


@dataclass
class RaceResult:
    round_number: int
    event_name: str
    track_name: str
    entries: list[RaceResultEntry] = field(default_factory=list)

    @classmethod
    def from_dict(cls, data):
        data = data or {}
        return cls(
            round_number=int(data.get("round_number") or 1),
            event_name=str(data.get("event_name") or ""),
            track_name=str(data.get("track_name") or ""),
            entries=[RaceResultEntry.from_dict(item) for item in data.get("entries") or []],
        )


def score_race_result(result, scoring):
    fastest = min((entry.fastest_lap for entry in result.entries if entry.fastest_lap and entry.fastest_lap > 0), default=None)
    most_led = max((entry.laps_led for entry in result.entries), default=0)
    for entry in result.entries:
        bonuses = []
        if entry.starting_position == 1:
            bonuses.append("Pole")
        if fastest is not None and entry.fastest_lap == fastest:
            bonuses.append("Fastest Lap")
        if entry.laps_led > 0:
            bonuses.append("Led a Lap")
        if most_led > 0 and entry.laps_led == most_led:
            bonuses.append("Most Laps Led")
        if entry.incidents == 0:
            bonuses.append("Incident Free")
        calculation = scoring.calculate(entry.position, bonus_names=bonuses)
        entry.position_points = calculation["finish_points"]
        entry.bonus_points = sum(item["amount"] for item in calculation["bonuses"])
        entry.penalty_points = abs(sum(item["amount"] for item in calculation["penalties"]))
        entry.points = calculation["total"] + entry.stage_points + entry.manual_adjustment
    return result


def calculate_standings(results):
    drivers = {}
    for race in results:
        for entry in race.entries:
            key = entry.name.casefold().strip() or f"number:{entry.car_number}"
            row = drivers.setdefault(key, {"name": entry.name, "car_number": entry.car_number, "starts": 0, "wins": 0, "top_fives": 0, "top_tens": 0, "poles": 0, "laps_led": 0, "points": 0.0, "finish_total": 0})
            row["starts"] += 1
            row["wins"] += int(entry.position == 1)
            row["top_fives"] += int(entry.position <= 5)
            row["top_tens"] += int(entry.position <= 10)
            row["poles"] += int(entry.starting_position == 1)
            row["laps_led"] += entry.laps_led
            row["points"] += entry.points
            row["finish_total"] += entry.position
            row["last_finish"] = entry.position
    standings = []
    for row in drivers.values():
        row["average_finish"] = round(row.pop("finish_total") / row["starts"], 2)
        standings.append(row)
    standings.sort(key=lambda row: (-row["points"], -row["wins"], row["average_finish"], row["name"]))
    return standings


def save_race_results(path, results):
    path = Path(path)
    path.parent.mkdir(parents=True, exist_ok=True)
    payload = {"schema_version": RESULTS_SCHEMA_VERSION, "races": [{**asdict(result), "entries": [asdict(entry) for entry in result.entries]} for result in results]}
    path.write_text(json.dumps(payload, indent=2) + "\n", encoding="utf-8")
    return path


def load_race_results(path):
    path = Path(path)
    if not path.exists():
        return []
    return [RaceResult.from_dict(item) for item in json.loads(path.read_text(encoding="utf-8")).get("races") or []]


def active_iracing_race_result(round_number, event_name="", ir=None):
    owns_sdk = ir is None
    if owns_sdk:
        import irsdk
        ir = irsdk.IRSDK()
        if not ir.startup():
            raise RuntimeError("iRacing is not running or no completed race session is available.")
    try:
        weekend = ir["WeekendInfo"] or {}
        session_info = ir["SessionInfo"] or {}
        driver_info = ir["DriverInfo"] or {}
        drivers = {int(item.get("CarIdx")): item for item in driver_info.get("Drivers") or [] if item.get("CarIdx") is not None}
        sessions = session_info.get("Sessions") or []
        race = next((item for item in sessions if str(item.get("SessionName", "")).casefold() == "race"), None)
        if not race or not race.get("ResultsPositions"):
            raise RuntimeError("The active session does not contain completed race results yet.")
        entries = []
        for item in race.get("ResultsPositions") or []:
            car_idx = int(item.get("CarIdx", -1))
            driver = drivers.get(car_idx, {})
            position = int(item.get("Position", -1)) + 1
            if position < 1 or driver.get("CarIsPaceCar"):
                continue
            entries.append(RaceResultEntry(
                position=position,
                name=str(driver.get("UserName") or f"Car {car_idx}"),
                car_number=str(driver.get("CarNumber") or driver.get("CarNumberRaw") or ""),
                starting_position=(int(item.get("StartingPosition")) + 1) if item.get("StartingPosition") is not None else None,
                laps_completed=int(item.get("LapsComplete") or 0), laps_led=int(item.get("LapsLed") or 0),
                fastest_lap=float(item.get("FastestTime")) if item.get("FastestTime") not in (None, -1) else None,
                incidents=int(item.get("Incidents")) if item.get("Incidents") is not None else None,
                status=str(item.get("ReasonOutStr") or ""),
            ))
        return RaceResult(int(round_number), event_name or str(weekend.get("EventType") or "Race"), str(weekend.get("TrackDisplayName") or weekend.get("TrackName") or ""), entries)
    finally:
        if owns_sdk:
            ir.shutdown()
