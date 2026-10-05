#!/usr/bin/env python3
"""Build one robot-system/profile bundle without bundling other systems."""
import argparse
import ast
import os
from pathlib import Path
import subprocess
import sys

from targets import ROOT, load_target, prepare_target


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("target", help="Key from config/release_targets.json")
    args = parser.parse_args()
    target = load_target(args.target)
    config_dir = ROOT / "build/platform-config" / args.target
    prepare_target(args.target, config_dir)
    work = ROOT / "build/pyinstaller" / args.target
    environment = dict(os.environ, ROBOT_PLATFORM_BUILD_TARGET=args.target)
    environment["MPLCONFIGDIR"] = str(work / "matplotlib")
    Path(environment["MPLCONFIGDIR"]).mkdir(parents=True, exist_ok=True)
    subprocess.run([sys.executable, "-m", "PyInstaller", "--noconfirm", "--clean",
                    "--distpath", str(ROOT / "dist"), "--workpath", str(work),
                    "packaging/platform.spec"], cwd=ROOT, env=environment, check=True)
    toc = ast.literal_eval((work / "platform/PYZ-00.toc").read_text())
    # PYZ entries are nested; inspect module-name tuples rather than source paths.
    def modules(value):
        if isinstance(value, (tuple, list)):
            if value and isinstance(value[0], str):
                yield value[0]
            for item in value:
                yield from modules(item)
    allowed = set(target["packages"])
    for module in modules(toc):
        parts = module.split(".")
        if parts[:2] == ["src", "robot_systems"] and len(parts) > 3 and parts[2] not in allowed:
            raise RuntimeError(f"Other robot system bundled: {module}")
        if parts[:2] == ["src", "robot_systems"] and "example_usage" in parts:
            raise RuntimeError(f"Development example bundled: {module}")
    bundle = ROOT / "dist" / target["product"]
    support = [sys.executable, "packaging/remote_support/build_payload.py", str(bundle / "installation/remote-support")]
    if os.environ.get("PL_SUPPORT_VENDOR_INSTALLER"):
        support += ["--vendor-installer", os.environ["PL_SUPPORT_VENDOR_INSTALLER"]]
    subprocess.run(support, cwd=ROOT, check=True)
    print(f"{args.target} bundle created at: {bundle}")


if __name__ == "__main__":
    main()
