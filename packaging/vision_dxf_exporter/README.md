# PL DXF Vision Build

Build the complete standalone Windows installer from the repository root:

```bat
packaging\vision_dxf_exporter\build_installer_windows.bat
```

The build creates:

- `dist\PLDxfVision\PLDxfVision.exe`
- `dist\PLDxfVision\vision\...` with bundled camera settings and calibration data
- `dist\installer\PLDxfVisionSetup.exe`
- `dist\installer\PLDxfVisionSetup.msi` when the MSI build is run

The installer contains the PyInstaller build output, so the target PC does not need Python,
the project repository, or the project `.venv`.

The standalone exporter excludes `pyzbar`. QR/barcode detection is optional and is loaded lazily
only if QR scanning is explicitly called, so missing `zbar` native DLLs cannot prevent contour
capture or DXF export from starting.

The installer includes optional tasks for:

- creating a desktop shortcut
- starting PL DXF Vision when the current Windows user logs in

Build only the unpacked standalone executable with:

```bat
packaging\vision_dxf_exporter\build_windows.bat
```

Or manually compile the installer after running the PyInstaller build:

```bat
iscc packaging\vision_dxf_exporter\installer.iss
```

## Building From Linux With Wine

PyInstaller does not cross-compile a Windows executable from native Linux Python. The Windows
build must run under Windows Python, either on a Windows machine, a Windows CI runner, a Windows VM,
or Windows Python installed inside Wine.

If you see a path like `/usr/bin\python.exe`, the build is mixing Linux Python/MSYS paths with
Windows tooling. Do not run PyInstaller for the Windows exe with native `/usr/bin/python`.

Wine build prerequisites:

- Wine
- Windows Python installed inside the Wine prefix
- Python dependencies installed into that Windows Python environment
- Inno Setup 6 installed inside the Wine prefix, if you want the installer
- WiX `heat.exe` plus Linux `wixl`, if you want the one-file MSI

From Linux, after those are installed:

```bash
chmod +x packaging/vision_dxf_exporter/build_installer_wine.sh
packaging/vision_dxf_exporter/build_installer_wine.sh
```

If the Wine Python launcher is not available as `py.exe`, point the script at the exact Windows
Python executable:

```bash
WINE_PYTHON_EXE='C:\Python311\python.exe' packaging/vision_dxf_exporter/build_installer_wine.sh
```

If Inno Setup is installed somewhere else:

```bash
WINE_ISCC_EXE='C:\Program Files\Inno Setup 6\ISCC.exe' packaging/vision_dxf_exporter/build_installer_wine.sh
```

Build the one-file MSI from Linux/Wine with:

```bash
chmod +x packaging/vision_dxf_exporter/build_msi_wixl.sh
packaging/vision_dxf_exporter/build_msi_wixl.sh
```

The MSI installs to `Program Files\PL DXF Vision` and creates a Start Menu shortcut.

On first launch, the installed app copies the bundled `vision` folder into a user-writable app-data location:

`%LOCALAPPDATA%\PLDxfVision\vision`

You can still override paths at launch:

```bat
PLDxfVision.exe --settings-file C:\path\camera_settings.json --data-storage-path C:\path\data
```

## Windows Startup vs Windows Service

The exporter is a GUI application, so the installer uses a Startup shortcut for automatic launch.
That is the correct Windows mechanism for starting an interactive Qt application at login.

A true Windows Service runs in a non-interactive background session and should not directly host
the PyQt6 GUI. If background capture/export is required before user login, split it into a separate
non-GUI service executable and keep this app as the operator UI.
