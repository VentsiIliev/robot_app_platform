# Ubuntu remote support installation

This payload is included in platform release archives for every system/profile under
`installation/remote-support/`. It runs independently of the application
bundle and does not need a source checkout or the application's Python
environment. Ubuntu must provide `/usr/bin/python3`, systemd, and an installed
`rustdesk.service`.

The platform installer invokes this automatically with the bundled vendor installer,
using sudo for the system step and passing the desktop user. It preserves the saved
ON/OFF state and defaults to OFF on first installation. To run the step manually:

```bash
sudo bash installation/remote-support/install.sh ROBOT_UI_USER
```

To also provision the rebranded PL PROJECT build, pass its trusted installer:

```bash
sudo bash installation/remote-support/install.sh ROBOT_UI_USER \
  --vendor-installer installation/remote-support/install_pl_remote_support.sh
```

The vendor script must support `--provision-only`: install and verify the
package, but leave service startup and GUI launch to the robot platform.
The boot gate is installed before calling it so package post-install actions
cannot enable remote support while the saved choice is OFF. The current
PL PROJECT installer downloads a pinned release and requires network access;
an offline product installer will need the corresponding verified package.

Stage the vendor installer into a release payload with:

```bash
python3 packaging/remote_support/build_payload.py /tmp/support-payload \
  --vendor-installer /home/ilv/src/rustdesk/install_pl_remote_support.sh
```

The platform owns a packaged copy at
`packaging/remote_support/install_pl_remote_support.sh`. Paint builds include
that copy by default. `PL_SUPPORT_VENDOR_INSTALLER` optionally selects an
alternate installer when building. Update the platform copy deliberately
when changing the supported branded release; packaging does not read a
separate RustDesk source checkout.

First installation defaults to OFF and ends any current RustDesk session.
Upgrades preserve the customer choice. The HMI runs without administrator
privileges; it talks to the socket owned by its configured account.

Provision RustDesk's relay/server settings separately. Its own `stop-service`
option must be cleared in both the system and HMI user's configuration:
otherwise RustDesk can stop itself immediately after the customer selects ON.
The support installer does not overwrite RustDesk connection credentials or
desktop configuration. The product provisioning workflow must validate those
settings before enabling remote support.

The payload installs the helper under `/usr/local/libexec`, two systemd units,
and a RustDesk drop-in. Customer state remains under
`/var/lib/plproject/remote-support/`, outside the application bundle. Missing
state means OFF, including at boot. Do not remove the RustDesk gate while
uninstalling the application: that could restore RustDesk's normal boot start.
A future package removal action must stop RustDesk before removing the gate.

Verify the target Ubuntu image with OFF and ON across reboot, an upgrade in
each state, and OFF during an active support session. Watch actions with:

```bash
journalctl -f -u plproject-remote-support.service -u rustdesk.service
```
