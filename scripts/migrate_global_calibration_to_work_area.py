#!/usr/bin/env python3
"""Copy the current global calibration into a named work-area profile.

This utility is intentionally independent of the platform runtime and uses only
the Python standard library. The original global calibration is never modified.
"""

from __future__ import annotations

import argparse
import json
import os
from pathlib import Path
import shutil
import tempfile


ARTIFACT_SUFFIXES = (
    ".npy",
    "_homography_residual.json",
    "_geometry_scale.json",
    "_model_report.json",
)


def _artifact_path(matrix_path: Path, suffix: str) -> Path:
    if suffix == ".npy":
        return matrix_path
    return matrix_path.with_name(f"{matrix_path.stem}{suffix}")


def _atomic_copy(source: Path, destination: Path) -> None:
    destination.parent.mkdir(parents=True, exist_ok=True)
    with tempfile.NamedTemporaryFile(dir=destination.parent, delete=False) as handle:
        temporary = Path(handle.name)
    try:
        shutil.copy2(source, temporary)
        os.replace(temporary, destination)
    finally:
        if temporary.exists():
            temporary.unlink()


def _atomic_write_json(path: Path, payload: dict) -> None:
    with tempfile.NamedTemporaryFile(
        mode="w", encoding="utf-8", dir=path.parent, delete=False
    ) as handle:
        json.dump(payload, handle, indent=2)
        handle.write("\n")
        temporary = Path(handle.name)
    os.replace(temporary, path)


def migrate(args: argparse.Namespace) -> None:
    area = str(args.area or "").strip()
    profile_id = str(args.profile or "").strip()
    reference_frame = str(args.reference_frame or "").strip().lower()
    if not area or not profile_id or not reference_frame:
        raise SystemExit("Area, profile, and reference frame must all be non-empty")
    if profile_id == "global":
        raise SystemExit("Profile id 'global' is reserved for the existing global calibration")
    settings_path = args.settings.resolve()
    if not settings_path.is_file():
        raise SystemExit(f"Calibration settings file does not exist: {settings_path}")
    data_dir = settings_path.parent / "data"
    source_matrix = (args.source or data_dir / "cameraToRobotMatrix_camera_center.npy").resolve()
    destination_matrix = (
        args.destination or data_dir / "calibrations" / area / "camera_to_robot.npy"
    ).resolve()
    if source_matrix == destination_matrix:
        raise SystemExit("Source and destination calibration matrix paths must be different")

    required_sources = [
        _artifact_path(source_matrix, ".npy"),
        _artifact_path(source_matrix, "_homography_residual.json"),
    ]
    missing = [str(path) for path in required_sources if not path.is_file()]
    if missing:
        raise SystemExit(f"Required global calibration artifacts are missing: {missing}")

    destinations = []
    for suffix in ARTIFACT_SUFFIXES:
        source = _artifact_path(source_matrix, suffix)
        if not source.is_file():
            continue
        destination = _artifact_path(destination_matrix, suffix)
        if destination.exists() and not args.overwrite:
            raise SystemExit(f"Destination already exists: {destination} (use --overwrite)")
        destinations.append((source, destination))

    try:
        settings = json.loads(settings_path.read_text(encoding="utf-8"))
    except (OSError, ValueError) as exc:
        raise SystemExit(f"Cannot read calibration settings: {exc}") from exc
    if not isinstance(settings, dict):
        raise SystemExit("Calibration settings root must be a JSON object")
    coordinate = settings.setdefault("Coordinate calibration", {})
    if not isinstance(coordinate, dict):
        raise SystemExit("'Coordinate calibration' must be a JSON object")
    profiles = coordinate.setdefault("Profiles", {})
    assignments = coordinate.setdefault("Work area profiles", {})
    if not isinstance(profiles, dict) or not isinstance(assignments, dict):
        raise SystemExit("Calibration profiles and work-area assignments must be JSON objects")
    if not args.overwrite and profile_id in profiles:
        raise SystemExit(f"Profile {profile_id!r} already exists (use --overwrite)")
    if not args.overwrite and area in assignments:
        raise SystemExit(f"Work area {area!r} already has an assignment (use --overwrite)")
    relative_matrix = os.path.relpath(destination_matrix, data_dir)
    profiles[profile_id] = {
        "Matrix path": relative_matrix,
        "Reference frame": reference_frame,
    }
    assignments[area] = profile_id
    coordinate.setdefault("Calibration target", "global")
    coordinate["Mode"] = "per_area" if args.enable_per_area else coordinate.get("Mode", "global")

    for source, destination in destinations:
        _atomic_copy(source, destination)
        print(f"Copied {source} -> {destination}")
    _atomic_write_json(settings_path, settings)
    print(f"Assigned work area {area!r} to profile {profile_id!r} in {settings_path}")
    if not args.enable_per_area:
        print("Per-area mode was not enabled; review the settings and enable it when ready.")


def main() -> None:
    repository = Path(__file__).resolve().parents[1]
    default_settings = repository / "src/robot_systems/paint/storage/settings/vision/calibration_settings.json"
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--settings", type=Path, default=default_settings)
    parser.add_argument("--source", type=Path)
    parser.add_argument("--destination", type=Path)
    parser.add_argument("--area", default="paint")
    parser.add_argument("--profile", default="paint_local")
    parser.add_argument("--reference-frame", default="calibration")
    parser.add_argument("--enable-per-area", action="store_true")
    parser.add_argument("--overwrite", action="store_true")
    migrate(parser.parse_args())


if __name__ == "__main__":
    main()
