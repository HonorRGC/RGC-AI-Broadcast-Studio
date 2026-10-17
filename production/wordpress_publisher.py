from __future__ import annotations

import base64
import json
import re
from dataclasses import asdict, dataclass
from pathlib import Path
from urllib.request import Request, urlopen

from production.league_manager import load_league_profile, load_race_results, load_schedule


@dataclass
class WordPressPublishSettings:
    endpoint: str = "https://realisticgamingcrew.com/wp-json/rgc-league-manager/v1/sync"
    username: str = ""
    application_password: str = ""
    league_slug: str = ""
    season_slug: str = ""
    auto_publish: bool = False

    @classmethod
    def from_dict(cls, data):
        data = data or {}
        return cls(
            endpoint=str(data.get("endpoint") or cls.endpoint),
            username=str(data.get("username") or ""),
            application_password=str(data.get("application_password") or ""),
            league_slug=str(data.get("league_slug") or ""),
            season_slug=str(data.get("season_slug") or ""),
            auto_publish=bool(data.get("auto_publish", False)),
        )


def slugify(value, fallback):
    slug = re.sub(r"[^a-z0-9]+", "-", str(value or "").strip().casefold()).strip("-")
    return slug or fallback


def load_wordpress_settings(path):
    path = Path(path)
    profile_data = {}
    try:
        if path.exists():
            profile_data = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, ValueError, TypeError):
        profile_data = {}
    settings = WordPressPublishSettings.from_dict(profile_data)
    shared_path = path.parent.parent / "wordpress_connection.json"
    try:
        shared = json.loads(shared_path.read_text(encoding="utf-8")) if shared_path.exists() else {}
    except (OSError, ValueError, TypeError):
        shared = {}
    if shared.get("endpoint"):
        settings.endpoint = str(shared["endpoint"])
    if shared.get("username"):
        settings.username = str(shared["username"])
    if shared.get("application_password"):
        settings.application_password = str(shared["application_password"])
    return settings


def save_wordpress_settings(path, settings):
    path = Path(path)
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(asdict(settings), indent=2), encoding="utf-8")
    shared_path = path.parent.parent / "wordpress_connection.json"
    shared_path.write_text(
        json.dumps(
            {
                "endpoint": settings.endpoint,
                "username": settings.username,
                "application_password": settings.application_password,
            },
            indent=2,
        ),
        encoding="utf-8",
    )


def build_wordpress_payload(folder, settings=None):
    folder = Path(folder)
    settings = settings or load_wordpress_settings(folder / "wordpress.json")
    league = load_league_profile(folder / "league.json")
    schedule = load_schedule(folder / "schedule.json")
    results = load_race_results(folder / "results.json")
    return {
        "league": {
            "slug": settings.league_slug or slugify(league.name, folder.name),
            "name": league.name,
            "short_name": league.short_name,
        },
        "season": {
            "slug": settings.season_slug or slugify(league.season_name, "current-season"),
            "name": league.season_name or "Current Season",
        },
        "schedule": [asdict(item) for item in schedule],
        "results": [asdict(item) for item in results],
    }


def publish_league_to_wordpress(folder, settings=None, timeout=30):
    folder = Path(folder)
    settings = settings or load_wordpress_settings(folder / "wordpress.json")
    if not settings.endpoint.strip():
        raise ValueError("Enter the WordPress League Manager endpoint.")
    if not settings.username.strip() or not settings.application_password.strip():
        raise ValueError("Enter the WordPress username and Application Password.")
    token = base64.b64encode(
        f"{settings.username.strip()}:{settings.application_password.strip()}".encode("utf-8")
    ).decode("ascii")
    request = Request(
        settings.endpoint.strip(),
        data=json.dumps(build_wordpress_payload(folder, settings)).encode("utf-8"),
        headers={
            "Authorization": f"Basic {token}",
            "Content-Type": "application/json",
            "User-Agent": "RGC-AI-Broadcast-Studio",
        },
        method="POST",
    )
    with urlopen(request, timeout=timeout) as response:
        result = json.loads(response.read().decode("utf-8"))
    if not result.get("ok"):
        raise RuntimeError(f"WordPress did not confirm the league upload: {result}")
    return result
