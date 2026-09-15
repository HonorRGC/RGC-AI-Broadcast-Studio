import argparse
import csv
import html
import re
import sys
from pathlib import Path
from urllib.error import HTTPError, URLError
from urllib.parse import urljoin, urlparse, urlunparse
from urllib.request import HTTPRedirectHandler, Request, build_opener


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
    "about",
    "car_image",
]

SCHEDULE_FIELDS = ["track_name", "schedule_id", "notes"]


class NoAutoRedirect(HTTPRedirectHandler):
    def redirect_request(self, req, fp, code, msg, headers, newurl):
        return None


def url_variants(url):
    parsed = urlparse(str(url or "").strip())
    if not parsed.scheme:
        parsed = urlparse(f"https://{url}")
    path = parsed.path or "/"
    variants = []
    path_parts = [part for part in path.split("/") if part]
    if parsed.netloc.lower() in {"www.velocityleague.gg", "velocityleague.gg"} and path_parts:
        league_slug = path_parts[0]
        remaining_path = "/" + "/".join(path_parts[1:]) if len(path_parts) > 1 else "/"
        variants.append(
            urlunparse(
                (
                    parsed.scheme or "https",
                    f"{league_slug}.velocityleague.gg",
                    remaining_path,
                    "",
                    parsed.query,
                    "",
                )
            )
        )
    hosts = unique(
        [
            parsed.netloc,
            parsed.netloc.removeprefix("www."),
            f"www.{parsed.netloc.removeprefix('www.')}" if parsed.netloc else "",
        ]
    )
    paths = unique([path.rstrip("/") or "/", f"{path.rstrip('/')}/"])
    for host in hosts:
        for candidate_path in paths:
            variants.append(urlunparse((parsed.scheme or "https", host, candidate_path, "", parsed.query, "")))
    return unique(variants)


def fetch_html(url, timeout=20):
    return fetch_html_following_redirects(url, timeout=timeout)


def fetch_html_following_redirects(url, timeout=20, max_redirects=6):
    opener = build_opener(NoAutoRedirect)
    seen = set()
    current = url_variants(url)[0]
    last_error = None
    for _attempt in range(max_redirects + 1):
        if current in seen:
            raise RuntimeError(f"Redirect loop while fetching {url}; last URL was {current}")
        seen.add(current)
        request = velocity_request(current)
        try:
            with opener.open(request, timeout=timeout) as response:
                return response.read().decode("utf-8", errors="replace")
        except HTTPError as error:
            last_error = error
            if error.code not in (301, 302, 303, 307, 308):
                raise
            location = error.headers.get("Location")
            if not location:
                raise
            current = urljoin(current, location)
        except URLError:
            raise
    raise RuntimeError(f"Too many redirects while fetching {url}: {last_error}")


def fetch_first_html(urls, timeout=20):
    errors = []
    for url in urls:
        try:
            return url, fetch_html(url, timeout=timeout)
        except Exception as error:
            errors.append(f"{url}: {error}")
    raise RuntimeError("; ".join(errors))


def velocity_request(url):
    request = Request(
        url,
        headers={
            "User-Agent": "curl/8.0.0 RGC-AI-Broadcast-Studio/1.0",
            "Accept": "*/*",
        },
    )
    return request


def html_to_text(document):
    document = re.sub(r"(?is)<(script|style).*?>.*?</\1>", " ", document or "")
    document = re.sub(r"(?i)<br\s*/?>", "\n", document)
    document = re.sub(r"(?i)</(p|div|li|tr|td|th|h[1-6]|section|article)>", "\n", document)
    text = re.sub(r"(?s)<[^>]+>", " ", document)
    text = html.unescape(text)
    lines = [" ".join(line.split()) for line in text.splitlines()]
    return "\n".join(line for line in lines if line)


