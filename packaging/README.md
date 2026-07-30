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

The requirements file contains build and release tooling, including PyInstaller
and the coverage package used by the repository test harness. These tools are
needed only on the build machine, not on machines running the bundle.

The output is `dist/paint-robot/`. Test it with:

```bash
./dist/paint-robot/paint-robot
```

The ROS 2 Fairino bridge is not bundled. With the current configuration, it
must be reachable at `http://localhost:5000`.

## Release

The release helper uses system-specific tags such as `paint-v1.0.0`, keeping
paint releases distinct from glue and welding releases in this repository.
The version must match `PaintRobotSystem.metadata.version`, the current branch
must be `work`, and the working tree must be clean.

Prepare and test a local release archive without changing Git or GitHub:

```bash
./packaging/release_paint.sh 1.0.0
```

After testing the generated bundle, publish the annotated tag, archive,
SHA-256 checksum, and GitHub release:

```bash
./packaging/release_paint.sh 1.0.0 --publish
```

The publish step also checks that local `work` exactly matches `origin/work`.
Use `--skip-tests` only when the same commit has already passed the test suite.

## Runtime data

This first build preserves the application's current storage behavior and
places paint settings inside the bundle. Before installing the application
under a read-only system directory such as `/opt`, move mutable settings,
users, calibration artifacts, and workpieces to an external data directory.
