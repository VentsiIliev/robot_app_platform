#!/usr/bin/env python3
"""Package an existing PyInstaller bundle into a platform-only release."""
import argparse
import hashlib
import json
import platform
from pathlib import Path
import subprocess
import sys
import tarfile
import tempfile

sys.path.insert(0, str(Path(__file__).resolve().parents[2]))
from src.engine.updates.releases import version_tuple
from src.engine.updates.factory_defaults import load_factory_defaults
from targets import load_target


def release_parser():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("target", help="Target name, or version for legacy paint-only usage")
    parser.add_argument("version", nargs="?")
    parser.add_argument("--bundle", type=Path)
    parser.add_argument("--output", type=Path, default=Path("dist/platform-releases"))
    parser.add_argument("--channel", choices=("stable", "testing"), default="stable")
    parser.add_argument("--storage-schema", type=int, default=1)
    parser.add_argument("--migrations", type=Path)
    parser.add_argument("--svn-revision", help="Exact source revision used by the SVN build job")
    parser.add_argument("--signing-key", type=Path)
    return parser


def main():
    parser = release_parser()
    args = parser.parse_args()
    if args.version is None:
        args.version, args.target = args.target, "paint"
    release_target = load_target(args.target)
    product = release_target["product"]
    version_tuple(args.version)
    if args.storage_schema < 1:
        parser.error("storage schema must be positive")
    bundle = (args.bundle or Path("dist") / product).resolve()
    if not (bundle / release_target["executable"]).is_file():
        parser.error(f"Build target {args.target} first")
    marker = bundle / "_internal/config/release-target.json"
    if not marker.is_file() or json.loads(marker.read_text()) != release_target:
        parser.error("Bundle identity does not match the selected robot system/profile; rebuild it")
    if not (bundle / "_internal/config/factory-defaults.json").is_file():
        parser.error("Bundle has no factory configuration; rebuild the selected target")
    load_factory_defaults(bundle / "_internal", release_target)
    if args.storage_schema > 1 and not args.migrations:
        parser.error("A higher storage schema requires migrations")
    product_output = args.output / args.target
    output = product_output / args.channel
    output.mkdir(parents=True, exist_ok=True)
    archive = output / f"{product}-{args.version}-{platform.machine()}.tar.gz"
    if archive.exists():
        parser.error("Release already exists; use a new version or output directory")
    manifest = {"format": 2, "product": product, "version": args.version,
                **{key: release_target[key] for key in ("robot_system", "profile", "storage_system", "executable")},
                "architecture": platform.machine(), "os": "ubuntu-24.04",
                "storage_schema": args.storage_schema, "source_svn_revision": args.svn_revision}
    with tempfile.TemporaryDirectory() as temporary:
        internal = Path(temporary) / "manifest.json"
        internal.write_text(json.dumps(manifest, indent=2), encoding="utf-8")
        with tarfile.open(archive, "w:gz", dereference=True) as target:
            target.add(internal, arcname="manifest.json")
            def exclude_storage(member):
                parts = Path(member.name).parts
                if any(p in {"storage", "profiles"} for p in parts):
                    source_path = bundle.joinpath(*parts[1:])
                    if "translations" not in parts and not source_path.is_dir():
                        raise ValueError(f"Bundle contains live machine data: {member.name}")
                return member
            target.add(bundle, arcname="platform", filter=exclude_storage)
            if args.migrations:
                target.add(args.migrations, arcname="migrations")
    with archive.open("rb") as stream:
        manifest["sha256"] = hashlib.file_digest(stream, "sha256").hexdigest()
    manifest.update(archive=archive.name, channel=args.channel)
    latest = output / "latest.json"
    latest.write_text(json.dumps(manifest, indent=2), encoding="utf-8")
    if args.signing_key:
        subprocess.run(["openssl", "dgst", "-sha256", "-sign", str(args.signing_key),
                        "-out", str(latest) + ".sig", str(latest)], check=True)
    else:
        Path(str(latest) + ".sig").unlink(missing_ok=True)
        print("Unsigned local release: remote updates require --signing-key")
    kit = product_output / f"{product}-installer-{args.version}-{platform.machine()}.tar.gz"
    kit_prefix = f"{product}-installer"
    source = Path(__file__).resolve().parents[2]
    with tempfile.TemporaryDirectory() as temporary:
        kit_root = Path(temporary)
        installer = kit_root / "install.sh"
        installer.write_text('#!/usr/bin/env bash\nset -euo pipefail\nINSTALL_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"\nexec /usr/bin/python3 "$INSTALL_DIR/tools/manage.py" install "$INSTALL_DIR/release.tar.gz" "$@"\n')
        installer.chmod(0o755)
        with tarfile.open(kit, "w:gz", dereference=True) as target:
            target.add(installer, arcname=f"{kit_prefix}/install.sh")
            target.add(archive, arcname=f"{kit_prefix}/release.tar.gz")
            target.add(Path(__file__).with_name("manage.py"), arcname=f"{kit_prefix}/tools/manage.py")
            def exclude_cache(member):
                return None if "__pycache__" in Path(member.name).parts else member
            target.add(source / "src/engine/updates", arcname=f"{kit_prefix}/tools/src/engine/updates", filter=exclude_cache)
            target.add(source / "src/__init__.py", arcname=f"{kit_prefix}/tools/src/__init__.py")
            target.add(source / "src/engine/__init__.py", arcname=f"{kit_prefix}/tools/src/engine/__init__.py")
    print(archive)
    print(kit)


if __name__ == "__main__":
    main()
