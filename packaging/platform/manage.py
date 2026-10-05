#!/usr/bin/env python3
"""Independent installer/updater/launcher. Uses Ubuntu's system Python, not Qt."""
import argparse
import json
import os
import pwd
from pathlib import Path
import shutil
import subprocess
import sys
import tarfile
import uuid

# Source checkout: parents[2]. Installed tools: this script's directory.
HERE = Path(__file__).resolve().parent
sys.path.insert(0, str(HERE if (HERE / "src").is_dir() else HERE.parents[1]))
from src.engine.updates.config import UpdateConfig, default_config_path, default_install_root
from src.engine.updates.files import atomic_json, lock, sync_tree, sync_directory
from src.engine.updates.updater import PlatformUpdater
from src.engine.updates.releases import validate_manifest, release_executable


def install_remote_support(root):
    """Provision system remote support, preserving the controller's ON/OFF state."""
    payload = root / "current/platform/installation/remote-support"
    installer = payload / "install.sh"
    vendor = payload / "install_pl_remote_support.sh"
    if not installer.is_file() or not vendor.is_file():
        raise RuntimeError("Platform installed, but remote-support payload is missing; rebuild this release")
    ui_user = pwd.getpwuid(os.getuid()).pw_name
    if os.geteuid() == 0:
        ui_user = os.environ.get("SUDO_USER", "")
        if not ui_user or ui_user == "root":
            raise RuntimeError("Run the platform installer as the desktop user so remote support can grant that account access")
    command = ["bash", str(installer), ui_user, "--vendor-installer", str(vendor)]
    if os.geteuid() != 0:
        command.insert(0, "sudo")
    print("Installing remote support (administrator authentication may be required)...", flush=True)
    try:
        subprocess.run(command, check=True)
    except (OSError, subprocess.CalledProcessError) as error:
        raise RuntimeError("Platform installed, but remote-support installation failed; rerun the installer to retry: " + str(error)) from error


def install(args):
    with tarfile.open(args.archive.resolve(), "r:gz") as archive:
        member = archive.getmember("manifest.json")
        if member.size > 1024 * 1024 or not member.isfile():
            raise ValueError("Invalid local release manifest")
        local_manifest = json.load(archive.extractfile(member))
    product = local_manifest["product"]
    validate_manifest(local_manifest, product)
    initial_source = {}
    if local_manifest.get("format") == 2:
        with tarfile.open(args.archive.resolve(), "r:gz") as archive:
            seed_name = f"platform/_internal/config/update-source/{local_manifest['robot_system']}.json"
            try:
                seed = archive.getmember(seed_name)
            except KeyError:
                seed = None
            if seed is not None:
                if not seed.isfile() or seed.size > 1024 * 1024:
                    raise ValueError("Invalid bundled update-source configuration")
                initial_source = json.load(archive.extractfile(seed))
                if initial_source.get("product") != product:
                    raise ValueError("Bundled update source belongs to another robot system/profile")
    config_path = (args.config or default_config_path(product)).expanduser().resolve()
    if config_path.exists():
        config = UpdateConfig.load(config_path)
        root = (args.root.expanduser().resolve() if args.root else config.install_root)
        if config.install_root != root or config.product != product:
            raise ValueError("Existing configuration belongs to another robot system/profile installation")
    else:
        root = (args.root or default_install_root(product)).expanduser().resolve()
        atomic_json(config_path, {
            "enabled": False, "repository_url": "", "public_key": None,
            "channel": "stable", **initial_source,
            "product": product, "install_root": str(root),
        })
        config = UpdateConfig.load(config_path)
    updater = PlatformUpdater(config)
    with updater.offline():
        updater._recover()
        if args.storage_from:
            if updater.installed() or (updater.data.exists() and any(updater.data.iterdir())):
                raise ValueError("Storage import is allowed only into an empty first installation")
            source = args.storage_from.expanduser().resolve()
            if not (source / "storage").is_dir():
                raise ValueError("--storage-from must be the old robot-system package directory containing storage/")
            if any(p.is_symlink() for p in source.rglob("*") if p.is_relative_to(source / "storage") or p.is_relative_to(source / "profiles")):
                raise ValueError("Resolve storage symlinks before import")
            temporary = root / ".storage-import"
            if temporary.exists():
                raise ValueError("Interrupted storage import found; inspect .storage-import before retrying")
            temporary.mkdir(parents=True)
            for name in ("storage", "profiles"):
                if (source / name).is_dir():
                    shutil.copytree(source / name, temporary / local_manifest.get("storage_system", "paint") / name)
            if updater.data.exists():
                updater.data.rmdir()
            os.rename(temporary, updater.data)
    current = updater.installed()
    if current != local_manifest:
        updater.stage_local(args.archive.resolve())
        updater.queue()
        updater.apply_pending()
    # Update the independent helper during a trusted installer maintenance run.
    # Subsequent refreshes atomically replace a symlink to a complete tool tree.
    tools = root / "tools"
    with updater.offline():
        tool_versions = root / "updater-tools"
        tool_versions.mkdir(exist_ok=True)
        new_tools = tool_versions / uuid.uuid4().hex
        new_tools.mkdir()
        shutil.copy2(__file__, new_tools / "manage.py")
        updater_source = Path(sys.modules[PlatformUpdater.__module__].__file__).parent
        shutil.copytree(updater_source, new_tools / "src/engine/updates", ignore=shutil.ignore_patterns("__pycache__"))
        (new_tools / "src/__init__.py").touch()
        (new_tools / "src/engine/__init__.py").touch()
        atomic_json(new_tools / "installation.json", {"product": product, "config_path": str(config_path)})
        sync_tree(new_tools)
        sync_directory(tool_versions)
        if tools.exists() and not tools.is_symlink():
            os.rename(tools, tool_versions / ("legacy-" + uuid.uuid4().hex))
        pointer = root / ".tools-new"
        pointer.unlink(missing_ok=True)
        pointer.symlink_to(new_tools.relative_to(root))
        os.replace(pointer, tools)
        sync_directory(root)
    install_remote_support(root)
    print(f"Installed platform at {root}\nUpdate configuration: {config_path}")
    print(f"Launch: /usr/bin/python3 '{tools / 'manage.py'}' --config '{config_path}' launch")


