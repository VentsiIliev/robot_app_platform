# Platform installer and updates

This implementation packages one selected robot system/profile per installer. It preserves the existing
ROS backend launch configuration; it does not install or update ROS or the backend.
Target: Ubuntu 24.04, built on the target CPU architecture.


## Independent system/profile releases

Select a target from `config/release_targets.json`:

| Target | Product |
|---|---|
| paint | paint-robot |
| paint_tray_dry | paint-tray-dry-robot |
| paint_auto_dry | paint-auto-dry-robot |
| glue | glue-robot |
| twin_robot | twin-robot |
| welding | welding-robot |

Each target folder has executable `build_release.sh`, `install_latest.sh` and
`run_latest.sh` scripts. These always select that folder's target, regardless of
`config/platform.json`. For example:

```bash
./src/robot_systems/paint_tray_dry/build_release.sh
./src/robot_systems/paint_tray_dry/install_latest.sh
./src/robot_systems/paint_tray_dry/run_latest.sh

./src/robot_systems/glue/build_release.sh
./src/robot_systems/glue/install_latest.sh
./src/robot_systems/glue/run_latest.sh
```

Edit `src/robot_systems/TARGET/VERSION` to choose that target's release version
(one `major.minor.patch` value, for example `1.0.6`). Each system/profile has its
own file. Tray Dryer starts at `1.0.6`; the other targets start at `1.0.0`.
An explicit argument such as `build_release.sh 1.0.7` overrides the file for that
build without changing it. Missing or invalid version files stop before building.
Install/latest and run/latest continue selecting the latest available installer
and the installed application; they do not depend on `VERSION`.

Replace the folder with any target in the table above. `build_release.sh [VERSION]`
builds a fresh bundle, runs its hardware-free self-test with Qt offscreen, then
creates the installer and update archive. A failed build or self-test stops the
release. It accepts the release options `--channel`, `--output`, `--storage-schema`,
`--migrations`, `--svn-revision` and `--signing-key`. Set `PYTHON_BIN` to override
the build interpreter (default: project `.venv/bin/python`). Relative paths are
resolved from the project root, even when scripts are invoked from another directory.
The install/run scripts accept `--root`, `--config` and `--releases-dir` as described
below. Each system/profile keeps its own installed product and update source.

The lower-level build and package commands remain available:

```bash
./packaging/build_platform.sh paint_tray_dry
.venv/bin/python packaging/platform/build_release.py paint_tray_dry 1.0.6
```

Every target has its own version sequence, artifact folder, installer, data root
and update config. Builds embed only the selected system/profile packages and
shared platform code. Profile builds include their base system dependencies.
Changing a repository URL cannot change the installed product/profile: mismatched
releases are rejected. Versions may be identical across independent products.

Edit `config/update_sources/TARGET.json` before building to choose that target’s
release repository, channel and trusted public-key path. The installer seeds
`~/.config/robot-platform/PRODUCT/updates.json` from that file on first installation
only. Reinstallation and updates preserve the machine’s existing configuration.
For example, tray and automatic dryers use separate `paint_tray_dry.json` and
`paint_auto_dry.json`, and separate installed product config directories. Replace
the example URLs and provision the public key before enabling remote updates.

Existing Paint installations retain their legacy flat config and installation
paths when detected. New installations use the product-specific paths below.
`build_paint.sh` remains a compatibility shortcut for target `paint`.

Twin’s attached runtime currently exposes no idle-state contract. Its Update
screen therefore refuses scheduling while a runtime is attached; close the
platform and use the offline CLI. Twin packaging adds a bootstrap provider, but
backend/runtime provisioning remains a separate phase.

## Convenient local install and launch

From the project root, use the scripts for the desired system/profile:

```bash
./src/robot_systems/paint_tray_dry/install_latest.sh
./src/robot_systems/paint_tray_dry/run_latest.sh
```

Replace `paint_tray_dry` with any target listed above. Each script always selects
its own target. The former root-level install/run shortcuts have been removed.

`install_latest.sh` selects the highest semantic version of a trusted local
installer kit for that target and CPU architecture under
`dist/platform-releases/TARGET/`. Close the platform before installing. The installer also provisions the bundled
PL PROJECT remote-support package and system controller automatically, using
`sudo` only for that step. Run it as the desktop user; it may request that user's
administrator password. Package downloads require internet access. First installation
leaves remote access OFF, and subsequent installations preserve its ON/OFF setting.
A remote-support failure returns an error; rerunning the installer retries it
without replacing platform data. Older kits must be rebuilt to include this step.
Existing
settings and update-source configuration are preserved. It installs a completed
release kit; a raw PyInstaller bundle must first be packaged with `build_release.py`.
`run_latest.sh` starts the selected installed platform through its independent
launcher, including normal pending-update handling. It does not install a newer
local kit automatically. Both scripts work when invoked by absolute path from
another directory. Use `--root` and/or `--config` for custom installations;
`--releases-dir` selects another local release-output directory.

## Build and install

Build the application using the existing virtual environment:

