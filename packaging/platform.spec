# -*- mode: python ; coding: utf-8 -*-
"""Build exactly one declared robot system/profile."""
import os
import sys
from pathlib import Path
from PyInstaller.utils.hooks import collect_data_files

ROOT = Path.cwd().resolve()
sys.path.insert(0, str(ROOT / "packaging/platform"))
from targets import load_target

target = load_target(os.environ.get("ROBOT_PLATFORM_BUILD_TARGET", "paint"))
config_dir = ROOT / "build/platform-config" / target["target"]
datas = [(str(config_dir / "platform.json"), "config"),
         (str(config_dir / "factory-defaults.json"), "config"),
         (str(config_dir / "release-target.json"), "config"),
         (str(ROOT / "config/update_sources" / (target["target"] + ".json")), "config/update-source")]
# Give the system-specific source file a stable bundled name for the installer.
# PyInstaller retains its basename; the target marker identifies which file to read.
for resource in ("src/applications/base/resources", "src/applications/localization",
                 "pl_gui/dashboard/resources", "pl_gui/shell/resources"):
    datas.append((str(ROOT / resource), resource))
for translations in sorted((ROOT / "src/applications").glob("*/localization")):
    datas.append((str(translations), str(translations.relative_to(ROOT))))
for package in target["packages"]:
    package_root = ROOT / "src/robot_systems" / package
    for translations in sorted(package_root.rglob("translations")):
        if translations.is_dir() and (translations / "en.json").is_file():
            datas.append((str(translations), str(translations.relative_to(ROOT))))
datas += collect_data_files("contour_editor")
datas += collect_data_files("qtawesome")
excluded = [f"src.robot_systems.{path.name}" for path in (ROOT / "src/robot_systems").iterdir()
            if path.is_dir() and path.name not in target["packages"] and path.name != "__pycache__"]
analysis = Analysis([str(ROOT / "packaging/platform_entrypoint.py")], pathex=[str(ROOT)],
                    binaries=[], datas=datas,
                    hiddenimports=[f"src.robot_systems.{target['robot_system']}.bootstrap_provider",
                                   "src.applications.network_settings.build_application"],
                    hookspath=[], hooksconfig={}, runtime_hooks=[], excludes=excluded,
                    noarchive=False, optimize=0)
pyz = PYZ(analysis.pure)
executable = EXE(pyz, analysis.scripts, [], exclude_binaries=True,
                 name=target["executable"], debug=False, bootloader_ignore_signals=False,
                 strip=False, upx=True, console=True)
bundle = COLLECT(executable, analysis.binaries, analysis.datas,
                 strip=False, upx=True, upx_exclude=[], name=target["product"])
