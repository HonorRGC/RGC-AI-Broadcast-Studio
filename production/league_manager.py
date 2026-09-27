from __future__ import annotations

import json
from dataclasses import asdict, dataclass, field
from pathlib import Path


SCORING_SCHEMA_VERSION = 1


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