def discover_links(base_url, document):
    links = []
    for match in re.finditer(r"""href=["']([^"']+)["']""", document or "", flags=re.I):
        href = html.unescape(match.group(1)).strip()
        if not href or href.startswith(("#", "mailto:", "tel:", "javascript:")):
            continue
        links.append(urljoin(base_url, href))
    return links


def page_candidates(base_url, kind, home_html=""):
    base = base_url.rstrip("/")
    candidates = []
    for link in discover_links(base_url, home_html):
        path = urlparse(link).path.lower()
        if f"/{kind}" in path or path.endswith(f"/{kind}"):
            candidates.append(link)
    candidates.extend([f"{base}/{kind}", f"{base_url.rstrip('/')}/{kind}"])
    return unique(candidates)


def unique(values):
    seen = set()
    cleaned = []
    for value in values:
        key = str(value or "").strip()
        lower = key.lower()
        if key and lower not in seen:
            cleaned.append(key)
            seen.add(lower)
    return cleaned


def first_fetchable_text(urls):
    errors = []
    for url in urls:
        try:
            return url, html_to_text(fetch_html(url))
        except Exception as error:
            errors.append(f"{url}: {error}")
    return "", "\n".join(errors)


def clean_driver_name(value):
    text = str(value or "").strip()
    text = re.sub(r"\s+", " ", text)
    return text


def normalize_number(value):
    text = str(value or "").strip()
    return text.lstrip("#")


def parse_standings_rows(text, series_filter=""):
    lines = [line.strip() for line in str(text or "").splitlines() if line.strip()]
    series_filter = str(series_filter or "").strip().lower()
    rows = []
    current_series = ""
    for index, line in enumerate(lines):
        if series_filter and series_filter in line.lower():
            current_series = line
        if not re.fullmatch(r"P\d{1,3}", line, flags=re.I):
            continue
        position = re.sub(r"\D", "", line)
        window = lines[index + 1 : index + 12]
        name = ""
        number = ""
        points = ""
        wins = ""
        for item in window:
            if not number and re.fullmatch(r"#?[A-Za-z0-9]{1,4}", item) and any(ch.isdigit() for ch in item):
                number = normalize_number(item)
                continue
            if not name and re.search(r"[A-Za-z]", item) and not any(
                token in item.lower()
                for token in ("leader", "gap", "wins", "win", "view profile", "strong", "steady", "hot")
            ):
                name = clean_driver_name(item)
                continue
            if not points and re.fullmatch(r"\d{1,5}", item):
                points = item
                continue
            win_match = re.search(r"(\d+)\s+wins?", item, flags=re.I)
            if win_match:
                wins = win_match.group(1)
        if not name:
            continue
        if series_filter and current_series and series_filter not in current_series.lower():
            continue
        points_to_next = ""
        for item in window:
            gap_match = re.search(r"[−-]\s*(\d+)\s*gap", item, flags=re.I)
            if gap_match:
                points_to_next = gap_match.group(1)
                break
        rows.append(
            {
                "name": name,
                "car_number": number,
                "stats_scope": "season",
                "starts": "",
                "wins": wins,
                "top_fives": "",
                "top_tens": "",
                "poles": "",
                "avg_finish": "",
                "last_finish": "",
                "points_position": position,
                "points_to_next": points_to_next,
                "track_starts": "",
                "track_wins": "",
                "best_track_finish": "",
                "notes": f"Velocity import from {current_series or 'league standings'}; {points} points".strip("; "),
            }
        )
    return dedupe_stats(rows)


