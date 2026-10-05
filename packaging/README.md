# Robot platform packaging

Use [Platform installer and updates](platform/README.md) for independent system/profile installers, dedicated update-source configs, signing and data-preserving updates. The commands below retain the older Paint build/publishing workflow.

# Paint standalone build

The Ubuntu remote support controller is installed separately from the
application bundle. See [Network Settings](../docs/applications/network_settings/README.md)
for the installer, boot behavior, and validation path.
The build stages its complete installation payload inside
`paint-robot/installation/remote-support/`, so release archives carry the
installer without requiring the repository on the robot. The final product
installer can invoke that payload with the configured HMI user.
The platform's rebranded RustDesk installer is included by default.
`PL_SUPPORT_VENDOR_INSTALLER` can select an alternate script; it must support
`--provision-only`. See the [payload guide](remote_support/README.md).

This profile creates a PyInstaller `onedir` distribution for the paint robot
system. It bundles Python and pip-installed runtime dependencies, so Python is
not required on the target machine.

The Paint target excludes all other robot systems. Shared
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

Mutable settings, users, calibration artifacts, and workpieces are excluded
from the bundle. Standalone execution uses external storage; installed operation
uses the independent launcher and versioned releases. See
[Platform installer and updates](platform/README.md) for installation, migration
of existing machine storage, the configurable HTTPS release source, signing,
and rollback. ROS backend software remains outside this update mechanism.
