import argparse
import csv
from datetime import date, datetime
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

SCHEDULE_FIELDS = [
    "track_name",
    "schedule_id",
    "results_url",
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


def load_source(source, series_id="", season_id="", schedule_mode=False):
    if source.startswith("http://") or source.startswith("https://"):
        source = (
            normalize_sim_racer_hub_schedule_source(source, series_id=series_id, season_id=season_id)
            if schedule_mode
            else normalize_sim_racer_hub_source(source, series_id=series_id, season_id=season_id)
        )
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


def normalize_sim_racer_hub_schedule_source(source, series_id="", season_id=""):
    parsed = urlparse(source)
    if not parsed.netloc.endswith("simracerhub.com"):
        return source

    query = parse_qs(parsed.query)
    selected_series_id = query.get("series_id", [series_id])[0]
    selected_season_id = query.get("season_id", [season_id])[0]
    path = parsed.path or "/"
    is_home_page = path in ("", "/")
    is_stats_page = path.endswith("/league_stats.php") or path == "league_stats.php"
    is_series_page = path.endswith("/series_seasons.php") or path == "series_seasons.php"
    if not is_home_page and not is_stats_page and not is_series_page:
        return source

    replacement_query = {}
    if selected_series_id:
        replacement_query["series_id"] = selected_series_id
    if selected_season_id:
        replacement_query["season_id"] = selected_season_id

    return urlunparse(
        parsed._replace(
            path="/series_seasons.php",
            query=urlencode(replacement_query),
        )
    )


def normalize_sim_racer_hub_standings_source(source, season_id="", schedule_id=""):
    parsed = urlparse(source)
    if not parsed.netloc.endswith("simracerhub.com"):
        return source

    query = parse_qs(parsed.query)
    selected_season_id = query.get("season_id", [season_id])[0]
    selected_schedule_id = query.get("schedule_id", [schedule_id])[0]
    replacement_query = {}
    if selected_season_id:
        replacement_query["season_id"] = selected_season_id
    if selected_schedule_id:
        replacement_query["schedule_id"] = selected_schedule_id
    return urlunparse(
        parsed._replace(
            path="/season_standings.php",
            query=urlencode(replacement_query),
        )
    )


def sim_racer_hub_query_value(source, key):
    parsed = urlparse(str(source or ""))
    if not parsed.netloc.endswith("simracerhub.com"):
        return ""
    return parse_qs(parsed.query).get(key, [""])[0]


def extract_driver_name(page_html):
    match = re.search(r"<h1[^>]*>(.*?)</h1>", page_html, re.IGNORECASE | re.DOTALL)
    if not match:
        return ""
    return clean_driver_name(html.unescape(strip_tags(match.group(1))).strip())


def extract_json_object(page_html, key):
    value = extract_json_value(page_html, key)
    return value if isinstance(value, dict) else {}


def extract_json_collection(page_html, key):
    value = extract_json_value(page_html, key)
    if isinstance(value, dict):
        return value.values()
    if isinstance(value, list):
        return value
    return []


def extract_json_value(page_html, key):
    start = -1
    marker = ""
    for candidate in (f"{key}:", f'"{key}":', f"'{key}':"):
        found = page_html.find(candidate)
        if found >= 0 and (start < 0 or found < start):
            start = found
            marker = candidate
    if start < 0:
        return {}

    value_start = -1
    opener = ""
    closer = ""
    for index in range(start + len(marker), len(page_html)):
        char = page_html[index]
        if char in "{[":
            value_start = index
            opener = char
            closer = "}" if char == "{" else "]"
            break
        if char not in " \r\n\t":
            return {}
    if value_start < 0:
        return {}

    stack = []
    in_string = False
    escape = False

    for index in range(value_start, len(page_html)):
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
        elif char in "{[":
            stack.append("}" if char == "{" else "]")
        elif char in "}]":
            if not stack or char != stack[-1]:
                return {}
            stack.pop()
            if not stack:
                return json.loads(page_html[value_start : index + 1])

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


def summarize_race_schedule(
    page_html,
    league_id="",
    series_id="",
    season_id="",
    source_url="https://simracerhub.com",
    first_schedule_id="",
):
    configs = extract_json_object(page_html, "configs")
    rows_by_key = {}

    for race in schedule_records_from_json(page_html):
        if not schedule_record_matches_filters(race, league_id, series_id, season_id):
            continue
        row = schedule_row_from_record(race, configs, source_url)
        add_schedule_row(rows_by_key, row)

    for row in schedule_rows_from_links(page_html, source_url, season_id=season_id):
        add_schedule_row(rows_by_key, row)

    if first_schedule_id and not rows_by_key:
        for row in schedule_rows_from_race_participants(
            page_html,
            configs,
            source_url,
            league_id=league_id,
            series_id=series_id,
            season_id=season_id,
            first_schedule_id=first_schedule_id,
        ):
            add_schedule_row(rows_by_key, row)

    rows = list(rows_by_key.values())
    rows.sort(key=schedule_sort_key)
    return rows


def merge_schedule_rows(*row_groups):
    rows_by_key = {}
    for rows in row_groups:
        for row in rows or []:
            add_schedule_row(rows_by_key, row)
    rows = list(rows_by_key.values())
    rows.sort(key=schedule_sort_key)
    return rows


def schedule_records_from_json(page_html):
    records = []
    for key in ("schedules", "schedule", "races", "race_schedule", "events"):
        records.extend(extract_json_collection(page_html, key))

    race_participants = extract_json_object(page_html, "rps")
    if race_participants:
        grouped = {}
        for race in race_participants.values():
            schedule_id = schedule_id_from_record(race)
            if not schedule_id:
                continue
            grouped.setdefault(schedule_id, race)
        records.extend(grouped.values())

    return [record for record in records if isinstance(record, dict)]


def schedule_record_matches_filters(record, league_id="", series_id="", season_id=""):
    checks = (
        ("league_id", league_id),
        ("series_id", series_id),
        ("season_id", season_id),
    )
    for key, wanted in checks:
        if not wanted:
            continue
        value = str((record or {}).get(key) or "").strip()
        if value and value != str(wanted):
            return False
    return True


def schedule_row_from_record(record, configs, source_url):
    schedule_id = schedule_id_from_record(record)
    track_name = track_name_from_record(record, configs)
    if not track_name and str(record.get("chase") or "").upper() == "Y":
        track_name = "Championship"
    results_url = str(
        record.get("results_url")
        or record.get("race_url")
        or record.get("url")
        or ""
    ).strip()
    if results_url and results_url.startswith("/"):
        results_url = sim_racer_hub_race_url(source_url, schedule_id) if schedule_id else ""
    notes = str(
        record.get("race_name")
        or record.get("event_name")
        or record.get("race_date_str")
        or record.get("race_date_fmt")
        or record.get("race_date")
        or ""
    ).strip()
    return {
        "track_name": track_name,
        "schedule_id": schedule_id,
        "results_url": results_url,
        "notes": notes,
    }


def schedule_rows_from_links(page_html, source_url, season_id=""):
    rows = []
    pattern = re.compile(
        r"<a[^>]+href=[\"'](?P<href>[^\"']*[^\"']*schedule_id=(?P<id>\d+)[^\"']*)[\"'][^>]*>(?P<label>.*?)</a>",
        re.IGNORECASE | re.DOTALL,
    )
    for match in pattern.finditer(page_html or ""):
        href = html.unescape(match.group("href")).strip()
        parsed = urlparse(href)
        query = parse_qs(parsed.query)
        link_season_id = query.get("season_id", [""])[0]
        if season_id and link_season_id and str(link_season_id) != str(season_id):
            continue
        label = html.unescape(strip_tags(match.group("label"))).strip()
        rows.append(
            {
                "track_name": label,
                "schedule_id": match.group("id"),
                "results_url": absolute_sim_racer_hub_url(source_url, href),
                "notes": "",
            }
        )
    return rows


def schedule_rows_from_race_participants(
    page_html,
    configs,
    source_url,
    league_id="",
    series_id="",
    season_id="",
    first_schedule_id="",
):
    first_id = int_or_none(first_schedule_id)
    if first_id is None:
        return []

    race_participants = extract_json_object(page_html, "rps")
    if not race_participants:
        return []

    grouped = {}
    for race in filter_races(race_participants.values(), league_id, series_id, season_id):
        key = schedule_fallback_group_key(race)
        if not key:
            continue
        grouped.setdefault(key, race)

    records = sorted(grouped.values(), key=lambda record: (race_sort_key(record), track_name_from_record(record, configs)))
    rows = []
    for index, record in enumerate(records):
        schedule_id = str(first_id + index)
        row = schedule_row_from_record(record, configs, source_url)
        row["schedule_id"] = schedule_id
        row["results_url"] = sim_racer_hub_race_url(source_url, schedule_id)
        if not row["notes"]:
            race_number = index + 1
            date_text = str(record.get("race_date") or "")[:10]
            row["notes"] = f"Race {race_number}" + (f" - {date_text}" if date_text else "")
        rows.append(row)
    return rows


def schedule_fallback_group_key(record):
    schedule_id = schedule_id_from_record(record)
    if schedule_id:
        return ("schedule", schedule_id)
    race_date = str((record or {}).get("race_date") or "").strip()
    race_timestamp = str((record or {}).get("race_timestamp") or "").strip()
    track_config_id = str((record or {}).get("track_config_id") or "").strip()
    race_name = str((record or {}).get("race_name") or "").strip()
    if race_date or race_timestamp or track_config_id:
        return (race_date, race_timestamp, track_config_id, race_name)
    return None


def add_schedule_row(rows_by_key, row):
    row = {field: str((row or {}).get(field, "") or "").strip() for field in SCHEDULE_FIELDS}
    if not row["schedule_id"] and not row["results_url"]:
        return
    if not row["track_name"]:
        row["track_name"] = row["notes"] or f"Race {len(rows_by_key) + 1}"
    key = row["schedule_id"] or row["results_url"]
    existing = rows_by_key.get(key)
    if existing:
        for field in SCHEDULE_FIELDS:
            if not existing.get(field) and row.get(field):
                existing[field] = row[field]
        return
    rows_by_key[key] = row


def schedule_id_from_record(record):
    for key in ("schedule_id", "race_schedule_id", "season_race_id", "race_id", "id"):
        value = str((record or {}).get(key) or "").strip()
        if value:
            return value
    return ""


def track_name_from_record(record, configs):
    for key in (
        "track_name",
        "track_display_name",
        "track_config_name",
        "track_config_short",
        "track",
    ):
        value = str((record or {}).get(key) or "").strip()
        if value:
            return value

    config_id = str((record or {}).get("track_config_id") or record.get("config_id") or "").strip()
    config = configs.get(config_id, {}) if config_id else {}
    for key in ("track_name", "track_config_name", "track_config_short", "type_name"):
        value = str(config.get(key) or "").strip()
        if value:
            return value
    return ""


def schedule_sort_key(row):
    notes = str((row or {}).get("notes") or "")
    date_match = re.search(r"\d{4}-\d{2}-\d{2}", notes)
    if date_match:
        parsed = parse_iso_date(date_match.group(0))
        if parsed:
            return (parsed.toordinal(), normalize(row.get("track_name")))
    parsed = parse_sim_racer_hub_date(notes)
    if parsed:
        return (parsed.toordinal(), normalize(row.get("track_name")))
    return (int_or_zero((row or {}).get("schedule_id")), normalize(row.get("track_name")))


def sim_racer_hub_race_url(source_url, schedule_id):
    base = sim_racer_hub_base_url(source_url)
    return f"{base}/scoring/season_race.php?schedule_id={schedule_id}"


def absolute_sim_racer_hub_url(source_url, href):
    href = str(href or "").strip()
    if href.startswith("http://") or href.startswith("https://"):
        return href
    base = sim_racer_hub_base_url(source_url)
    if href.startswith("/"):
        return f"{base}{href}"
    if href.endswith(".php") or ".php?" in href:
        return f"{base}/{href.lstrip('/')}"
    return f"{base}/scoring/{href}"


def sim_racer_hub_base_url(source_url):
    parsed = urlparse(str(source_url or "https://simracerhub.com"))
    scheme = parsed.scheme or "https"
    netloc = parsed.netloc or "simracerhub.com"
    return f"{scheme}://{netloc}".rstrip("/")


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


def write_race_schedule(output_path, rows):
    output_path = Path(output_path)
    output_path.parent.mkdir(parents=True, exist_ok=True)
    with output_path.open("w", newline="", encoding="utf-8") as csv_file:
        writer = csv.DictWriter(csv_file, fieldnames=SCHEDULE_FIELDS)
        writer.writeheader()
        writer.writerows({field: row.get(field, "") for field in SCHEDULE_FIELDS} for row in rows)


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


def parse_sim_racer_hub_date(value):
    text = str(value or "").strip()
    for fmt in ("%b %d, %Y", "%B %d, %Y"):
        try:
            return datetime.strptime(text, fmt).date()
        except Exception:
            continue
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
        "--schedule-only",
        action="store_true",
        help="Import a race schedule CSV instead of stats.",
    )
    parser.add_argument(
        "--schedule-output",
        default="league/race_schedule.csv",
        help="Race schedule CSV to write when --schedule-only is used.",
    )
    parser.add_argument(
        "--first-schedule-id",
        default="",
        help="Optional first Sim Racer Hub schedule_id. If the schedule page does not expose IDs, IDs are assigned sequentially from this value.",
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
    effective_season_id = args.season_id or sim_racer_hub_query_value(args.source, "season_id")
    effective_first_schedule_id = (
        args.first_schedule_id
        or sim_racer_hub_query_value(args.source, "schedule_id")
    )

    if args.schedule_only:
        schedule_source = normalize_sim_racer_hub_schedule_source(
            args.source,
            series_id=args.series_id,
            season_id=effective_season_id,
        )
        page_html = fetch_url(schedule_source) if args.source.startswith(("http://", "https://")) else load_source(args.source)
        rows = summarize_race_schedule(
            page_html,
            league_id=args.league_id,
            series_id=args.series_id,
            season_id=effective_season_id,
            source_url=schedule_source,
            first_schedule_id=effective_first_schedule_id,
        )
        if effective_first_schedule_id and args.source.startswith(("http://", "https://")):
            standings_source = normalize_sim_racer_hub_standings_source(
                args.source,
                season_id=effective_season_id,
                schedule_id=effective_first_schedule_id,
            )
            if standings_source != schedule_source:
                standings_html = fetch_url(standings_source)
                standings_rows = summarize_race_schedule(
                    standings_html,
                    league_id=args.league_id,
                    series_id=args.series_id,
                    season_id=effective_season_id,
                    source_url=standings_source,
                    first_schedule_id=effective_first_schedule_id,
                )
                rows = merge_schedule_rows(rows, standings_rows)
        if not rows and effective_first_schedule_id and args.source.startswith(("http://", "https://")):
            fallback_source = normalize_sim_racer_hub_source(
                args.source,
                series_id=args.series_id,
                season_id=effective_season_id,
            )
            fallback_html = fetch_url(fallback_source)
            rows = summarize_race_schedule(
                fallback_html,
                league_id=args.league_id,
                series_id=args.series_id,
                season_id=effective_season_id,
                source_url=fallback_source,
                first_schedule_id=effective_first_schedule_id,
            )
        if args.dry_run:
            writer = csv.DictWriter(sys.stdout, fieldnames=SCHEDULE_FIELDS)
            writer.writeheader()
            writer.writerows(rows)
            return 0
        write_race_schedule(args.schedule_output, rows)
        print(f"Imported {len(rows)} race schedule rows -> {args.schedule_output}")
        return 0

    page_html = load_source(
        args.source,
        series_id=args.series_id,
        season_id=effective_season_id,
        schedule_mode=False,
    )

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
