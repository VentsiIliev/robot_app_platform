#!/usr/bin/env python3
"""Build, verify without hardware, and package an explicitly selected target."""
import os
from pathlib import Path
import platform
import subprocess
import sys

from build_release import release_parser
from targets import ROOT, load_target
from src.engine.updates.releases import version_tuple


def main(argv=None):
    arguments = list(sys.argv[1:] if argv is None else argv)
    parser = release_parser()
    args = parser.parse_args(arguments)
    if args.bundle is not None:
        parser.error("This command builds a fresh bundle; use build_release.py to package an existing bundle")
    try:
        target = load_target(args.target)
        if args.version is None:
            version_file = ROOT / "src/robot_systems" / args.target / "VERSION"
            try:
                args.version = version_file.read_text(encoding="utf-8").strip()
            except OSError as error:
                parser.error(f"Cannot read release version from {version_file}: {error}")
            # Make the configured version explicit for the lower-level packager.
            arguments.insert(1, args.version)
        version_tuple(args.version)
    except ValueError as error:
        parser.error(str(error))
    if args.storage_schema < 1 or (args.storage_schema > 1 and not args.migrations):
        parser.error("A positive storage schema and migrations for schemas above 1 are required")
    archive = args.output / args.target / args.channel / f"{target['product']}-{args.version}-{platform.machine()}.tar.gz"
    if archive.exists():
        parser.error("Release already exists; use a new version or output directory")
    subprocess.run([sys.executable, str(ROOT / "packaging/platform/build.py"), args.target], cwd=ROOT, check=True)
    executable = ROOT / "dist" / target["product"] / target["executable"]
    environment = dict(os.environ, QT_QPA_PLATFORM="offscreen")
    subprocess.run([str(executable), "--self-test"], cwd=ROOT, env=environment, check=True)
    subprocess.run([sys.executable, str(ROOT / "packaging/platform/build_release.py"), *arguments], cwd=ROOT, check=True)
    return 0


if __name__ == "__main__":
    try:
        sys.exit(main())
    except (OSError, subprocess.CalledProcessError) as error:
        print(f"Build/release failed: {error}", file=sys.stderr)
        sys.exit(1)
