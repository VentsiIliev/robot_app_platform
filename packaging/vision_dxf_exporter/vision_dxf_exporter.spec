# -*- mode: python ; coding: utf-8 -*-

from pathlib import Path
import importlib.util

block_cipher = None
repo_root = Path.cwd()
vision_root = repo_root / "src" / "robot_systems" / "paint" / "storage" / "settings" / "vision"

datas = []
if vision_root.exists():
    datas.append((str(vision_root), "vision"))
logo_path = repo_root / "packaging" / "vision_dxf_exporter" / "Logo.png"
icon_path = repo_root / "packaging" / "vision_dxf_exporter" / "PLDxfVision.ico"
if logo_path.exists():
    datas.append((str(logo_path), "assets"))

a = Analysis(
    [str(repo_root / "src" / "tools" / "vision_dxf_exporter" / "run.py")],
    pathex=[str(repo_root)],
    binaries=[],
    datas=datas,
    hiddenimports=[
        "cv2",
        "ezdxf",
        "numpy",
        "PyQt6",
        "PyQt6.QtCore",
        "PyQt6.QtGui",
        "PyQt6.QtWidgets",
        "src.engine.vision.implementation.VisionSystem.VisionSystem",
        "src.engine.vision.implementation.plvision.PLVision.Camera",
        "src.engine.vision.implementation.plvision.PLVision.ImageProcessing",
    ],
    hookspath=[],
    hooksconfig={},
    runtime_hooks=[],
    excludes=["pyzbar"],
    win_no_prefer_redirects=False,
    win_private_assemblies=False,
    cipher=block_cipher,
    noarchive=False,
)
pyz = PYZ(a.pure, a.zipped_data, cipher=block_cipher)

exe = EXE(
    pyz,
    a.scripts,
    [],
    exclude_binaries=True,
    name="PLDxfVision",
    debug=False,
    bootloader_ignore_signals=False,
    strip=False,
    upx=True,
    console=False,
    disable_windowed_traceback=False,
    argv_emulation=False,
    target_arch=None,
    codesign_identity=None,
    entitlements_file=None,
    icon=str(icon_path) if icon_path.exists() else None,
)
coll = COLLECT(
    exe,
    a.binaries,
    a.zipfiles,
    a.datas,
    strip=False,
    upx=True,
    upx_exclude=[],
    name="PLDxfVision",
)
