from __future__ import annotations

import argparse
import shutil
import subprocess
import sys
from pathlib import Path

try:
    import tomllib
except ModuleNotFoundError:  # pragma: no cover - Python < 3.11 fallback
    import tomli as tomllib

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from tools.build_tester_zip import should_include, tracked_files


DIST_DIR = ROOT / "dist"
INSTALLER_SOURCE_DIR = DIST_DIR / "windows_installer_source"
INNO_SCRIPT = ROOT / "installer" / "RGC_AI_Broadcast_Studio.iss"


DEFAULT_INNO_PATHS = [
    Path("C:/Program Files (x86)/Inno Setup 7/ISCC.exe"),
    Path("C:/Program Files/Inno Setup 7/ISCC.exe"),
    Path("C:/Program Files (x86)/Inno Setup 6/ISCC.exe"),
    Path("C:/Program Files/Inno Setup 6/ISCC.exe"),
]


def project_version(root: Path = ROOT) -> str:
    pyproject = root / "pyproject.toml"
    with pyproject.open("rb") as file:
        data = tomllib.load(file)
    return str(data.get("project", {}).get("version", "0.0.0"))


def clean_directory(path: Path) -> None:
    if path.exists():
        shutil.rmtree(path)
    path.mkdir(parents=True, exist_ok=True)


def prepare_installer_source(
    *,
    root: Path = ROOT,
    source_dir: Path = INSTALLER_SOURCE_DIR,
) -> Path:
    clean_directory(source_dir)
    for relative in tracked_files(root):
        if not should_include(relative):
            continue
        source = root / relative
        target = source_dir / relative
        target.parent.mkdir(parents=True, exist_ok=True)
        shutil.copy2(source, target)
    return source_dir


def find_inno_compiler(explicit_path: str | None = None) -> Path | None:
    if explicit_path:
        path = Path(explicit_path)
        return path if path.exists() else None

    from_path = shutil.which("ISCC.exe") or shutil.which("iscc")
    if from_path:
        return Path(from_path)

    for path in DEFAULT_INNO_PATHS:
        if path.exists():
            return path
    return None


def build_inno_command(
    compiler: Path,
    *,
    source_dir: Path,
    output_dir: Path,
    version: str,
    script: Path = INNO_SCRIPT,
) -> list[str]:
    return [
        str(compiler),
        f"/DSourceDir={source_dir}",
        f"/DOutputDir={output_dir}",
        f"/DAppVersion={version}",
        str(script),
    ]


def build_windows_setup(
    *,
    inno_path: str | None = None,
    require_inno: bool = False,
    root: Path = ROOT,
) -> Path | None:
    version = project_version(root)
    source_dir = prepare_installer_source(root=root)
    compiler = find_inno_compiler(inno_path)

    print(f"Prepared installer source: {source_dir}")
    print(f"App version: {version}")

    if compiler is None:
        print("")
        print("Inno Setup compiler was not found, so Setup.exe was not built yet.")
        print("Install Inno Setup from https://jrsoftware.org/isinfo.php")
        print("The script checks common Inno Setup 7 and 6 install folders.")
        print("Then rerun:")
        print(r"  .\.venv\Scripts\python.exe tools\build_windows_setup.py")
        if require_inno:
            raise FileNotFoundError("Inno Setup compiler was not found.")
        return None

    DIST_DIR.mkdir(parents=True, exist_ok=True)
    command = build_inno_command(
        compiler,
        source_dir=source_dir,
        output_dir=DIST_DIR,
        version=version,
    )
    subprocess.run(command, cwd=root, check=True)

    setup_path = DIST_DIR / f"RGC-AI-Broadcast-Studio-Setup-{version}.exe"
    print(f"Created Windows installer: {setup_path}")
    return setup_path


def main() -> None:
    parser = argparse.ArgumentParser(
        description="Prepare and optionally build the RGC AI Broadcast Studio Windows installer."
    )
    parser.add_argument(
        "--inno-path",
        help="Optional path to ISCC.exe if Inno Setup is not on PATH.",
    )
    parser.add_argument(
        "--require-inno",
        action="store_true",
        help="Fail if Inno Setup is not installed instead of only preparing installer source.",
    )
    args = parser.parse_args()

    try:
        build_windows_setup(inno_path=args.inno_path, require_inno=args.require_inno)
    except Exception as error:
        print(f"Installer build failed: {error}", file=sys.stderr)
        raise


if __name__ == "__main__":
    main()
