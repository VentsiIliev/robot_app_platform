# -*- mode: python ; coding: utf-8 -*-
"""PyInstaller configuration for the paint-only robot application."""

from pathlib import Path

from PyInstaller.utils.hooks import collect_data_files


ROOT = Path.cwd().resolve()

datas = [
    (str(ROOT / "packaging" / "paint_config" / "platform.json"), "config"),
    (str(ROOT / "src" / "applications" / "base" / "resources"), "src/applications/base/resources"),
    (str(ROOT / "src" / "applications" / "localization"), "src/applications/localization"),
    (str(ROOT / "src" / "robot_systems" / "paint" / "storage"), "src/robot_systems/paint/storage"),
    (str(ROOT / "pl_gui" / "dashboard" / "resources"), "pl_gui/dashboard/resources"),
    (str(ROOT / "pl_gui" / "shell" / "resources"), "pl_gui/shell/resources"),
]
datas += collect_data_files("contour_editor")
datas += collect_data_files("qtawesome")

hiddenimports = [
    "src.robot_systems.paint.bootstrap_provider",
]

excluded_robot_systems = [
    "src.robot_systems.glue",
    "src.robot_systems.welding",
    "src.robot_systems.ROBOT_SYSTEM_BLUEPRINT",
]

analysis = Analysis(
    [str(ROOT / "packaging" / "paint_entrypoint.py")],
    pathex=[str(ROOT)],
    binaries=[],
    datas=datas,
    hiddenimports=hiddenimports,
    hookspath=[],
    hooksconfig={},
    runtime_hooks=[],
    excludes=excluded_robot_systems,
    noarchive=False,
    optimize=0,
)

pyz = PYZ(analysis.pure)

executable = EXE(
    pyz,
    analysis.scripts,
    [],
    exclude_binaries=True,
    name="paint-robot",
    debug=False,
    bootloader_ignore_signals=False,
    strip=False,
    upx=True,
    console=True,
    disable_windowed_traceback=False,
    argv_emulation=False,
    target_arch=None,
    codesign_identity=None,
    entitlements_file=None,
)

bundle = COLLECT(
    executable,
    analysis.binaries,
    analysis.datas,
    strip=False,
    upx=True,
    upx_exclude=[],
    name="paint-robot",
)