def launch(updater, config_path):
    def apply_or_reopen():
        try:
            return updater.apply_pending()
        except Exception as exc:
            if updater.installed() is None:
                raise
            print(f"Update failed; reopening the previous platform: {exc}", file=sys.stderr)
            return True

    updater.recover()
    apply_or_reopen()
    while True:
        with lock(updater.state / "runtime.lock", shared=True):
            current = updater.installed()
            if current is None:
                raise ValueError("Platform is not installed")
            executable = updater.root / "current/platform" / release_executable(current)
            env = dict(os.environ)
            env["ROBOT_PLATFORM_DATA_ROOT"] = str(updater.data)
            env["ROBOT_PLATFORM_PRODUCT"] = current["product"]
            env["ROBOT_PLATFORM_UPDATE_CONFIG"] = str(config_path.resolve())
            for key in ("VIRTUAL_ENV", "PYTHONHOME", "PYTHONPATH"):
                env.pop(key, None)
            result = subprocess.run([str(executable)], cwd=executable.parent, env=env)
        if result.returncode != 0:
            print("Platform exited with an error; pending update remains unapplied", file=sys.stderr)
            return result.returncode
        if not apply_or_reopen():
            return 0


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--config", type=Path)
    commands = parser.add_subparsers(dest="command", required=True)
    installer = commands.add_parser("install")
    installer.add_argument("archive", type=Path)
    installer.add_argument("--config", type=Path, default=argparse.SUPPRESS)
    installer.add_argument("--root", type=Path)
    installer.add_argument("--storage-from", type=Path)
    for name in ("check", "stage", "queue", "apply", "launch", "recover"):
        commands.add_parser(name)
    rollback = commands.add_parser("rollback")
    rollback.add_argument("--restore-pre-update-data", action="store_true", required=True,
                          help="Restore the data snapshot; newer data stays in an additional backup")
    args = parser.parse_args()
    try:
        if args.command == "install":
            install(args)
            return 0
        if args.config is None:
            metadata = HERE / "installation.json"
            args.config = (Path(json.loads(metadata.read_text())["config_path"])
                           if metadata.is_file() else default_config_path())
        updater = PlatformUpdater(UpdateConfig.load(args.config))
        if args.command == "launch":
            return launch(updater, args.config)
        if args.command in {"check", "stage"}:
            result = updater.check() if args.command == "check" else updater.stage_latest()
            print(json.dumps(result, indent=2))
        elif args.command == "queue":
            updater.queue()
        elif args.command == "apply":
            updater.apply_pending()
        elif args.command == "recover":
            updater.recover()
        elif args.command == "rollback":
            updater.rollback()
        return 0
    except Exception as exc:
        print(f"Platform operation failed: {exc}", file=sys.stderr)
        return 1


if __name__ == "__main__":
    sys.exit(main())