```bash
./packaging/build_platform.sh paint
.venv/bin/python packaging/platform/build_release.py paint 1.0.0
```

Outputs include an update archive under `dist/platform-releases/paint/stable/` and a
`paint-robot-installer-1.0.0-ARCH.tar.gz` installation kit. Extract the kit on the
target and run `paint-robot-installer/install.sh`. It uses `/usr/bin/python3` and
`openssl` from Ubuntu; the GUI bundle contains its own Python runtime.

For an existing machine, import storage during first installation:

```bash
./paint-robot-installer/install.sh \
  --storage-from /home/operator/robot_app_platform/src/robot_systems/paint
```

`--storage-from` points at the paint package, not just its `storage` directory:
this imports both base storage and all profile storage. The source is untouched.
Import is refused if the destination already contains data. Reinstallation and
updates never import or overwrite storage from a release.

The default installation is per-user, with no root privileges:

```text
~/.local/share/robot-platform/products/paint-robot/
    releases/VERSION/platform/
    current -> releases/VERSION
    data/paint/storage/
    data/paint/profiles/PROFILE/storage/
    tools/manage.py
    update-state/
    backups/
~/.config/robot-platform/paint-robot/updates.json
```

Use `--root /absolute/path` and `--config /absolute/path/updates.json` to choose
other locations. Install as the HMI user so data and tools have the right owner.
The installer prints the launch command. Always use that independent launcher
for installed operation:

```bash
/usr/bin/python3 ~/.local/share/robot-platform/products/paint-robot/tools/manage.py launch
```

The launcher exits when the GUI closes normally unless an update is pending. With
a pending update, it applies the update and launches the new version. It does not
auto-resume production. Existing backend start/stop behavior remains unchanged.
Direct GUI executable launches also hold the update lock, but cannot apply queued
updates themselves. For development, source runs keep their existing paths unless
`ROBOT_PLATFORM_DATA_ROOT` is explicitly set.

Live machine settings, accounts, calibration and workpieces are excluded from releases.
Authored hardware factory templates live separately in `config/factory_defaults/TARGET.json`
and are bundled as software resources. First installation and standalone startup
seed missing hardware/dryer files before serializers load them. Updates seed any
missing factory files in the staged data copy after migrations. An existing file
is always preserved byte-for-byte, even if empty; templates never merge or reset
its values. Other settings use their serializer defaults. Review the factory
hardware mapping and perform normal machine setup/calibration before production.
Translations are software resources and stay inside releases. The selected UI
language is stored with external settings.

## Configure the update source

The installer creates `~/.config/robot-platform/paint-robot/updates.json` only if absent.
Updates never replace it. See `config/updates.example.json` for all options.
`ROBOT_PLATFORM_UPDATE_CONFIG` selects another file for the application; use
`--config` with the independent CLI/launcher for the same installation.

```json
{
  "enabled": true,
  "repository_url": "https://your-server/releases/platform/",
  "public_key": "/home/operator/.config/robot-platform/release-public.pem",
  "product": "paint-robot",
  "channel": "stable",
  "install_root": "/home/operator/.local/share/robot-platform/products/paint-robot"
}
```

The repository is an HTTPS release directory, not an SVN working-copy URL.
Your SVN build job exports a fixed source revision, builds/tests the bundle and
publishes the resulting files. Machines download prebuilt, authenticated releases.
Credentials do not belong in the URL. This first implementation expects a release
endpoint accessible without interactive authentication; private endpoints need
an authentication mechanism added before deployment.

## Local-folder update testing

Use a trusted local release folder as `repository_url` to exercise the same
Check → Download → Schedule → Close → Activate workflow without an HTTPS server:

```json
{
  "enabled": true,
  "repository_url": "/home/ilv/Desktop/robot_app_platform/dist/platform-releases/paint_tray_dry",
  "public_key": null,
  "product": "paint-tray-dry-robot",
  "channel": "stable",
  "install_root": "/home/ilv/.local/share/robot-platform/products/paint-tray-dry-robot"
}
```

The updater reads `stable/latest.json` and its referenced archive. Pointing
directly at the `stable` folder also works. It compares the manifest version with
the installed version; unchanged/older versions report up to date. Local sources
must be absolute paths. Missing files produce an on-screen error. Local releases
without a public key are trusted installation inputs; only use your own release
output. If a public key is configured, local manifest signatures are verified too.
HTTPS sources always require a public key and a signed manifest. Checksums, target,
profile, channel, OS/CPU compatibility, safe extraction, self-tests and data
protection apply to both sources. Build/publish a higher release version to test
an available update. Existing installs need the local-source-capable maintenance
installer before this config can be used.

## Sign and publish releases

Create a signing key on the release builder and distribute its public key to the
machines through a trusted installation process:

```bash
openssl genpkey -algorithm RSA -pkeyopt rsa_keygen_bits:3072 -out release-private.pem
openssl pkey -in release-private.pem -pubout -out release-public.pem
.venv/bin/python packaging/platform/build_release.py paint 1.1.0 \
  --svn-revision 1842 --signing-key /secure/path/release-private.pem
```

