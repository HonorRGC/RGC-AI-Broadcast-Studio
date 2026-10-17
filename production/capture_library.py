"""Manage a stopped broadcast's capture bundle without touching other races."""
import json
from pathlib import Path
from production.capture_images import asset_files, image_directory


def capture_bundles(recordings_dir, process_id, started_after=0):
    if not process_id:
        return []
    root = Path(recordings_dir).resolve()
    bundles = []
    for metadata in sorted(root.glob("*.capture.json")):
        try:
            payload = json.loads(metadata.read_text(encoding="utf-8"))
            if payload.get("process_id") != process_id or float(payload.get("started_at", 0)) < started_after:
                continue
            stem = metadata.name.removesuffix(".capture.json")
            paths = (root / (stem + ".jsonl"), root / (stem + ".events.jsonl"), metadata)
            if any(path.resolve().parent != root for path in paths):
                continue
            bundles.append({"metadata": payload, "paths": paths,
                            "size_bytes": sum(path.stat().st_size for path in (*paths, *asset_files(paths[0])) if path.is_file())})
        except (OSError, ValueError, TypeError):
            continue
    return bundles


def set_capture_retention(bundle, keep, recordings_dir):
    root = Path(recordings_dir).resolve()
    paths = tuple(Path(path) for path in bundle["paths"])
    # Resolve and validate the whole bundle before any mutation. Metadata cannot
    # nominate arbitrary filenames, and symlinks outside recordings are rejected.
    if len(paths) != 3 or any(path.resolve().parent != root for path in paths):
        raise ValueError("Capture bundle must stay inside the recordings folder")
    telemetry, events, metadata = paths
    if events != telemetry.with_suffix(".events.jsonl") or metadata != telemetry.with_suffix(".capture.json"):
        raise ValueError("Capture filenames do not belong to the same recording")
    images = asset_files(telemetry)
    if keep:
        payload = json.loads(metadata.read_text(encoding="utf-8"))
        payload["retention"] = "kept"
        temporary = metadata.with_suffix(".tmp")
        temporary.write_text(json.dumps(payload, indent=2), encoding="utf-8")
        temporary.replace(metadata)
    else:
        for image in images:
            image.unlink()
        folder = image_directory(telemetry)
        if folder.exists():
            folder.rmdir()
        for path in paths:
            path.unlink(missing_ok=True)
