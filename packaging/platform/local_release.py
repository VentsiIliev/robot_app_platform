"""Install the latest local kit or run the selected installed robot platform."""
import argparse
import json
from pathlib import Path, PurePosixPath
import platform
import re
import subprocess
import sys
import tarfile
import tempfile

from targets import ROOT, load_target

sys.path.insert(0, str(ROOT))
from src.engine.updates.config import UpdateConfig, default_config_path, default_install_root
from src.engine.updates.releases import version_tuple


def latest_installer(releases: Path, target: dict) -> Path:
    """Select by semantic version, never by filename order or modification time."""
    folder = releases / target["target"]
    pattern = re.compile(re.escape(target["product"]) + r"-installer-(\d+\.\d+\.\d+)-" +
                         re.escape(platform.machine()) + r"\.tar\.gz$")
    candidates = []
    if folder.exists():
        for path in folder.iterdir():
            match = pattern.fullmatch(path.name)
            if path.is_file() and match:
                candidates.append((version_tuple(match.group(1)), path))
    if not candidates:
        raise ValueError(f"No installer for {target['target']} / {platform.machine()} in {folder}. "
                         f"Build a release with packaging/platform/build_release.py {target['target']} VERSION first.")
    return max(candidates, key=lambda candidate: candidate[0])[1]


def install(kit: Path, target: dict, config: Path | None, root: Path | None) -> int:
    print(f"Installing latest local release: {kit}", flush=True)
    prefix = f"{target['product']}-installer"
    with tempfile.TemporaryDirectory(prefix="robot-platform-installer-") as directory:
        with tarfile.open(kit, "r:gz") as archive:
            for member in archive:
                path = PurePosixPath(member.name)
                if path.is_absolute() or ".." in path.parts or "\\" in member.name or not path.parts or path.parts[0] != prefix:
                    raise ValueError("Unsafe installer archive path")
                if not (member.isdir() or member.isfile()):
                    raise ValueError("Installer links and special files are forbidden")
            archive.extractall(directory, filter="data")
        command = [str(Path(directory) / prefix / "install.sh")]
        if config:
            command += ["--config", str(config.expanduser().resolve())]
        if root:
            command += ["--root", str(root.expanduser().resolve())]
        return subprocess.run(command).returncode


def run(target: dict, config: Path | None, root: Path | None) -> int:
    selected_config = (config or default_config_path(target["product"])).expanduser().resolve()
    settings = UpdateConfig.load(selected_config) if selected_config.exists() else None
    if settings and settings.product != target["product"]:
        raise ValueError("Configuration belongs to another robot system/profile")
    installed_root = (root or (settings.install_root if settings else default_install_root(target["product"]))).expanduser().resolve()
    helper = installed_root / "tools/manage.py"
    marker = installed_root / "current/manifest.json"
    if not helper.is_file() or not marker.is_file():
        raise ValueError(f"{target['target']} is not installed at {installed_root}. Run install_latest.sh {target['target']} first.")
    if json.loads(marker.read_text())["product"] != target["product"]:
        raise ValueError("Installation belongs to another robot system/profile")
    command = ["/usr/bin/python3", str(helper)]
    if config:
        command += ["--config", str(config.expanduser().resolve())]
    command += ["launch"]
    print(f"Launching installed {target['target']} from {installed_root}", flush=True)
    return subprocess.run(command).returncode


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("action", choices=("install", "run"))
    parser.add_argument("target", nargs="?", help="Defaults to config/platform.json's selected system")
    parser.add_argument("--releases-dir", type=Path, default=ROOT / "dist/platform-releases")
    parser.add_argument("--config", type=Path)
    parser.add_argument("--root", type=Path)
    args = parser.parse_args()
    try:
        name = args.target or json.loads((ROOT / "config/platform.json").read_text())["robot_system"]
        target = load_target(name)
        if args.action == "install":
            return install(latest_installer(args.releases_dir.expanduser().resolve(), target), target, args.config, args.root)
        return run(target, args.config, args.root)
    except (OSError, ValueError, KeyError, tarfile.TarError) as error:
        print(f"Platform operation failed: {error}", file=sys.stderr)
        return 1


if __name__ == "__main__":
    sys.exit(main())
