import argparse
import csv
import html
import json
import re
import sys
from pathlib import Path
from urllib.error import HTTPError, URLError
from urllib.parse import parse_qs, urlencode, urljoin, urlparse, urlunparse
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

SCHEDULE_FIELDS = ["track_name", "schedule_id", "results_url", "notes"]


def extract_recap_urls(html_text, base_url, series_key=""):
    urls = []
    for raw_href in re.findall(r'href=["\']([^"\']*/recap/\d+[^"\']*)["\']', str(html_text or ""), flags=re.I):
        href = html.unescape(raw_href)
        url = urljoin(base_url, href)
        if series_key:
            query_series = parse_qs(urlparse(url).query).get("series", [""])[0]
            if query_series and query_series.casefold() != series_key.casefold():
                continue
        if url not in urls:
            urls.append(url)
    return urls


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


def extract_embedded_records(document, name_key="name"):
    """Read Velocity's structured Next.js records instead of guessing from display text."""
    decoded = html.unescape(str(document or "")).replace(r'\"', '"')
    decoder = json.JSONDecoder()
    records = []
    seen = set()
    for match in re.finditer(r'\{"cust_id"', decoded):
        try:
            record, _end = decoder.raw_decode(decoded[match.start() :])
        except (json.JSONDecodeError, TypeError, ValueError):
            continue
        if not isinstance(record, dict) or name_key not in record:
            continue
        signature = json.dumps(record, sort_keys=True, default=str)
        if signature in seen:
            continue
        records.append(record)
        seen.add(signature)
    return records


def parse_structured_standings(document):
    records = extract_embedded_records(document, name_key="display_name")
    # Velocity embeds overview standings for its other series before the table
    # selected by the URL. A repeated customer marks the next complete table;
    # the selected series is the final table rendered in the page payload.
    groups = []
    current_group = []
    current_customers = set()
    for record in records:
        cust_id = str(record.get("cust_id") or "").strip()
        if cust_id and cust_id in current_customers and current_group:
            groups.append(current_group)
            current_group = []
            current_customers = set()
        current_group.append(record)
        if cust_id:
            current_customers.add(cust_id)
    if current_group:
        groups.append(current_group)
    selected_records = groups[-1] if groups else []

    rows = []
    seen_customers = set()
    position = 0
    for record in selected_records:
        cust_id = str(record.get("cust_id") or "").strip()
        if not cust_id or cust_id in seen_customers:
            continue
        name = clean_driver_name(record.get("display_name"))
        number = normalize_number(record.get("car_number"))
        if not name:
            continue
        position += 1
        race_entries = record.get("raceEntries") or record.get("raceDetails") or []
        completed_entries = [entry for entry in race_entries if isinstance(entry, dict)]
        latest = completed_entries[-1] if completed_entries else {}
        rows.append(
            {
                "_cust_id": cust_id,
                "_points": record.get("total_points", ""),
                "name": name,
                "car_number": number,
                "stats_scope": "season",
                "starts": record.get("races", ""),
                "wins": record.get("wins", ""),
                "top_fives": record.get("top5", ""),
                "top_tens": record.get("top10", ""),
                "poles": record.get("poles", ""),
                "avg_finish": average_finish(completed_entries),
                "last_finish": latest.get("finish_pos", ""),
                "points_position": str(position),
                "points_to_next": "",
                "track_starts": "",
                "track_wins": "",
                "best_track_finish": best_finish(completed_entries),
                "notes": f"Velocity season standings; {record.get('total_points', '')} points".strip("; "),
            }
        )
        seen_customers.add(cust_id)
    if rows:
        previous_points = safe_float(rows[0].get("_points"))
        for row in rows:
            points = safe_float(row.get("_points"))
            if row["points_position"] != "1" and previous_points is not None and points is not None:
                row["points_to_next"] = format_number(previous_points - points)
            previous_points = points
    return rows


