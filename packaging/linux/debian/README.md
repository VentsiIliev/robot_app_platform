# Linux Debian Package

This packaging path creates an installable Ubuntu 24.04 amd64 `.deb` for the
Robot App Platform paint operator application.

## Design

The package installs:

```text
/opt/robot-app-platform/app/       committed application source and data seed
/opt/robot-app-platform/runtime/   bundled prepared Python virtual environment
/usr/bin/robot-app-platform        desktop/CLI launcher
```

Robot-system settings, calibration updates, users, workpieces, and generated
debug data must remain writable. On launch, the installed command maintains a
per-user runnable mirror under:

```text
${XDG_DATA_HOME:-$HOME/.local/share}/robot-app-platform/app/
```

Package upgrades refresh application code in that mirror while retaining
runtime-owned storage directories.
The launcher preserves file contents and modes without copying package
ownership or group metadata into the per-user tree.

Startup output is written to:

```text
${XDG_DATA_HOME:-$HOME/.local/share}/robot-app-platform/logs/launcher.log
```

This captures import, Qt, hardware connection, and settings errors from
desktop-menu launches where no terminal is visible.

## Build

Build from the prepared Ubuntu checkout containing `.venv/`:

```bash
packaging/linux/debian/build_deb.sh 0.1.1
```

Output:

```text
dist/linux/robot-app-platform_0.1.1_amd64.deb
```

The package bundles the prepared virtual environment because the repository
does not currently define a reproducible Python dependency manifest. It is
therefore intended for Ubuntu 24.04 amd64 machines matching the build runtime.

## Install

```bash
sudo apt install ./robot-app-platform_0.1.1_amd64.deb
robot-app-platform
```

The application is also available from the desktop application menu after
installation.

## Smoke Check

To prepare the per-user runtime copy without commanding hardware or opening the
GUI:

```bash
robot-app-platform --prepare-only
```

Full cell validation must be performed with verified robot, camera,
calibration, targeting, and safety settings on the deployed machine.

If a desktop-menu launch does not open a window, inspect:

```bash
tail -n 100 "${XDG_DATA_HOME:-$HOME/.local/share}/robot-app-platform/logs/launcher.log"
```
