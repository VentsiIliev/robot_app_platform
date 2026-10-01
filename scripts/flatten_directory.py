"""List or copy every file in a directory tree into one flat directory."""

from collections import Counter
import os
from pathlib import Path
import shutil


START_DIRECTORY = Path("/home/ilv/Desktop/robot_app_platform")
DESTINATION_DIRECTORY = Path("/home/ilv/Desktop/test")
COPY_FILES = False  # First pass: print the files without copying anything.
EXCLUDED_DIRECTORY_NAMES = {".git", ".venv", "__pycache__"}


def _flat_name(path: Path, start: Path, used_names: set[str]) -> str:
    relative = path.relative_to(start)
    candidate = "__".join((start.name, *relative.parts))

    base = Path(candidate)
    number = 2
    while candidate in used_names:
        candidate = f"{base.stem}__{number}{base.suffix}"
        number += 1
    used_names.add(candidate)
    return candidate


def flatten_files(start: Path, destination: Path, copy_files: bool = False) -> None:
    start = start.expanduser().resolve()
    destination = destination.expanduser().resolve()

    if not start.is_dir():
        raise ValueError(f"Start directory does not exist: {start}")
    if destination.exists() and not destination.is_dir():
        raise ValueError(f"Destination is not a directory: {destination}")
    if destination == start or start in destination.parents:
        raise ValueError("Destination directory must be outside the start directory")

    files = []
    for current_root, dirs, names in os.walk(start):
        dirs[:] = sorted(name for name in dirs if name not in EXCLUDED_DIRECTORY_NAMES)
        files.extend(
            Path(current_root) / name
            for name in names
            if (Path(current_root) / name).is_file()
        )
    files.sort()
    name_counts = Counter(path.name for path in files)
    used_names = {path.name for path in destination.iterdir()} if destination.is_dir() else set()
    used_names.update(path.name for path in files if name_counts[path.name] == 1)
    destinations = []

    for path in files:
        if name_counts[path.name] == 1 and not (destination / path.name).exists():
            target_name = path.name
        else:
            target_name = _flat_name(path, start, used_names)
        target = destination / target_name
        destinations.append((path, target))
        print(f"[{'COPY' if copy_files else 'PREVIEW'}] {path} -> {target}")

    print(f"Found {len(files)} file(s).")

    if copy_files:
        destination.mkdir(parents=True, exist_ok=True)
        for path, target in destinations:
            shutil.copy2(path, target)
        print(f"Copied {len(files)} file(s).")
    else:
        print("Preview only; no files were copied.")


if __name__ == "__main__":
    flatten_files(START_DIRECTORY, DESTINATION_DIRECTORY, COPY_FILES)