def parse_structured_career(document):
    rows = []
    seen_customers = set()
    for record in extract_embedded_records(document):
        cust_id = str(record.get("cust_id") or "").strip()
        if not cust_id or cust_id in seen_customers or "starts" not in record:
            continue
        name = clean_driver_name(record.get("name"))
        if not name:
            continue
        rows.append(
            {
                "_cust_id": cust_id,
                "name": name,
                "car_number": normalize_number(record.get("active_car_number") or record.get("car_number")),
                "stats_scope": "career",
                "starts": record.get("starts", ""),
                "wins": record.get("wins", ""),
                "top_fives": record.get("top5", ""),
                "top_tens": record.get("top10", ""),
                "poles": record.get("poles", ""),
                "avg_finish": record.get("avg_finish", ""),
                "last_finish": "",
                "points_position": "",
                "points_to_next": "",
                "track_starts": "",
                "track_wins": "",
                "best_track_finish": "",
                "notes": "Velocity combined league career stats",
            }
        )
        seen_customers.add(cust_id)
    return rows


def extract_series_season_keys(document):
    decoded = html.unescape(str(document or "")).replace(r'\"', '"')
    return unique(re.findall(r'"season_key"\s*:\s*"([^"]+)"', decoded, flags=re.I))


def aggregate_series_career(season_groups):
    """Combine only the selected series' seasons into series-career totals."""
    by_customer = {}
    for season_rows in season_groups:
        for row in season_rows:
            cust_id = str(row.get("_cust_id") or "").strip()
            identity = cust_id or clean_driver_name(row.get("name")).casefold()
            if not identity:
                continue
            current = by_customer.setdefault(
                identity,
                {
                    "_cust_id": cust_id,
                    "name": row.get("name", ""),
                    "car_number": row.get("car_number", ""),
                    "stats_scope": "career",
                    "starts": 0,
                    "wins": 0,
                    "top_fives": 0,
                    "top_tens": 0,
                    "poles": 0,
                    "_finish_total": 0.0,
                    "_finish_starts": 0,
                    "last_finish": "",
                    "best_track_finish": "",
                },
            )
            current["name"] = row.get("name") or current["name"]
            current["car_number"] = row.get("car_number") or current["car_number"]
            starts = int(safe_float(row.get("starts")) or 0)
            current["starts"] += starts
            for target, source in (
                ("wins", "wins"),
                ("top_fives", "top_fives"),
                ("top_tens", "top_tens"),
                ("poles", "poles"),
            ):
                current[target] += int(safe_float(row.get(source)) or 0)
            avg_finish = safe_float(row.get("avg_finish"))
            if avg_finish is not None and starts > 0:
                current["_finish_total"] += avg_finish * starts
                current["_finish_starts"] += starts
            if row.get("last_finish") not in (None, ""):
                current["last_finish"] = row.get("last_finish")
            best = safe_float(row.get("best_track_finish"))
            prior_best = safe_float(current.get("best_track_finish"))
            if best is not None and (prior_best is None or best < prior_best):
                current["best_track_finish"] = format_number(best)

    results = []
    season_count = len(season_groups)
    for current in by_customer.values():
        finish_starts = current.pop("_finish_starts")
        finish_total = current.pop("_finish_total")
        current["avg_finish"] = (
            format_number(finish_total / finish_starts) if finish_starts else ""
        )
        current.update(
            {
                "points_position": "",
                "points_to_next": "",
                "track_starts": "",
                "track_wins": "",
                "notes": f"Velocity selected-series career across {season_count} season{'s' if season_count != 1 else ''}",
            }
        )
        results.append(current)
    return results


def parse_structured_directory(document, series_key=""):
    rows = []
    by_customer = {}
    series_key = str(series_key or "").strip().casefold()
    for record in extract_embedded_records(document):
        cust_id = str(record.get("cust_id") or "").strip()
        if not cust_id or not clean_driver_name(record.get("name")):
            continue
        record_series = str(record.get("series_key") or "").strip().casefold()
        if series_key and record_series and record_series != series_key:
            continue
        existing = by_customer.get(cust_id)
        if existing and existing.get("car_number"):
            continue
        by_customer[cust_id] = {
            "_cust_id": cust_id,
            "name": clean_driver_name(record.get("name")),
            "car_number": normalize_number(record.get("last_car_number")),
            "hometown": "",
            "state": "",
            "country": str(record.get("country_code") or "").strip(),
            "driving_style": "",
            "sponsor": "",
            "about": directory_about(record),
            "car_image": "",
        }
    rows.extend(by_customer.values())
    return rows


