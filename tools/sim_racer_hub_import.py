import argparse
import csv
from datetime import date
import html
import json
import re
import sys
from pathlib import Path
from urllib.parse import parse_qs, urlencode, urlparse, urlunparse
from urllib.request import Request, urlopen


STATS_FIELDS = [
    "name",
    "car_number",
    "stats_scope",
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

DRIVER_FIELDS = [
    "name",
    "car_number",
    "hometown",
    "state",
    "country",
    "driving_style",
    "sponsor",
    "notes",
    "car_image",
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


def load_source(source, series_id="", season_id=""):
    if source.startswith("http://") or source.startswith("https://"):
        source = normalize_sim_racer_hub_source(source, series_id=series_id, season_id=season_id)
        return fetch_url(source)
    return Path(source).read_text(encoding="utf-8")


def normalize_sim_racer_hub_source(source, series_id="", season_id=""):
    parsed = urlparse(source)
    if not parsed.netloc.endswith("simracerhub.com"):
        return source

    query = parse_qs(parsed.query)
    selected_series_id = query.get("series_id", [series_id])[0]
    selected_season_id = query.get("season_id", [season_id])[0]
    path = parsed.path or "/"
    is_home_page = path in ("", "/")
    is_series_page = path.endswith("/series_seasons.php") or path == "series_seasons.php"
    if not is_home_page and not is_series_page:
        return source

    replacement_query = {}
    if selected_series_id:
        replacement_query["series_id"] = selected_series_id
    if selected_season_id:
        replacement_query["season_id"] = selected_season_id

    return urlunparse(
        parsed._replace(
            path="/league_stats.php",
            query=urlencode(replacement_query),
        )
    )


def extract_driver_name(page_html):
    match = re.search(r"<h1[^>]*>(.*?)</h1>", page_html, re.IGNORECASE | re.DOTALL)
    if not match:
        return ""
    return clean_driver_name(html.unescape(strip_tags(match.group(1))).strip())


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
        key=race_sort_key,
        reverse=True,
    )


def resolve_track_ids(page_html, track_name="", track_id="", track_config_id=""):
    track_ids = {
        "track_ids": set(),
        "track_config_ids": set(),
    }

    if track_id:
        track_ids["track_ids"].add(str(track_id))
    if track_config_id:
        track_ids["track_config_ids"].add(str(track_config_id))
    if not track_name:
        return track_ids

    configs = extract_json_object(page_html, "configs")
    wanted = normalize(track_name)
    for config_id, config in configs.items():
        names = [
            config.get("track_name"),
            config.get("track_config_name"),
            config.get("track_config_short"),
            config.get("type_name"),
        ]
        searchable = " ".join(str(name or "") for name in names)
        if wanted and wanted in normalize(searchable):
            track_ids["track_config_ids"].add(str(config_id))
            if config.get("track_id"):
                track_ids["track_ids"].add(str(config.get("track_id")))

    return track_ids


def summarize_driver_stats(
    page_html,
    league_id="",
    series_id="",
    season_id="",
    track_id="",
    track_config_id="",
    track_name="",
):
    driver_name = extract_driver_name(page_html)
    race_map = extract_json_object(page_html, "rps")
    races = filter_races(race_map.values(), league_id, series_id, season_id)

    if not races:
        raise ValueError("No Sim Racer Hub races matched the requested filters.")

    return summarize_races(
        races,
        driver_name=driver_name,
        track_ids=resolve_track_ids(page_html, track_name, track_id, track_config_id),
        stats_scope=stats_scope_for_filters(season_id),
    )


def summarize_bulk_driver_stats(
    page_html,
    league_id="",
    series_id="",
    season_id="",
    track_id="",
    track_config_id="",
    track_name="",
    min_starts=1,
):
    race_map = extract_json_object(page_html, "rps")
    drivers = extract_json_object(page_html, "drivers")
    races = filter_races(race_map.values(), league_id, series_id, season_id)
    track_ids = resolve_track_ids(page_html, track_name, track_id, track_config_id)

    grouped = {}
    for race in races:
        driver_id = str(race.get("driver_id") or "").strip()
        if not driver_id:
            continue
        grouped.setdefault(driver_id, []).append(race)

    rows = []
    for driver_id, driver_races in grouped.items():
        if len(driver_races) < int(min_starts or 1):
            continue
        driver_info = drivers.get(driver_id, {})
        rows.append(
            summarize_races(
                driver_races,
                driver_name=clean_driver_name(driver_info.get("driver_name", "")),
                track_ids=track_ids,
                stats_scope=stats_scope_for_filters(season_id),
            )
        )

    return sorted(
        rows,
        key=lambda row: (
            -int_or_zero(row.get("starts")),
            float_or_large(row.get("avg_finish")),
            normalize(row.get("name")),
        ),
    )


def summarize_driver_roster(
    page_html,
    league_id="",
    series_id="",
    season_id="",
    min_starts=1,
):
    race_map = extract_json_object(page_html, "rps")
    drivers = extract_json_object(page_html, "drivers")
    races = filter_races(race_map.values(), league_id, series_id, season_id)

    grouped = {}
    for race in races:
        driver_id = str(race.get("driver_id") or "").strip()
        if not driver_id:
            continue
        grouped.setdefault(driver_id, []).append(race)

    rows = []
    for driver_id, driver_races in grouped.items():
        if len(driver_races) < int(min_starts or 1):
            continue
        driver_info = drivers.get(driver_id, {})
        name = clean_driver_name(driver_info.get("driver_name", ""))
        if not name:
            continue
        most_recent = sorted(driver_races, key=race_sort_key, reverse=True)[0]
        rows.append(
            {
                "name": name,
                "car_number": str(most_recent.get("driver_number") or ""),
                "hometown": "",
                "state": "",
                "country": country_name(driver_info.get("flair_country_code")),
                "driving_style": "",
                "sponsor": "",
                "notes": "",
                "car_image": "",
            }
        )

    return sorted(rows, key=lambda row: normalize(row.get("name")))


def summarize_races(
    races,
    driver_name="",
    track_ids=None,
    stats_scope="season",
):
    races = sorted(
        races,
        key=race_sort_key,
        reverse=True,
    )
    if not races:
        raise ValueError("Cannot summarize an empty race list.")

    finishes = [int_or_none(race.get("finish_pos_class") or race.get("finish_pos")) for race in races]
    finishes = [finish for finish in finishes if finish is not None]
    qualify_positions = [
        int_or_none(race.get("qualify_pos_class") or race.get("qualify_pos")) for race in races
    ]
    qualify_positions = [position for position in qualify_positions if position is not None]

    track_races = []
    track_ids = track_ids or {}
    track_config_ids = {str(value) for value in track_ids.get("track_config_ids", set()) if value}
    base_track_ids = {str(value) for value in track_ids.get("track_ids", set()) if value}
    if track_config_ids or base_track_ids:
        for race in races:
            if str(race.get("track_config_id")) in track_config_ids:
                track_races.append(race)
            elif str(race.get("track_id")) in base_track_ids:
                track_races.append(race)

    track_finishes = [
        int_or_none(race.get("finish_pos_class") or race.get("finish_pos"))
        for race in track_races
    ]
    track_finishes = [finish for finish in track_finishes if finish is not None]
    most_recent_track = track_races[0] if track_races else None

    most_recent = races[0]
    total_laps_led = sum(int_or_zero(race.get("laps_led")) for race in races)
    total_incidents = sum(int_or_zero(race.get("incidents")) for race in races)
    total_passes = sum(int_or_zero(race.get("passes")) for race in races)
    quality_passes = sum(int_or_zero(race.get("quality_passes")) for race in races)
    closing_passes = sum(int_or_zero(race.get("closing_passes")) for race in races)
    total_points = sum(int_or_zero(race.get("race_points")) for race in races)
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
    if total_points:
        notes.append(f"{total_points} race points")
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
    if most_recent_track and track_finishes:
        notes.append(
            "last track race "
            f"{most_recent_track.get('race_date_str') or most_recent_track.get('race_date')}: "
            f"finished {ordinal(track_finishes[0])}"
        )

    return {
        "name": driver_name,
        "car_number": str(most_recent.get("driver_number") or ""),
        "stats_scope": stats_scope or "season",
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


def stats_scope_for_filters(season_id=""):
    return "season" if str(season_id or "").strip() else "career"


def merge_stats_row(output_path, new_row):
    output_path = Path(output_path)
    output_path.parent.mkdir(parents=True, exist_ok=True)
    rows = []

    if output_path.exists():
        with output_path.open(newline="", encoding="utf-8-sig") as csv_file:
            reader = csv.DictReader(csv_file)
            for row in reader:
                rows.append({field: row.get(field, "") for field in STATS_FIELDS})

    key_name = normalize_driver_name(new_row.get("name"))
    key_number = normalize_number(new_row.get("car_number"))
    key_scope = normalize_stats_scope(new_row.get("stats_scope"))
    updated = False
    merged = []

    for row in rows:
        same_name = key_name and normalize_driver_name(row.get("name")) == key_name
        same_number = key_number and normalize_number(row.get("car_number")) == key_number
        same_scope = normalize_stats_scope(row.get("stats_scope")) == key_scope
        if (same_name or same_number) and same_scope:
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


def merge_stats_rows(output_path, new_rows):
    for row in new_rows:
        merge_stats_row(output_path, row)


def normalize_stats_scope(value):
    text = str(value or "season").strip().casefold()
    if text in ("career", "all", "all_seasons", "all seasons"):
        return "career"
    return "season"


def merge_driver_roster(output_path, new_rows):
    output_path = Path(output_path)
    output_path.parent.mkdir(parents=True, exist_ok=True)
    existing_rows = []

    if output_path.exists():
        with output_path.open(newline="", encoding="utf-8-sig") as csv_file:
            reader = csv.DictReader(csv_file)
            for row in reader:
                existing_rows.append({field: row.get(field, "") for field in DRIVER_FIELDS})

    merged_by_name = {}
    order = []
    for row in existing_rows:
        key = normalize_driver_name(row.get("name"))
        if not key:
            continue
        if key not in merged_by_name:
            order.append(key)
        row["name"] = clean_driver_name(row.get("name"))
        merged_by_name[key] = {field: row.get(field, "") for field in DRIVER_FIELDS}

    for new_row in new_rows:
        key = normalize_driver_name(new_row.get("name"))
        if not key:
            continue
        if key not in merged_by_name:
            order.append(key)
            merged_by_name[key] = {field: "" for field in DRIVER_FIELDS}

        current = merged_by_name[key]
        current["name"] = clean_driver_name(current.get("name") or new_row.get("name"))
        for field in ("car_number", "country"):
            if new_row.get(field) and not current.get(field):
                current[field] = new_row.get(field, "")

    with output_path.open("w", newline="", encoding="utf-8") as csv_file:
        writer = csv.DictWriter(csv_file, fieldnames=DRIVER_FIELDS)
        writer.writeheader()
        writer.writerows(merged_by_name[key] for key in order)


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


def race_sort_key(race):
    timestamp = int_or_zero((race or {}).get("race_timestamp"))
    if timestamp:
        return timestamp
    race_date = parse_iso_date((race or {}).get("race_date"))
    if race_date:
        return race_date.toordinal()
    return 0


def parse_iso_date(value):
    try:
        return date.fromisoformat(str(value or "")[:10])
    except Exception:
        return None


def float_or_none(value):
    try:
        return float(str(value))
    except Exception:
        return None


def float_or_large(value):
    number = float_or_none(value)
    return number if number is not None else 999999.0


def normalize(value):
    return str(value or "").strip().casefold()


def normalize_driver_name(value):
    return normalize(clean_driver_name(value))


def clean_driver_name(value):
    name = str(value or "").strip()
    return re.sub(r"(?<=[A-Za-z])\d+$", "", name).strip()


def normalize_number(value):
    return str(value or "").strip().lstrip("#").casefold()


def ordinal(value):
    number = int_or_none(value)
    if number is None:
        return str(value or "")
    if 10 <= number % 100 <= 20:
        suffix = "th"
    else:
        suffix = {1: "st", 2: "nd", 3: "rd"}.get(number % 10, "th")
    return f"{number}{suffix}"


def plural(count, singular, plural_text=None):
    return singular if int(count) == 1 else (plural_text or f"{singular}s")


def country_name(value):
    code = str(value or "").strip().upper()
    if not code:
        return ""
    return {
        "US": "USA",
        "CA": "Canada",
        "GB": "United Kingdom",
        "AU": "Australia",
        "NZ": "New Zealand",
        "MX": "Mexico",
    }.get(code, code)


def build_parser():
    parser = argparse.ArgumentParser(
        description="Import Sim Racer Hub stats into league/stats.csv."
    )
    parser.add_argument(
        "source",
        help="Sim Racer Hub driver_stats or league_stats URL, or a saved HTML file.",
    )
    parser.add_argument("--output", default="league/stats.csv", help="Stats CSV to update.")
    parser.add_argument("--league-id", default="", help="Only include this Sim Racer Hub league ID.")
    parser.add_argument("--series-id", default="", help="Only include this Sim Racer Hub series ID.")
    parser.add_argument("--season-id", default="", help="Only include this Sim Racer Hub season ID.")
    parser.add_argument("--track-id", default="", help="Optional current track ID for track-history stats.")
    parser.add_argument(
        "--track-name",
        default="",
        help="Optional track name, such as Nashville or Michigan, for track-history stats.",
    )
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
    parser.add_argument(
        "--bulk",
        action="store_true",
        help="Treat source as a Sim Racer Hub league_stats page and import all matching drivers.",
    )
    parser.add_argument(
        "--drivers-only",
        action="store_true",
        help="Import a driver roster CSV instead of stats.",
    )
    parser.add_argument(
        "--drivers-output",
        default="league/drivers.csv",
        help="Driver roster CSV to update when --drivers-only is used.",
    )
    parser.add_argument(
        "--min-starts",
        default="1",
        help="Bulk mode only: only import drivers with at least this many starts.",
    )
    return parser


def main(argv=None):
    args = build_parser().parse_args(argv)
    page_html = load_source(args.source, series_id=args.series_id, season_id=args.season_id)

    if args.bulk:
        if args.drivers_only:
            rows = summarize_driver_roster(
                page_html,
                league_id=args.league_id,
                series_id=args.series_id,
                season_id=args.season_id,
                min_starts=args.min_starts,
            )
            if args.dry_run:
                writer = csv.DictWriter(sys.stdout, fieldnames=DRIVER_FIELDS)
                writer.writeheader()
                writer.writerows(rows)
                return 0
            merge_driver_roster(args.drivers_output, rows)
            print(f"Imported {len(rows)} driver roster rows -> {args.drivers_output}")
            return 0

        rows = summarize_bulk_driver_stats(
            page_html,
            league_id=args.league_id,
            series_id=args.series_id,
            season_id=args.season_id,
            track_id=args.track_id,
            track_config_id=args.track_config_id,
            track_name=args.track_name,
            min_starts=args.min_starts,
        )

        if args.dry_run:
            writer = csv.DictWriter(sys.stdout, fieldnames=STATS_FIELDS)
            writer.writeheader()
            writer.writerows(rows)
            return 0

        merge_stats_rows(args.output, rows)
        print(f"Imported {len(rows)} drivers -> {args.output}")
        return 0

    row = summarize_driver_stats(
        page_html,
        league_id=args.league_id,
        series_id=args.series_id,
        season_id=args.season_id,
        track_id=args.track_id,
        track_config_id=args.track_config_id,
        track_name=args.track_name,
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
