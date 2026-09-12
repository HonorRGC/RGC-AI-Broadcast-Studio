from __future__ import annotations

import argparse
import subprocess
import zipfile
from datetime import datetime
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
DEFAULT_DIST_DIR = ROOT / "dist"

PRIVATE_OR_LOCAL_PARTS = {
    ".env",
    ".pytest_cache",
    ".ruff_cache",
    ".runtime",
    ".venv",
    "__pycache__",
    "build",
    "dist",
    "league",
    "profiles",
    "recordings",
}

PRIVATE_SUFFIXES = {
    ".log",
    ".mp3",
    ".pyc",
    ".pyo",
    ".wav",
}


def should_include(path: str) -> bool:
    parts = Path(path).parts
    if any(part in PRIVATE_OR_LOCAL_PARTS for part in parts):
        return False
    if Path(path).suffix.lower() in PRIVATE_SUFFIXES:
        return False
    return True


def tracked_files(root: Path = ROOT) -> list[str]:
    result = subprocess.run(
        ["git", "ls-files"],
        cwd=root,
        text=True,
        capture_output=True,
        check=True,
    )
    return [line.strip() for line in result.stdout.splitlines() if line.strip()]


def build_tester_zip(
    *,
    root: Path = ROOT,
    dist_dir: Path = DEFAULT_DIST_DIR,
    name: str | None = None,
) -> Path:
    version_stamp = datetime.now().strftime("%Y%m%d-%H%M")
    zip_name = name or f"RGC-AI-Broadcast-Studio-Tester-{version_stamp}.zip"
    if not zip_name.lower().endswith(".zip"):
        zip_name += ".zip"

    dist_dir.mkdir(parents=True, exist_ok=True)
    zip_path = dist_dir / zip_name

    files = [path for path in tracked_files(root) if should_include(path)]
    with zipfile.ZipFile(zip_path, "w", compression=zipfile.ZIP_DEFLATED) as archive:
        for path in files:
            archive.write(root / path, path)

    return zip_path


def main() -> None:
    parser = argparse.ArgumentParser(
        description="Build a clean RGC AI Broadcast Studio tester ZIP."
    )
    parser.add_argument(
        "--name",
        help="Optional ZIP filename. Defaults to RGC-AI-Broadcast-Studio-Tester-YYYYMMDD-HHMM.zip.",
    )
    args = parser.parse_args()

    zip_path = build_tester_zip(name=args.name)
    print(f"Created tester ZIP: {zip_path}")
    print("Private files excluded: .env, league/, profiles/, recordings/, .venv/, caches, logs, and local audio.")


if __name__ == "__main__":
    main()