def directory_about(record):
    first_raced = str(record.get("first_raced") or "").strip()
    starts = str(record.get("starts") or "").strip()
    parts = []
    if starts:
        parts.append(f"Velocity directory lists {starts} league start{'s' if starts != '1' else ''}")
    if first_raced:
        parts.append(f"first raced {first_raced[:10]}")
    return "; ".join(parts)


def safe_float(value):
    try:
        return float(value)
    except (TypeError, ValueError):
        return None


def format_number(value):
    if value is None:
        return ""
    return str(int(value)) if float(value).is_integer() else f"{float(value):g}"


def average_finish(entries):
    finishes = [safe_float(entry.get("finish_pos")) for entry in entries]
    finishes = [value for value in finishes if value is not None and value > 0]
    return format_number(sum(finishes) / len(finishes)) if finishes else ""


def best_finish(entries):
    finishes = [safe_float(entry.get("finish_pos")) for entry in entries]
    finishes = [value for value in finishes if value is not None and value > 0]
    return format_number(min(finishes)) if finishes else ""


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


def resolve_series_key(input_url, series_filter, document):
    parsed = urlparse(str(input_url or ""))
    query_key = (parse_qs(parsed.query).get("series") or [""])[0].strip()
    if query_key:
        return query_key
    reserved = {"standings", "drivers", "directory", "schedule", "recap"}
    path_parts = [part for part in parsed.path.split("/") if part]
    if parsed.netloc.endswith("velocityleague.gg") and len(path_parts) >= 2:
        candidate = path_parts[-1].strip()
        if candidate.casefold() not in reserved:
            return candidate

    decoded = html.unescape(str(document or "")).replace(r'\"', '"')
    pairs = []
    for pattern in (
        r'"series_key":"([^"]+)"[^{}]{0,500}"series_name":"([^"]+)"',
        r'"seriesKey":"([^"]+)"[^{}]{0,500}"seriesName":"([^"]+)"',
    ):
        pairs.extend(re.findall(pattern, decoded, flags=re.I))
    wanted = str(series_filter or "").strip().casefold()
    for key, name in pairs:
        if wanted and wanted in {key.casefold(), name.casefold()}:
            return key
    if wanted:
        token = schedule_token(wanted)
        for key, name in pairs:
            if token in {schedule_token(key), schedule_token(name)}:
                return key
        return token
    return pairs[0][0] if pairs else ""


def build_standings_query(series_key, input_url=""):
    """Target the active series standings unless the user chose a season.

    Velocity's unqualified series URL resolves the current standings.  Forcing
    ``season=s1`` can select an older or different season and was the reason the
    Wednesday graphic showed the wrong order.
    """
    query = {"series": str(series_key or "").strip()}
    supplied_season = (parse_qs(urlparse(str(input_url or "")).query).get("season") or [""])[0].strip()
    if supplied_season:
        query["season"] = supplied_season
    return urlencode({key: value for key, value in query.items() if value})


def merge_driver_sources(directory_rows, standings_rows, career_rows):
    """Use career names first, then season records, while retaining signed drivers."""
    by_customer = {}
    for source in (directory_rows, standings_rows, career_rows):
        for row in source:
            cust_id = str(row.get("_cust_id") or "").strip()
            if not cust_id:
                continue
            current = by_customer.setdefault(
                cust_id,
                {field: "" for field in DRIVER_FIELDS} | {"_cust_id": cust_id},
            )
            if row.get("name"):
                current["name"] = row["name"]
            if row.get("car_number"):
                current["car_number"] = row["car_number"]
            for field in DRIVER_FIELDS[2:]:
                if row.get(field) and not current.get(field):
                    current[field] = row[field]
    return [
        {field: row.get(field, "") for field in DRIVER_FIELDS}
        for row in by_customer.values()
        if looks_like_driver_name(row.get("name"))
    ]


