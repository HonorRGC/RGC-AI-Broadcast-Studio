from __future__ import annotations

import argparse
import json
from pathlib import Path
from urllib.error import URLError
from urllib.parse import urljoin
from urllib.request import urlopen

from production.sim_racing_apps import (
    DEFAULT_BASE_URL,
    CAR_FIELDS,
    build_sim_racing_apps_car_debug_info,
    build_sim_racing_apps_car_render_info,
    ensure_base_url,
    fetch_sim_racing_apps_data,
    sim_racing_apps_session_car_count,
)


DEFAULT_CANDIDATES = (
    DEFAULT_BASE_URL,
    "http://localhost/SIMRacingApps/",
    "http://127.0.0.1:80/SIMRacingApps/",
    "http://localhost:80/SIMRacingApps/",
)


def main() -> None:
    parser = argparse.ArgumentParser(
        description=(
            "Probe the local Sim Racing Apps server for live iRacing car render, "
            "number, and driver matching data."
        )
    )
    parser.add_argument(
        "--base-url",
        default="",
        help="Sim Racing Apps base URL. Example: http://127.0.0.1/SIMRacingApps/",
    )
    parser.add_argument(
        "--cars",
        type=int,
        default=10,
        help="How many live cars to print from the SRA session roster.",
    )
    parser.add_argument(
        "--extract-images",
        action="store_true",
        help="Download sample car render images so you can visually verify them.",
    )
    parser.add_argument(
        "--output-dir",
        default="outputs/sim_racing_apps_probe",
        help="Where downloaded image samples should be saved.",
    )
    args = parser.parse_args()

    base_url = choose_base_url(args.base_url)
    print("=" * 80)
    print("RGC AI Broadcast Studio - Sim Racing Apps Probe")
    print("=" * 80)
    print("This checks the same local web source Sim Racing Apps overlays use.")
    print("Make sure Sim Racing Apps Server is running and iRacing is in a session.")
    print("=" * 80)
    print(f"Selected base URL: {base_url or 'NONE'}")

    if not base_url:
        print("No Sim Racing Apps server answered. Start SRA and try again.")
        return

    count = sim_racing_apps_session_car_count(base_url=base_url)
    print(f"Session cars reported by SRA: {count}")
    print("-" * 80)

    summaries = []
    for car_idx in range(max(0, min(args.cars, count))):
        probe_driver = {"car_idx": car_idx}
        debug_info = build_sim_racing_apps_car_debug_info(probe_driver, base_url=base_url)
        direct = debug_info.get("direct", {})
        render_info = build_sim_racing_apps_car_render_info(probe_driver, base_url=base_url)
        summaries.append(
            {
                "car_idx": car_idx,
                "name": direct.get("name", ""),
                "number": direct.get("number", ""),
                "image_url": render_info.get("image_url", ""),
                "number_style": render_info.get("number_style", {}),
            }
        )

    print(json.dumps({"base_url": base_url, "cars": summaries}, indent=2))

    if args.extract_images:
        output_dir = Path(args.output_dir)
        output_dir.mkdir(parents=True, exist_ok=True)
        saved = []
        for item in summaries:
            image_url = item.get("image_url", "")
            if not image_url:
                continue
            saved_path = download_image_sample(image_url, output_dir, item)
            if saved_path:
                saved.append(str(saved_path))
        print("-" * 80)
        if saved:
            print("Saved image samples:")
            for path in saved:
                print(f"  {path}")
        else:
            print("No image samples were available to save.")

    print("-" * 80)
    print("Fields checked per car:")
    for field_name in CAR_FIELDS:
        print(f"  Data/Car/I#/ {field_name}".replace("#/ ", "#/"))


def choose_base_url(requested: str) -> str:
    candidates = []
    if requested:
        candidates.append(requested)
    for candidate in DEFAULT_CANDIDATES:
        if candidate and candidate not in candidates:
            candidates.append(candidate)

    for candidate in candidates:
        base_url = ensure_base_url(candidate)
        data = fetch_sim_racing_apps_data("Data/Session/Cars", base_url=base_url)
        if data.get("State") == "NORMAL":
            return base_url
    return ""


def download_image_sample(image_url: str, output_dir: Path, item: dict) -> Path | None:
    try:
        with urlopen(image_url, timeout=2.0) as response:
            raw = response.read(2_500_000)
            content_type = response.headers.get("Content-Type", "")
    except (OSError, TimeoutError, URLError):
        return None

    if not raw:
        return None

    suffix = ".png"
    if "jpeg" in content_type or "jpg" in content_type:
        suffix = ".jpg"
    elif "webp" in content_type:
        suffix = ".webp"

    number = safe_filename(item.get("number") or str(item.get("car_idx", "car")))
    name = safe_filename(item.get("name") or "driver")
    path = output_dir / f"I{item.get('car_idx')}_{number}_{name}{suffix}"
    path.write_bytes(raw)
    return path


def safe_filename(value: object) -> str:
    text = "".join(ch if ch.isalnum() or ch in ("-", "_") else "_" for ch in str(value))
    return text.strip("_")[:60] or "item"


if __name__ == "__main__":
    main()
