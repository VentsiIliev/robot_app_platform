"""Seed authored factory settings without replacing machine-owned files."""
import json
import os
from pathlib import Path
import uuid

from .files import atomic_json, sync_directory

ALLOWED_FILES = frozenset({
    "hardware/peripherals.json", "hardware/modbus.json",
    "hardware/cameras.json", "dryer/settings.json",
})


def load_factory_defaults(resource_root: Path, identity: dict) -> dict:
    """Validate the selected product's templates; legacy bundles have none."""
    source = resource_root / "config/factory-defaults.json"
    if not source.exists():
        return {}
    document = json.loads(source.read_text(encoding="utf-8"))
    if document.get("format") != 1 or any(
        document.get(key) != identity.get(key)
        for key in ("product", "robot_system", "profile")
    ):
        raise ValueError("Factory defaults belong to another robot system/profile")
    files = document.get("files")
    if not isinstance(files, dict) or not files.keys() <= ALLOWED_FILES:
        raise ValueError("Unsupported factory settings file")
    if any(not isinstance(value, dict) for value in files.values()):
        raise ValueError("Factory settings must be JSON objects")
    return files


def seed_factory_defaults(resource_root: Path, data_root: Path, identity: dict) -> list[str]:
    """Atomically create missing settings files, including on subsequent releases."""
    files = load_factory_defaults(resource_root, identity)
    settings = data_root / identity["storage_system"]
    if identity["profile"] != "default":
        settings = settings / "profiles" / identity["profile"]
    settings = settings / "storage/settings"
    created = []
    for relative, value in files.items():
        destination = settings / relative
        parent = destination
        while parent != data_root.parent:
            if parent.is_symlink():
                raise ValueError("Factory settings cannot traverse data symlinks")
            parent = parent.parent
        if destination.exists():
            continue
        destination.parent.mkdir(parents=True, exist_ok=True)
        temporary = destination.with_name(".factory-" + uuid.uuid4().hex)
        try:
            atomic_json(temporary, value)
            try:
                # A competing writer creating the file always wins.
                os.link(temporary, destination)
            except FileExistsError:
                continue
            sync_directory(destination.parent)
            created.append(relative)
        finally:
            temporary.unlink(missing_ok=True)
    return created