def parse_driver_profile_rows(text):
    lines = [line.strip() for line in str(text or "").splitlines() if line.strip()]
    rows = []
    for index, line in enumerate(lines):
        number_match = re.fullmatch(r"#?([A-Za-z0-9]{1,4})", line)
        if not number_match:
            continue
        nearby = lines[max(0, index - 3) : index + 8]
        name = ""
        for item in nearby:
            if item == line:
                continue
            if re.search(r"[A-Za-z]", item) and not any(
                token in item.lower()
                for token in ("starts", "wins", "points", "profile", "series", "rfrl", "velocity")
            ):
                name = clean_driver_name(item)
                break
        if not name:
            continue
        stats_text = " ".join(nearby)
        rows.append(
            {
                "name": name,
                "car_number": number_match.group(1),
                "stats_scope": "career" if "career" in stats_text.lower() else "season",
                "starts": find_stat(stats_text, "Starts"),
                "wins": find_stat(stats_text, "Wins"),
                "top_fives": find_stat(stats_text, "Top 5"),
                "top_tens": find_stat(stats_text, "Top 10"),
                "poles": find_stat(stats_text, "Poles"),
                "avg_finish": find_stat(stats_text, "Avg Finish"),
                "last_finish": "",
                "points_position": "",
                "points_to_next": "",
                "track_starts": "",
                "track_wins": "",
                "best_track_finish": find_stat(stats_text, "Best Finish"),
                "notes": "Velocity driver profile import",
            }
        )
    return dedupe_stats(rows)


def find_stat(text, label):
    match = re.search(rf"{re.escape(label)}\s+([0-9.]+(?:st|nd|rd|th)?)", text, flags=re.I)
    return match.group(1).removesuffix("st").removesuffix("nd").removesuffix("rd").removesuffix("th") if match else ""


def dedupe_stats(rows):
    seen = set()
    cleaned = []
    for row in rows:
        key = (row.get("name", "").casefold(), row.get("car_number", ""), row.get("stats_scope", "season"))
        if not row.get("name") or key in seen:
            continue
        cleaned.append({field: row.get(field, "") for field in STATS_FIELDS})
        seen.add(key)
    return cleaned


def driver_rows_from_stats(stats_rows):
    rows = []
    seen = set()
    for stat in stats_rows:
        key = stat.get("name", "").casefold()
        if not key or key in seen:
            continue
        rows.append(
            {
                "name": stat.get("name", ""),
                "car_number": stat.get("car_number", ""),
                "hometown": "",
                "state": "",
                "country": "",
                "driving_style": "",
                "sponsor": "",
                "about": "",
                "car_image": "",
            }
        )
        seen.add(key)
    return rows


def schedule_token(value):
    token = re.sub(r"[^a-z0-9]+", "-", str(value or "").strip().lower()).strip("-")
    return token or "series"


def parse_schedule_rows(text, series_filter=""):
    lines = [line.strip() for line in str(text or "").splitlines() if line.strip()]
    series_filter = str(series_filter or "").strip().lower()
    rows = []
    for index, line in enumerate(lines):
        round_match = re.fullmatch(r"RD\s+(\d+)", line, flags=re.I)
        if not round_match:
            continue
        round_id = round_match.group(1)
        window = lines[index + 1 : index + 10]
        track = ""
        date_text = ""
        series_name = ""
        lap_text = ""
        for offset, item in enumerate(window):
            if not date_text and re.search(r"\b(MON|TUE|WED|THU|FRI|SAT|SUN)\b", item, flags=re.I):
                date_text = item
                detail_offset = offset + 1
                if detail_offset < len(window) and re.search(r"\b\d{1,2}:\d{2}\s*(AM|PM)\b", window[detail_offset], flags=re.I):
                    detail_offset += 1
                if detail_offset < len(window):
                    series_name = window[detail_offset]
                if detail_offset + 1 < len(window):
                    track = window[detail_offset + 1]
                if detail_offset + 2 < len(window):
                    lap_text = window[detail_offset + 2]
                break
        if series_filter and series_filter not in series_name.lower():
            continue
        if not track:
            for item in window:
                if track:
                    continue
                if any(
                    skip in item.lower()
                    for skip in ("series", "winner", "results", "recap", "laps", "lead chg", "cautions")
                ):
                    continue
                if re.search(
                    r"(speedway|raceway|superspeedway|park|motor|daytona|talladega|pocono|darlington|richmond|kansas|atlanta|iowa|charlotte|phoenix|texas|nashville|vegas|rockingham)",
                    item,
                    flags=re.I,
                ):
                    track = item
        if track:
            schedule_id = f"velocity-rd-{round_id}"
            if series_name:
                schedule_id = f"{schedule_id}-{schedule_token(series_name)}"
            notes = " - ".join(part for part in (date_text, series_name, lap_text) if part)
            rows.append(
                {
                    "track_name": track,
                    "schedule_id": schedule_id,
                    "notes": notes,
                }
            )
    return rows


