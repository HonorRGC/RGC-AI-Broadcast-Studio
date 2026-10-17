from __future__ import annotations

import csv
import re
import time
from pathlib import Path

from production.league_manager import (
    RaceResult,
    RaceResultEntry,
    load_race_results,
    load_schedule,
    load_scoring_system,
    save_race_results,
    save_schedule,
    score_race_result,
)
from production.wordpress_publisher import load_wordpress_settings, publish_league_to_wordpress


class AutomaticLeagueResultsRecorder:
    """Persist one stable, completed race into the selected league profile."""

    DRIVER_FIELDS = ("name", "car_number", "hometown", "state", "country", "driving_style", "sponsor", "about", "car_image")

    def __init__(self, enabled=False, league_folder=None, driver_loader=None, driver_saver=None):
        self.enabled = bool(enabled)
        self.league_folder = Path(league_folder) if league_folder else None
        self.driver_loader = driver_loader
        self.driver_saver = driver_saver
        self.done = False
        self.last_signature = ()
        self.stable_ticks = 0

    def reset(self):
        self.done = False
        self.last_signature = ()
        self.stable_ticks = 0

    def update(self, source, engine):
        if not self.enabled or self.done or not self.league_folder:
            return None
        director = getattr(engine, "race_director", None)
        if not getattr(director, "post_race_results_queued", False):
            return None
        results = list(source.get_results() or [])
        if not results:
            return None
        signature = self._signature(results)
        self.stable_ticks = self.stable_ticks + 1 if signature == self.last_signature else 1
        self.last_signature = signature
        if self.stable_ticks < 5:
            return None

        ai_enabled = bool(getattr(getattr(engine, "openai_director", None), "is_enabled", lambda: False)())
        if ai_enabled:
            queue = getattr(engine, "broadcast_queue", None)
            if queue and (getattr(queue, "items", []) or time.time() < float(getattr(queue, "busy_until", 0) or 0)):
                return None
        elif int(getattr(source, "get_session_state", lambda: 0)() or 0) < 5:
            return None

        result = self._build_result(source, results)
        saved = load_race_results(self.league_folder / "results.json")
        if any(item.round_number == result.round_number for item in saved):
            self.done = True
            return f"League Manager already has results for Round {result.round_number}; no duplicate was created."
        scoring = load_scoring_system(self.league_folder / "scoring.json")
        score_race_result(result, scoring)
        saved.append(result)
        save_race_results(self.league_folder / "results.json", saved)
        self._complete_schedule_round(result.round_number)
        added = self._add_missing_drivers(result)
        self.done = True
        message = f"League Manager automatically saved Round {result.round_number}: {len(result.entries)} results and {added} new driver profile(s)."
        website = load_wordpress_settings(self.league_folder / "wordpress.json")
        if website.auto_publish:
            try:
                published = publish_league_to_wordpress(self.league_folder, website)
                message += f" Published {published.get('league', 'league')} to the RGC website."
            except Exception as error:
                message += f" Website publish failed: {error}"
        return message

    def _build_result(self, source, results):
        schedule = load_schedule(self.league_folder / "schedule.json")
        track_info = source.get_track_info() or {}
        track_name = str(
            track_info.get("track_name")
            or track_info.get("TrackDisplayName")
            or track_info.get("TrackName")
            or ""
        ).strip()
        scheduled = self._scheduled_round(schedule, track_name)
        round_number = scheduled.round_number if scheduled else max((race.round_number for race in load_race_results(self.league_folder / "results.json")), default=0) + 1
        event_name = scheduled.event_name if scheduled else track_name or "Race"
        lookup = source.get_driver_lookup() or {}
        zero_based = any(self._int(item.get("Position"), 999) == 0 for item in results)
        entries = []
        for item in sorted(results, key=lambda row: self._int(row.get("Position"), 999)):
            car_idx = item.get("CarIdx")
            if car_idx is None:
                continue
            driver = lookup.get(car_idx, lookup.get(str(car_idx), {})) or {}
            if driver.get("CarIsPaceCar"):
                continue
            raw_position = self._int(item.get("Position"), -1)
            position = raw_position + 1 if zero_based else raw_position
            if position < 1:
                continue
            start = item.get("StartingPosition")
            start = self._int(start, -1) + (1 if zero_based else 0) if start is not None else None
            entries.append(RaceResultEntry(
                position=position,
                # Live telemetry exposes a normalized driver lookup (name/number),
                # while direct SDK result rows use the legacy UserName/CarNumber
                # spelling.  Accept both so automatic post-race saves never fall
                # back to internal CarIdx labels such as "Car 7".
                name=str(driver.get("name") or driver.get("UserName") or item.get("UserName") or f"Car {car_idx}"),
                car_number=str(driver.get("number") or driver.get("CarNumber") or driver.get("CarNumberRaw") or item.get("CarNumber") or ""),
                starting_position=start if start and start > 0 else None,
                laps_completed=self._int(item.get("LapsComplete"), 0),
                laps_led=self._int(item.get("LapsLed"), 0),
                fastest_lap=self._float_or_none(item.get("FastestTime")),
                incidents=self._int_or_none(item.get("Incidents")),
                status=str(item.get("ReasonOutStr") or ""),
            ))
        if not entries:
            raise RuntimeError("League Manager could not find classified race results to save.")
        return RaceResult(round_number, event_name, track_name, entries)

    def _scheduled_round(self, schedule, track_name):
        open_rounds = [event for event in schedule if event.status.casefold() != "completed"]
        target = self._key(track_name)
        return next((event for event in open_rounds if target and (target in self._key(event.track_name) or self._key(event.track_name) in target)), open_rounds[0] if open_rounds else None)

    def _complete_schedule_round(self, round_number):
        path = self.league_folder / "schedule.json"
        schedule = load_schedule(path)
        for event in schedule:
            if event.round_number == round_number:
                event.status = "Completed"
        save_schedule(path, schedule)

    def _add_missing_drivers(self, result):
        path = self.league_folder / "drivers.csv"
        rows = self.driver_loader(path) if self.driver_loader else self._load_drivers(path)
        names = {str(row.get("name") or "").casefold().strip() for row in rows}
        numbers = {str(row.get("car_number") or "").strip() for row in rows if row.get("car_number")}
        added = 0
        for entry in result.entries:
            if entry.name.casefold().strip() in names or (entry.car_number and entry.car_number in numbers):
                continue
            rows.append({"name": entry.name, "car_number": entry.car_number})
            names.add(entry.name.casefold().strip())
            numbers.add(entry.car_number)
            added += 1
        if self.driver_saver:
            self.driver_saver(path, rows)
        else:
            self._save_drivers(path, rows)
        return added

    def _load_drivers(self, path):
        if not path.exists():
            return []
        with path.open(newline="", encoding="utf-8-sig") as file:
            return [{field: str(row.get(field) or "").strip() for field in self.DRIVER_FIELDS} for row in csv.DictReader(file)]

    def _save_drivers(self, path, rows):
        path.parent.mkdir(parents=True, exist_ok=True)
        with path.open("w", newline="", encoding="utf-8") as file:
            writer = csv.DictWriter(file, fieldnames=self.DRIVER_FIELDS)
            writer.writeheader()
            writer.writerows([{field: str(row.get(field) or "").strip() for field in self.DRIVER_FIELDS} for row in rows])

    @staticmethod
    def _signature(results):
        return tuple((item.get("CarIdx"), item.get("Position"), item.get("LapsComplete"), item.get("ReasonOutId")) for item in results)

    @staticmethod
    def _key(value):
        return re.sub(r"[^a-z0-9]+", "", str(value or "").casefold())

    @staticmethod
    def _int(value, default=0):
        try:
            return int(value)
        except (TypeError, ValueError):
            return default

    @classmethod
    def _int_or_none(cls, value):
        return None if value is None else cls._int(value)

    @staticmethod
    def _float_or_none(value):
        try:
            number = float(value)
            return number if number > 0 else None
        except (TypeError, ValueError):
            return None