def looks_like_driver_name(value):
    text = clean_driver_name(value)
    if not text or not re.search(r"[A-Za-z]", text):
        return False
    return not any(
        token in text.casefold()
        for token in (
            "avg finish",
            "inc/race",
            "drivers",
            "starts",
            "top 5",
            "top 10",
            "points",
        )
    )


def apply_canonical_driver_names(stats_rows, career_rows):
    canonical = {
        str(row.get("_cust_id") or ""): row
        for row in career_rows
        if row.get("_cust_id")
    }
    for row in stats_rows:
        match = canonical.get(str(row.get("_cust_id") or ""))
        if not match:
            continue
        row["name"] = match.get("name") or row.get("name", "")
        row["car_number"] = match.get("car_number") or row.get("car_number", "")
    return stats_rows


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


def preserve_existing_driver_details(path, incoming_rows):
    path = Path(path)
    if not path.exists():
        return incoming_rows
    try:
        with path.open("r", newline="", encoding="utf-8-sig") as csv_file:
            existing_rows = list(csv.DictReader(csv_file))
    except (OSError, csv.Error):
        return incoming_rows
    by_name = {
        clean_driver_name(row.get("name")).casefold(): row
        for row in existing_rows
        if looks_like_driver_name(row.get("name"))
    }
    number_counts = {}
    for row in existing_rows:
        number = normalize_number(row.get("car_number"))
        if number:
            number_counts[number] = number_counts.get(number, 0) + 1
    by_number = {
        normalize_number(row.get("car_number")): row
        for row in existing_rows
        if normalize_number(row.get("car_number"))
        and number_counts.get(normalize_number(row.get("car_number"))) == 1
        and looks_like_driver_name(row.get("name"))
    }
    for incoming in incoming_rows:
        existing = by_name.get(clean_driver_name(incoming.get("name")).casefold())
        if not existing:
            existing = by_number.get(normalize_number(incoming.get("car_number")))
        if not existing:
            continue
        for field in DRIVER_FIELDS[2:]:
            if not incoming.get(field) and existing.get(field):
                incoming[field] = existing[field]
    return incoming_rows


