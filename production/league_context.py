import csv
from dataclasses import dataclass
from pathlib import Path

from config import LEAGUE_DRIVERS_CSV, LEAGUE_STATS_CSV, USE_LEAGUE_DRIVER_NOTES


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
    car_image: str = ""

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
            "car_image": self.car_image,
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


@dataclass(frozen=True)
class DriverStats:
    name: str = ""
    car_number: str = ""
    starts: str = ""
    wins: str = ""
    top_fives: str = ""
    top_tens: str = ""
    poles: str = ""
    avg_finish: str = ""
    last_finish: str = ""
    points_position: str = ""
    points_to_next: str = ""
    track_starts: str = ""
    track_wins: str = ""
    best_track_finish: str = ""
    notes: str = ""

    def as_dict(self):
        return {
            "name": self.name,
            "car_number": self.car_number,
            "starts": self.starts,
            "wins": self.wins,
            "top_fives": self.top_fives,
            "top_tens": self.top_tens,
            "poles": self.poles,
            "avg_finish": self.avg_finish,
            "last_finish": self.last_finish,
            "points_position": self.points_position,
            "points_to_next": self.points_to_next,
            "track_starts": self.track_starts,
            "track_wins": self.track_wins,
            "best_track_finish": self.best_track_finish,
            "notes": self.notes,
        }

    def context_summary(self):
        details = []
        if self.points_position:
            point_text = f"points: {self.ordinal(self.points_position)}"
            if self.points_to_next:
                point_text += f", {self.points_to_next} points to the next spot"
            details.append(point_text)
        if self.last_finish:
            details.append(f"last race finish: {self.ordinal(self.last_finish)}")
        if self.wins:
            details.append(f"season wins: {self.wins}")
        if self.top_fives:
            details.append(f"top fives: {self.top_fives}")
        if self.avg_finish:
            details.append(f"average finish: {self.avg_finish}")
        if self.track_starts:
            track_text = f"track starts: {self.track_starts}"
            if self.track_wins:
                track_text += f", track wins: {self.track_wins}"
            if self.best_track_finish:
                track_text += f", best track finish: {self.ordinal(self.best_track_finish)}"
            details.append(track_text)
        if self.notes:
            details.append(f"stat note: {self.notes}")

        if not details:
            return ""

        label = self.name or f"car {self.car_number}"
        if self.car_number:
            label = f"{label} in the number {self.car_number}"
        return f"{label} stats: " + "; ".join(details)

    @staticmethod
    def ordinal(value):
        text = str(value or "").strip()
        try:
            number = int(float(text))
        except Exception:
            return text
        if 10 <= number % 100 <= 20:
            suffix = "th"
        else:
            suffix = {1: "st", 2: "nd", 3: "rd"}.get(number % 10, "th")
        return f"{number}{suffix}"


class LeagueContext:
    """
    Loads optional league-supplied driver notes.

    This is intentionally CSV-first so a league admin can edit the file in
    Excel, Google Sheets, or a plain text editor without adding a database.
    """

    def __init__(
        self,
        drivers_csv_path=LEAGUE_DRIVERS_CSV,
        stats_csv_path=LEAGUE_STATS_CSV,
        enabled=USE_LEAGUE_DRIVER_NOTES,
    ):
        self.drivers_csv_path = Path(drivers_csv_path)
        self.stats_csv_path = Path(stats_csv_path)
        self.enabled = bool(enabled)
        self.profiles_by_name = {}
        self.profiles_by_number = {}
        self.stats_by_name = {}
        self.stats_by_number = {}
        self.load()

    def is_configured(self):
        return self.enabled and bool(
            self.profiles_by_name
            or self.profiles_by_number
            or self.stats_by_name
            or self.stats_by_number
        )

    def load(self):
        self.profiles_by_name = {}
        self.profiles_by_number = {}
        self.stats_by_name = {}
        self.stats_by_number = {}

        if not self.enabled:
            return

        self.load_driver_profiles()
        self.load_driver_stats()

    def load_driver_profiles(self):
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

    def load_driver_stats(self):
        if not self.stats_csv_path.exists():
            return
        with self.stats_csv_path.open(newline="", encoding="utf-8-sig") as csv_file:
            for row in csv.DictReader(csv_file):
                stats = self.stats_from_row(row)
                if not stats.name and not stats.car_number:
                    continue
                if stats.name:
                    self.stats_by_name[self.normalize(stats.name)] = stats
                if stats.car_number:
                    self.stats_by_number[self.normalize_number(stats.car_number)] = stats

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
            car_image=self.clean(row.get("car_image") or row.get("car_image_url")),
        )

    def stats_from_row(self, row):
        return DriverStats(
            name=self.clean(row.get("name") or row.get("driver")),
            car_number=self.clean(row.get("car_number") or row.get("number")),
            starts=self.clean(row.get("starts") or row.get("races")),
            wins=self.clean(row.get("wins")),
            top_fives=self.clean(row.get("top_fives") or row.get("top5")),
            top_tens=self.clean(row.get("top_tens") or row.get("top10")),
            poles=self.clean(row.get("poles")),
            avg_finish=self.clean(row.get("avg_finish") or row.get("average_finish")),
            last_finish=self.clean(row.get("last_finish")),
            points_position=self.clean(row.get("points_position") or row.get("points_rank")),
            points_to_next=self.clean(row.get("points_to_next")),
            track_starts=self.clean(row.get("track_starts")),
            track_wins=self.clean(row.get("track_wins")),
            best_track_finish=self.clean(row.get("best_track_finish")),
            notes=self.clean(row.get("notes") or row.get("stats_note")),
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
            stats = self.stats_for_driver(updated_info)
            if stats:
                stats_dict = stats.as_dict()
                updated_info["league_stats"] = stats_dict
                summary = stats.context_summary()
                if summary:
                    updated_info["league_stats_summary"] = summary
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
        for car_idx in getattr(item, "participant_car_indices", ()) or ():
            self.add_summary(
                self.stats_for_driver((driver_lookup or {}).get(car_idx, {})),
                summaries,
                seen,
            )
            if len(summaries) >= max_profiles:
                return summaries[:max_profiles]

        self.add_summary(
            self.stats_for_driver(assignment_info),
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

    def stats_for_driver(self, driver_info):
        name = self.clean((driver_info or {}).get("name"))
        number = self.clean(
            (driver_info or {}).get("number")
            or (driver_info or {}).get("car_number")
        )

        if name:
            stats = self.stats_by_name.get(self.normalize(name))
            if stats:
                return stats

        if number:
            return self.stats_by_number.get(self.normalize_number(number))

        return None

    def add_summary(self, profile, summaries, seen):
        if not profile:
            return
        summary = profile.context_summary()
        if not summary:
            return
        key = f"{profile.__class__.__name__}:{self.normalize(profile.name or profile.car_number)}"
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
