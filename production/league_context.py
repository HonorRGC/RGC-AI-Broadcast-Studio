import csv
from dataclasses import dataclass
from pathlib import Path

from config import LEAGUE_DRIVERS_CSV, USE_LEAGUE_DRIVER_NOTES


@dataclass(frozen=True)
class DriverProfile:
    name: str = ""
    car_number: str = ""
    hometown: str = ""
    state: str = ""
    country: str = ""
    driving_style: str = ""
    sponsor: str = ""
    notes: str = ""

    def location(self):
        parts = [self.hometown, self.state, self.country]
        return ", ".join(part for part in parts if part)

    def as_dict(self):
        return {
            "name": self.name,
            "car_number": self.car_number,
            "hometown": self.hometown,
            "state": self.state,
            "country": self.country,
            "driving_style": self.driving_style,
            "sponsor": self.sponsor,
            "notes": self.notes,
            "location": self.location(),
        }

    def context_summary(self):
        details = []
        location = self.location()
        if location:
            details.append(f"from {location}")
        if self.driving_style:
            details.append(f"driving style: {self.driving_style}")
        if self.sponsor:
            details.append(f"sponsor: {self.sponsor}")
        if self.notes:
            details.append(f"note: {self.notes}")

        if not details:
            return ""

        label = self.name or f"car {self.car_number}"
        if self.car_number:
            label = f"{label} in the number {self.car_number}"
        return f"{label}: " + "; ".join(details)


class LeagueContext:
    """
    Loads optional league-supplied driver notes.

    This is intentionally CSV-first so a league admin can edit the file in
    Excel, Google Sheets, or a plain text editor without adding a database.
    """

    def __init__(
        self,
        drivers_csv_path=LEAGUE_DRIVERS_CSV,
        enabled=USE_LEAGUE_DRIVER_NOTES,
    ):
        self.drivers_csv_path = Path(drivers_csv_path)
        self.enabled = bool(enabled)
        self.profiles_by_name = {}
        self.profiles_by_number = {}
        self.load()

    def is_configured(self):
        return self.enabled and bool(self.profiles_by_name or self.profiles_by_number)

    def load(self):
        self.profiles_by_name = {}
        self.profiles_by_number = {}

        if not self.enabled:
            return

        if not self.drivers_csv_path.exists():
            return

        with self.drivers_csv_path.open(newline="", encoding="utf-8-sig") as csv_file:
            for row in csv.DictReader(csv_file):
                profile = self.profile_from_row(row)
                if not profile.name and not profile.car_number:
                    continue
                if profile.name:
                    self.profiles_by_name[self.normalize(profile.name)] = profile
                if profile.car_number:
                    self.profiles_by_number[self.normalize_number(profile.car_number)] = profile

    def profile_from_row(self, row):
        return DriverProfile(
            name=self.clean(row.get("name")),
            car_number=self.clean(row.get("car_number") or row.get("number")),
            hometown=self.clean(row.get("hometown")),
            state=self.clean(row.get("state")),
            country=self.clean(row.get("country")),
            driving_style=self.clean(row.get("driving_style") or row.get("style")),
            sponsor=self.clean(row.get("sponsor")),
            notes=self.clean(row.get("notes")),
        )

    def enrich_driver_lookup(self, driver_lookup):
        if not self.enabled:
            return dict(driver_lookup or {})

        enriched = {}

        for car_idx, driver_info in (driver_lookup or {}).items():
            updated_info = dict(driver_info or {})
            profile = self.profile_for_driver(updated_info)
            if profile:
                profile_dict = profile.as_dict()
                updated_info["league_profile"] = profile_dict
                for key, value in profile_dict.items():
                    if value and key not in updated_info:
                        updated_info[key] = value
                summary = profile.context_summary()
                if summary:
                    updated_info["league_context_summary"] = summary
            enriched[car_idx] = updated_info

        return enriched

    def context_for_item(self, item, driver_lookup, max_profiles=3):
        if not self.enabled:
            return []

        summaries = []
        seen = set()

        for car_idx in getattr(item, "participant_car_indices", ()) or ():
            profile = self.profile_for_driver((driver_lookup or {}).get(car_idx, {}))
            self.add_summary(profile, summaries, seen)
            if len(summaries) >= max_profiles:
                return summaries

        assignment_info = {
            "name": getattr(item, "driver_name", ""),
            "number": getattr(item, "car_number", ""),
        }
        self.add_summary(
            self.profile_for_driver(assignment_info),
            summaries,
            seen,
        )
        return summaries[:max_profiles]

    def profile_for_driver(self, driver_info):
        name = self.clean((driver_info or {}).get("name"))
        number = self.clean(
            (driver_info or {}).get("number")
            or (driver_info or {}).get("car_number")
        )

        if name:
            profile = self.profiles_by_name.get(self.normalize(name))
            if profile:
                return profile

        if number:
            return self.profiles_by_number.get(self.normalize_number(number))

        return None

    def add_summary(self, profile, summaries, seen):
        if not profile:
            return
        summary = profile.context_summary()
        if not summary:
            return
        key = self.normalize(profile.name or profile.car_number)
        if key in seen:
            return
        seen.add(key)
        summaries.append(summary)

    @staticmethod
    def clean(value):
        return str(value or "").strip()

    @staticmethod
    def normalize(value):
        return str(value or "").strip().casefold()

    @staticmethod
    def normalize_number(value):
        return str(value or "").strip().lstrip("#").casefold()