def run_import(args):
    home_url, home_html = fetch_first_html(url_variants(args.url))
    home_text = html_to_text(home_html)
    parsed_home = urlparse(home_url)
    league_root = urlunparse((parsed_home.scheme, parsed_home.netloc, "", "", "", "")).rstrip("/")
    series_key = resolve_series_key(args.url, args.series, home_html)
    series_query = urlencode({"series": series_key}) if series_key else ""
    standings_query = build_standings_query(series_key, args.url) if series_key else ""

    schedule_candidates = []
    if series_key:
        schedule_candidates.append(f"{league_root}/schedule?{series_query}")
        schedule_candidates.append(f"{league_root}/{series_key}")
    schedule_candidates.extend(page_candidates(home_url, "schedule", home_html))
    standings_candidates = [f"{league_root}/standings?{standings_query}"] if standings_query else []
    standings_candidates.extend(page_candidates(home_url, "standings", home_html))
    drivers_candidates = [f"{league_root}/drivers?{series_query}"] if series_query else []
    drivers_candidates.extend(page_candidates(home_url, "drivers", home_html))
    directory_candidates = [f"{league_root}/directory"]
    directory_candidates.extend(page_candidates(home_url, "directory", home_html))

    schedule_url, schedule_html = fetch_first_html(unique(schedule_candidates))
    standings_url, standings_html = fetch_first_html(unique(standings_candidates))
    drivers_url, drivers_html = fetch_first_html(unique(drivers_candidates))
    directory_url, directory_html = fetch_first_html(unique(directory_candidates))

    standings_rows = parse_structured_standings(standings_html)
    if not standings_rows:
        standings_rows = parse_standings_rows(
            "\n".join([home_text, html_to_text(standings_html)]),
            args.series,
        )
    canonical_rows = parse_structured_career(drivers_html)
    if not canonical_rows:
        canonical_rows = parse_driver_profile_rows(html_to_text(drivers_html))
    directory_rows = parse_structured_directory(directory_html, series_key)
    standings_rows = apply_canonical_driver_names(standings_rows, canonical_rows)
    schedule_rows = parse_schedule_rows(html_to_text(schedule_html) or home_text)
    recap_urls = extract_recap_urls(schedule_html, league_root, series_key)
    for row, recap_url in zip(schedule_rows, recap_urls):
        row["results_url"] = recap_url
    season_rows = dedupe_stats(standings_rows)
    season_keys = extract_series_season_keys(standings_html)
    historical_seasons = []
    for season_key in season_keys:
        history_query = urlencode({"series": series_key, "season": season_key})
        _history_url, history_html = fetch_first_html(
            [f"{league_root}/standings?{history_query}"]
        )
        history_rows = parse_structured_standings(history_html)
        apply_canonical_driver_names(history_rows, canonical_rows)
        if history_rows:
            historical_seasons.append(dedupe_stats(history_rows))
    if not historical_seasons:
        historical_seasons = [season_rows]
    career_stats_rows = dedupe_stats(aggregate_series_career(historical_seasons))
    driver_rows = merge_driver_sources(directory_rows, standings_rows, canonical_rows)

    if args.dry_run:
        print(f"Velocity League URL: {home_url}")
        print(f"Series key: {series_key or 'not detected'}")
        print(f"Schedule page: {schedule_url or 'not found'}")
        print(f"Standings page: {standings_url or 'not found'}")
        print(f"Drivers page: {drivers_url or 'not found'}")
        print(f"Directory page: {directory_url or 'not found'}")
        print(f"Parsed season rows: {len(season_rows)}")
        print(f"Parsed career rows: {len(career_stats_rows)}")
        print(f"Parsed driver rows: {len(driver_rows)}")
        print(f"Parsed schedule rows: {len(schedule_rows)}")
        for row in season_rows[:10]:
            print(f"STAT {row.get('points_position') or '--'} #{row.get('car_number') or '--'} {row.get('name')}")
        for row in career_stats_rows[:5]:
            print(f"CAREER {row.get('starts') or '0'} starts #{row.get('car_number') or '--'} {row.get('name')}")
        for row in schedule_rows[:10]:
            print(f"SCHEDULE {row.get('schedule_id')} {row.get('track_name')} {row.get('notes')}")
        return 0

    if args.stats_output:
        write_csv(args.stats_output, STATS_FIELDS, season_rows)
    if args.career_output:
        write_csv(args.career_output, STATS_FIELDS, career_stats_rows)
    if args.drivers_output:
        driver_rows = preserve_existing_driver_details(args.drivers_output, driver_rows)
        write_csv(args.drivers_output, DRIVER_FIELDS, driver_rows)
    if args.schedule_output:
        write_csv(args.schedule_output, SCHEDULE_FIELDS, schedule_rows)
    print(f"Imported {len(season_rows)} Velocity season row(s) to {args.stats_output}.")
    print(f"Imported {len(career_stats_rows)} Velocity career row(s) to {args.career_output}.")
    print(f"Imported {len(driver_rows)} Velocity driver row(s) to {args.drivers_output}.")
    print(f"Imported {len(schedule_rows)} Velocity schedule row(s) to {args.schedule_output}.")
    return 0


def build_parser():
    parser = argparse.ArgumentParser(description="Import public Velocity League data for RGC AI Broadcast Studio.")
    parser.add_argument("url", help="Velocity league home URL, for example https://www.velocityleague.gg/trrl")
    parser.add_argument("--series", default="", help="Optional series name filter, for example Truck Series")
    parser.add_argument("--stats-output", default="league/season.csv")
    parser.add_argument("--career-output", default="league/career.csv")
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