def write_csv(path, fieldnames, rows):
    path = Path(path)
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("w", newline="", encoding="utf-8") as csv_file:
        writer = csv.DictWriter(csv_file, fieldnames=fieldnames)
        writer.writeheader()
        writer.writerows({field: row.get(field, "") for field in fieldnames} for row in rows)


def run_import(args):
    home_url, home_html = fetch_first_html(url_variants(args.url))
    home_text = html_to_text(home_html)
    schedule_url, schedule_text = first_fetchable_text(page_candidates(home_url, "schedule", home_html))
    standings_url, standings_text = first_fetchable_text(page_candidates(home_url, "standings", home_html))
    drivers_url, drivers_text = first_fetchable_text(page_candidates(home_url, "drivers", home_html))

    standings_rows = parse_standings_rows("\n".join([home_text, standings_text]), args.series)
    driver_stat_rows = parse_driver_profile_rows(drivers_text)
    schedule_rows = parse_schedule_rows(schedule_text or home_text, args.series)
    stats_rows = dedupe_stats(standings_rows + driver_stat_rows)
    driver_rows = driver_rows_from_stats(stats_rows)

    if args.dry_run:
        print(f"Velocity League URL: {home_url}")
        print(f"Schedule page: {schedule_url or 'not found'}")
        print(f"Standings page: {standings_url or 'not found'}")
        print(f"Drivers page: {drivers_url or 'not found'}")
        print(f"Parsed stats rows: {len(stats_rows)}")
        print(f"Parsed driver rows: {len(driver_rows)}")
        print(f"Parsed schedule rows: {len(schedule_rows)}")
        for row in stats_rows[:10]:
            print(f"STAT {row.get('points_position') or '--'} #{row.get('car_number') or '--'} {row.get('name')}")
        for row in schedule_rows[:10]:
            print(f"SCHEDULE {row.get('schedule_id')} {row.get('track_name')} {row.get('notes')}")
        return 0

    if args.stats_output:
        write_csv(args.stats_output, STATS_FIELDS, stats_rows)
    if args.drivers_output:
        write_csv(args.drivers_output, DRIVER_FIELDS, driver_rows)
    if args.schedule_output:
        write_csv(args.schedule_output, SCHEDULE_FIELDS, schedule_rows)
    print(f"Imported {len(stats_rows)} Velocity stat row(s) to {args.stats_output}.")
    print(f"Imported {len(driver_rows)} Velocity driver row(s) to {args.drivers_output}.")
    print(f"Imported {len(schedule_rows)} Velocity schedule row(s) to {args.schedule_output}.")
    return 0


def build_parser():
    parser = argparse.ArgumentParser(description="Import public Velocity League data for RGC AI Broadcast Studio.")
    parser.add_argument("url", help="Velocity league home URL, for example https://www.velocityleague.gg/trrl")
    parser.add_argument("--series", default="", help="Optional series name filter, for example Truck Series")
    parser.add_argument("--stats-output", default="league/season.csv")
    parser.add_argument("--drivers-output", default="league/drivers.csv")
    parser.add_argument("--schedule-output", default="league/race_schedule.csv")
    parser.add_argument("--dry-run", action="store_true")
    return parser


def main(argv=None):
    args = build_parser().parse_args(argv)
    try:
        return run_import(args)
    except Exception as error:
        print(f"Velocity import failed: {error}", file=sys.stderr)
        return 1


if __name__ == "__main__":
    raise SystemExit(main())
