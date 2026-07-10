import argparse
import csv
import html
import json
import re
import sys
from pathlib import Path
from urllib.request import Request, urlopen


STATS_FIELDS = [
    "name",
    "car_number",
    "starts",
    "wins",
    "top_fives",
    "top_tens",
    "poles",
    "avg_finish",
    "last_finish",
    "points_position",
    "points_to_next",
    "track_starts",
    "track_wins",
    "best_track_finish",
    "notes",
]


def fetch_url(url):
    request = Request(
        url,
        headers={
            "User-Agent": (
                "Mozilla/5.0 RGC-AI-Broadcast-Studio "
                "(Sim Racer Hub stats importer)"
            )
        },
    )
    with urlopen(request, timeout=20) as response:
        return response.read().decode("utf-8", errors="replace")


def load_source(source):
    if source.startswith("http://") or source.startswith("https://"):
        return fetch_url(source)
    return Path(source).read_text(encoding="utf-8")


def extract_driver_name(page_html):
    match = re.search(r"<h1[^>]*>(.*?)</h1>", page_html, re.IGNORECASE | re.DOTALL)
    if not match:
        return ""
    return html.unescape(strip_tags(match.group(1))).strip()


def extract_json_object(page_html, key):
    marker = f"{key}:"
    start = page_html.find(marker)
    if start < 0:
        return {}

    brace_start = page_html.find("{", start)
    if brace_start < 0:
        return {}

    depth = 0
    in_string = False
    escape = False

    for index in range(brace_start, len(page_html)):
        char = page_html[index]
        if in_string:
            if escape:
                escape = False
            elif char == "\\":
                escape = True
            elif char == '"':
                in_string = False
            continue

        if char == '"':
            in_string = True
        elif char == "{":
            depth += 1
        elif char == "}":
            depth -= 1
            if depth == 0:
                return json.loads(page_html[brace_start : index + 1])

    return {}


def strip_tags(text):
    return re.sub(r"<[^>]+>", "", text or "")


def filter_races(races, league_id="", series_id="", season_id=""):
    filtered = []
    for race in races:
        if league_id and str(race.get("league_id")) != str(league_id):
            continue
        if series_id and str(race.get("series_id")) != str(series_id):
            continue
        if season_id and str(race.get("season_id")) != str(season_id):
            continue
        filtered.append(race)
    return sorted(
        filtered,
        key=lambda race: int_or_zero(race.get("race_timestamp")),
        reverse=True,
    )


def summarize_driver_stats(
    page_html,
    league_id="",
    series_id="",
    season_id="",
    track_id="",
    track_config_id="",
):
    driver_name = extract_driver_name(page_html)
    race_map = extract_json_object(page_html, "rps")
    races = filter_races(race_map.values(), league_id, series_id, season_id)

    if not races:
        raise ValueError("No Sim Racer Hub races matched the requested filters.")

    finishes = [int_or_none(race.get("finish_pos_class") or race.get("finish_pos")) for race in races]
    finishes = [finish for finish in finishes if finish is not None]
    qualify_positions = [
        int_or_none(race.get("qualify_pos_class") or race.get("qualify_pos")) for race in races
    ]
    qualify_positions = [position for position in qualify_positions if position is not None]

    track_races = []
    if track_config_id:
        track_races = [
            race for race in races if str(race.get("track_config_id")) == str(track_config_id)
        ]
    elif track_id:
        track_races = [race for race in races if str(race.get("track_id")) == str(track_id)]

    track_finishes = [
        int_or_none(race.get("finish_pos_class") or race.get("finish_pos"))
        for race in track_races
    ]
    track_finishes = [finish for finish in track_finishes if finish is not None]

    most_recent = races[0]
    total_laps_led = sum(int_or_zero(race.get("laps_led")) for race in races)
    total_incidents = sum(int_or_zero(race.get("incidents")) for race in races)
    total_passes = sum(int_or_zero(race.get("passes")) for race in races)
    quality_passes = sum(int_or_zero(race.get("quality_passes")) for race in races)
    closing_passes = sum(int_or_zero(race.get("closing_passes")) for race in races)
    avg_start = average(qualify_positions)
    avg_pos_values = [
        float_or_none(race.get("avg_pos")) for race in races if race.get("avg_pos") not in (None, "")
    ]
    avg_running_position = average(
        [value for value in avg_pos_values if value is not None],
        digits=1,
    )

    notes = [
        f"Sim Racer Hub import from {len(races)} race(s)",
        f"last race {most_recent.get('race_date_str') or most_recent.get('race_date')}",
    ]
    if total_laps_led:
        notes.append(f"{total_laps_led} {plural(total_laps_led, 'lap')} led")
    if total_passes:
        notes.append(f"{total_passes} passes, {quality_passes} quality passes, {closing_passes} closing passes")
    if total_incidents:
        notes.append(f"{total_incidents} incidents")
    if avg_start:
        notes.append(f"average start {avg_start}")
    if avg_running_position:
        notes.append(f"average running position {avg_running_position}")

    return {
        "name": driver_name,
        "car_number": str(most_recent.get("driver_number") or ""),
        "starts": str(len(races)),
        "wins": str(count_finishes_at_or_better(finishes, 1)),
        "top_fives": str(count_finishes_at_or_better(finishes, 5)),
        "top_tens": str(count_finishes_at_or_better(finishes, 10)),
        "poles": str(count_finishes_at_or_better(qualify_positions, 1)),
        "avg_finish": average(finishes),
        "last_finish": str(finishes[0]) if finishes else "",
        "points_position": "",
        "points_to_next": "",
        "track_starts": str(len(track_races)) if track_races else "",
        "track_wins": str(count_finishes_at_or_better(track_finishes, 1)) if track_races else "",
        "best_track_finish": str(min(track_finishes)) if track_finishes else "",
        "notes": "; ".join(notes),
    }


