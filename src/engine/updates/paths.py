"""Resolve mutable robot-system paths independently of installed software."""
import os
from pathlib import Path


def system_path(system_class, relative_path: str) -> str:
    """Resolve a system-relative writable path; preserve source-run defaults."""
    root = os.environ.get("ROBOT_PLATFORM_DATA_ROOT")
    if root:
        system = system_class.__module__.split(".")[2]
        relative = Path(relative_path)
        if relative.is_absolute() or ".." in relative.parts:
            raise ValueError("External storage requires a system-relative path")
        return str(Path(root).expanduser().resolve() / system / relative)
    return os.path.join(system_class.package_root(), relative_path)
