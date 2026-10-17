import argparse
import json
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from production.wordpress_publisher import (
    WordPressPublishSettings,
    build_wordpress_payload,
    publish_league_to_wordpress,
)


def build_payload(folder, league_slug="", season_slug=""):
    return build_wordpress_payload(
        folder,
        WordPressPublishSettings(league_slug=league_slug, season_slug=season_slug),
    )


def publish(endpoint, username, application_password, payload, timeout=30):
    raise RuntimeError("Use publish_league_to_wordpress with a League Manager folder.")


def main(argv=None):
    parser = argparse.ArgumentParser(description="Publish one RGC League Manager profile to WordPress.")
    parser.add_argument("folder", help="League Manager folder containing league.json, schedule.json, and results.json")
    parser.add_argument("--endpoint", required=True, help="WordPress /wp-json/rgc-league-manager/v1/sync endpoint")
    parser.add_argument("--username", required=True)
    parser.add_argument("--application-password", required=True)
    parser.add_argument("--league-slug", default="")
    parser.add_argument("--season-slug", default="")
    parser.add_argument("--preview", action="store_true")
    args = parser.parse_args(argv)
    settings = WordPressPublishSettings(
        endpoint=args.endpoint,
        username=args.username,
        application_password=args.application_password,
        league_slug=args.league_slug,
        season_slug=args.season_slug,
    )
    payload = build_wordpress_payload(args.folder, settings)
    if args.preview:
        print(json.dumps(payload, indent=2))
        return 0
    result = publish_league_to_wordpress(args.folder, settings)
    print(json.dumps(result, indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