def merge_stats_row(output_path, new_row):
    output_path = Path(output_path)
    output_path.parent.mkdir(parents=True, exist_ok=True)
    rows = []

    if output_path.exists():
        with output_path.open(newline="", encoding="utf-8-sig") as csv_file:
            reader = csv.DictReader(csv_file)
            for row in reader:
                rows.append({field: row.get(field, "") for field in STATS_FIELDS})

    key_name = normalize(new_row.get("name"))
    key_number = normalize_number(new_row.get("car_number"))
    updated = False
    merged = []

    for row in rows:
        same_name = key_name and normalize(row.get("name")) == key_name
        same_number = key_number and normalize_number(row.get("car_number")) == key_number
        if same_name or same_number:
            merged.append({field: new_row.get(field, "") for field in STATS_FIELDS})
            updated = True
        else:
            merged.append(row)

    if not updated:
        merged.append({field: new_row.get(field, "") for field in STATS_FIELDS})

    with output_path.open("w", newline="", encoding="utf-8") as csv_file:
        writer = csv.DictWriter(csv_file, fieldnames=STATS_FIELDS)
        writer.writeheader()
        writer.writerows(merged)


def count_finishes_at_or_better(values, threshold):
    return sum(1 for value in values if value <= threshold)


def average(values, digits=1):
    values = [value for value in values if value is not None]
    if not values:
        return ""
    return f"{sum(values) / len(values):.{digits}f}"


def int_or_none(value):
    try:
        return int(float(str(value)))
    except Exception:
        return None


def int_or_zero(value):
    number = int_or_none(value)
    return number if number is not None else 0


def float_or_none(value):
    try:
        return float(str(value))
    except Exception:
        return None


def normalize(value):
    return str(value or "").strip().casefold()


def normalize_number(value):
    return str(value or "").strip().lstrip("#").casefold()


def plural(count, singular, plural_text=None):
    return singular if int(count) == 1 else (plural_text or f"{singular}s")


def build_parser():
    parser = argparse.ArgumentParser(
        description="Import one Sim Racer Hub driver stats page into league/stats.csv."
    )
    parser.add_argument("source", help="Sim Racer Hub driver_stats URL or saved HTML file.")
    parser.add_argument("--output", default="league/stats.csv", help="Stats CSV to update.")
    parser.add_argument("--league-id", default="", help="Only include this Sim Racer Hub league ID.")
    parser.add_argument("--series-id", default="", help="Only include this Sim Racer Hub series ID.")
    parser.add_argument("--season-id", default="", help="Only include this Sim Racer Hub season ID.")
    parser.add_argument("--track-id", default="", help="Optional current track ID for track-history stats.")
    parser.add_argument(
        "--track-config-id",
        default="",
        help="Optional current track config ID for track-history stats.",
    )
    parser.add_argument(
        "--dry-run",
        action="store_true",
        help="Print the imported row without writing the output CSV.",
    )
    return parser


def main(argv=None):
    args = build_parser().parse_args(argv)
    page_html = load_source(args.source)
    row = summarize_driver_stats(
        page_html,
        league_id=args.league_id,
        series_id=args.series_id,
        season_id=args.season_id,
        track_id=args.track_id,
        track_config_id=args.track_config_id,
    )

    if args.dry_run:
        writer = csv.DictWriter(sys.stdout, fieldnames=STATS_FIELDS)
        writer.writeheader()
        writer.writerow(row)
        return 0

    merge_stats_row(args.output, row)
    print(
        f"Imported {row['name'] or 'driver'}: {row['starts']} starts, "
        f"{row['wins']} wins, avg finish {row['avg_finish']} -> {args.output}"
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
