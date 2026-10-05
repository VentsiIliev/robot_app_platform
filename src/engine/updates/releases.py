"""Release format validation and extraction; archives never contain live data."""
import json
import platform
import re
import shutil
import tarfile
from pathlib import Path, PurePosixPath


VERSION = re.compile(r"^(0|[1-9][0-9]*)\.(0|[1-9][0-9]*)\.(0|[1-9][0-9]*)$")


def version_tuple(value: str) -> tuple[int, int, int]:
    if not isinstance(value, str) or not VERSION.fullmatch(value):
        raise ValueError("Release version must be major.minor.patch")
    return tuple(map(int, value.split(".")))


def validate_manifest(raw: dict, product: str) -> dict:
    if not isinstance(raw, dict) or raw.get("format") not in (1, 2) or raw.get("product") != product:
        raise ValueError("Wrong release format or product")
    if raw["format"] == 1 and product != "paint-robot":
        raise ValueError("Legacy releases support the default paint product only")
    if raw["format"] == 2:
        for name in ("robot_system", "profile", "storage_system", "executable"):
            value = raw.get(name)
            if not isinstance(value, str) or not re.fullmatch(r"[a-z][a-z0-9_-]*", value):
                raise ValueError(f"Invalid release {name}")
    version_tuple(raw.get("version"))
    if raw.get("architecture") != platform.machine():
        raise ValueError("Release CPU architecture does not match")
    if raw.get("os") != "ubuntu-24.04":
        raise ValueError("Only Ubuntu 24.04 releases are supported")
    os_info = platform.freedesktop_os_release()
    if os_info.get("ID") != "ubuntu" or os_info.get("VERSION_ID") != "24.04":
        raise ValueError("This release requires Ubuntu 24.04")
    schema = raw.get("storage_schema")
    if not isinstance(schema, int) or isinstance(schema, bool) or schema < 1:
        raise ValueError("storage_schema must be a positive integer")
    return raw


def extract_release(archive: Path, destination: Path, max_bytes: int) -> None:
    """Extract only regular files/directories within the release root."""
    destination.mkdir(parents=True, exist_ok=False)
    try:
        with tarfile.open(archive, "r:gz") as bundle:
            total = 0
            seen = set()
            for member in bundle:
                path = PurePosixPath(member.name)
                if path.is_absolute() or ".." in path.parts or not path.parts or "\\" in member.name:
                    raise ValueError("Unsafe release archive path")
                if path.parts[0] not in {"platform", "manifest.json", "migrations"}:
                    raise ValueError("Unexpected release archive content")
                if not (member.isfile() or member.isdir()) or member.name in seen:
                    raise ValueError("Release links, special files and duplicate entries are forbidden")
                if any(part in {"storage", "profiles"} for part in path.parts) and "translations" not in path.parts:
                    # Parent resource directories are allowed; mutable files are not.
                    if member.isfile():
                        raise ValueError("Release contains mutable storage")
                seen.add(member.name)
                total += member.size
                if total > max_bytes or len(seen) > 100000:
                    raise ValueError("Release extraction limit exceeded")
                target = destination.joinpath(*path.parts)
                if member.isdir():
                    target.mkdir(parents=True, exist_ok=True)
                else:
                    target.parent.mkdir(parents=True, exist_ok=True)
                    with bundle.extractfile(member) as source, target.open("xb") as output:
                        shutil.copyfileobj(source, output)
                    target.chmod(0o755 if member.mode & 0o111 else 0o644)
        manifest = json.loads((destination / "manifest.json").read_text())
        executable = destination / "platform" / release_executable(manifest)
        if not executable.is_file() or not executable.stat().st_mode & 0o111:
            raise ValueError("Release executable missing or not executable")
    except BaseException:
        shutil.rmtree(destination)
        raise


def release_executable(manifest: dict) -> str:
    value = manifest.get("executable", "paint-robot" if manifest.get("format") == 1 else "")
    if not isinstance(value, str) or not re.fullmatch(r"[a-z][a-z0-9_-]*", value):
        raise ValueError("Invalid release executable")
    return value


def release_identity(manifest: dict) -> tuple[str, str, str]:
    if manifest.get("format") == 1:
        return manifest["product"], "paint", "default"
    return manifest["product"], manifest["robot_system"], manifest["profile"]
