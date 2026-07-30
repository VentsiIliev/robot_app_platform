# Paint standalone build

This profile creates a PyInstaller `onedir` distribution for the paint robot
system. It bundles Python and pip-installed runtime dependencies, so Python is
not required on the target machine.

The profile explicitly excludes the glue and welding robot systems. Shared
platform modules and shared applications are included when they are imported
by the paint application.

The bundled startup configuration lists only `paint` as an installed and
supported robot system.

The contour-editor dependency currently imports its runtime `RadialMenu` class
from a module under its own `tests/examples` package. That module is therefore
runtime code despite its upstream path and cannot safely be excluded here.

## Build

Build on the same Linux distribution and CPU architecture as the target:

```bash
.venv/bin/python -m pip install -r packaging/requirements-build.txt
./packaging/build_paint.sh
```

The output is `dist/paint-robot/`. Test it with:

```bash
./dist/paint-robot/paint-robot
```

The ROS 2 Fairino bridge is not bundled. With the current configuration, it
must be reachable at `http://localhost:5000`.

## Runtime data

This first build preserves the application's current storage behavior and
places paint settings inside the bundle. Before installing the application
under a read-only system directory such as `/opt`, move mutable settings,
users, calibration artifacts, and workpieces to an external data directory.