Keep the private key outside the checkout, archives and installed machines.
Publish this layout:

```text
releases/platform/stable/
    latest.json
    latest.json.sig
    paint-robot-1.1.0-x86_64.tar.gz
```

Publish the archive first, then the matching signed manifest/signature pair.
Release versions are immutable; publish a higher `major.minor.patch` version for
changed contents. During a partially published manifest pair, verification fails
and the existing installation is unaffected. Unsigned builds are usable for
trusted local first installation, but remote updates require a valid signature.
The legacy `release_paint.sh` GitHub publishing workflow is separate and does not
produce this updater's release format.

## Apply an update

Administrators have a Software Update application in each system’s Administration
folder. Check, download, then schedule installation. Stop production before
scheduling. Close the platform normally; the launcher performs the update after
all platform processes have exited and reopens it. Backend software is unchanged.

Equivalent commands:

```bash
/usr/bin/python3 ~/.local/share/robot-platform/products/paint-robot/tools/manage.py check
/usr/bin/python3 ~/.local/share/robot-platform/products/paint-robot/tools/manage.py stage
/usr/bin/python3 ~/.local/share/robot-platform/products/paint-robot/tools/manage.py queue
# Close the GUI before using apply without the managed launcher.
/usr/bin/python3 ~/.local/share/robot-platform/products/paint-robot/tools/manage.py apply
```

The updater verifies the signed manifest, SHA-256, product, system, profile, OS and architecture.
It rejects unsafe archives, symlinks, live storage in releases and reused release
versions. Each candidate runs a hardware-free frozen self-test before staging. Activation takes an exclusive runtime lock, copies storage, migrates
that copy, retains the original as a backup and atomically changes the release
pointer. A transaction journal recovers interrupted activation before launching.
Downloads/migrations that fail leave the previous release and live data intact.
A failed GUI exit leaves a queued update unapplied.

The result is recorded in `update-state/result.json` and displayed when the Update
screen next opens. If activation fails, the launcher reopens the previous platform. The frozen self-test verifies imports, resources and Qt before staging. Runtime
health monitoring and automatic rollback on a later GUI startup failure are not implemented; use
explicit recovery/rollback. Production rollout still requires testing a real
bundle on a clean target machine with its GUI/hardware dependencies.

## Schema changes

Schema 1 is the initial format. For schema 2, provide `migrations/2.json` and build
with `--storage-schema 2 --migrations /path/to/migrations`. Include every intermediate
migration to support machines skipping releases. Operations are system-relative:

```json
[
  {
    "file": "paint/storage/settings/paint/process.json",
    "action": "add",
    "path": ["retry_count"],
    "value": 3
  },
  {
    "file": "paint/storage/settings/paint/process.json",
    "action": "rename",
    "path": ["old_field"],
    "to": "new_field"
  },
  {
    "file": "paint/storage/settings/paint/process.json",
    "action": "remove",
    "path": ["obsolete_field"]
  }
]
```

Add sets a value only when absent. Rename preserves the saved value and refuses
to overwrite another field. Remove deletes only the declared field. Other fields
and files remain unchanged. List transformations and unit/type conversions need
explicit migration support before shipping a release requiring them. Serializers
must also remain compatible with the migrated schema; test their load/save round
trips when changing settings contracts. No automatic defaults overlay is applied.

## Recovery and rollback

The launcher automatically recovers an interrupted activation. It can also be
invoked manually while the GUI is closed:

```bash
/usr/bin/python3 ~/.local/share/robot-platform/products/paint-robot/tools/manage.py recover
/usr/bin/python3 ~/.local/share/robot-platform/products/paint-robot/tools/manage.py rollback \
  --restore-pre-update-data
```

Rollback restores previous software and its pre-update storage snapshot together.
Data created after updating is retained in an additional backup, but is no longer
live after rollback. Backups/releases are retained; plan disk capacity and an
operator-managed retention policy. Do not edit/install directly into `current`.

The independent updater is refreshed by a trusted maintenance installation kit.
Remote application updates leave that helper unchanged. Its complete versioned
tree is selected through an atomic tools pointer.

## Startup failures

Packaged startup errors open a desktop dialog with the error and expandable
traceback details. The traceback is also saved as
`INSTALL_ROOT/update-state/last-startup-error.log`. Build self-tests remain
noninteractive. Tray Dryer fresh settings default to its supported `plate_layout`
strategy; loading existing settings does not silently rewrite saved strategies.

Maintain factory templates separately from development storage: changing live
settings does not change release defaults. Supported factory files are
`hardware/peripherals.json`, `hardware/modbus.json`, `hardware/cameras.json` and
`dryer/settings.json`. Paint variants have individual templates; Glue includes its
Modbus template. Twin and Welding currently have empty template sets and use
serializer defaults until their hardware configurations are defined. Existing
empty files created by older builds require an explicit, backed-up initialization;
ordinary installation/update preserves them.
