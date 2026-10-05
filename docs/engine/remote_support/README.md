# Remote support controller

`src/engine/remote_support/controller.py` is a standalone Python process run
by the systemd unit in `packaging/remote_support/`. It has no Qt or
robot-system-specific dependencies. The shared Network Settings application
uses an unprivileged Unix socket client and never executes `systemctl` itself.

The controller accepts only `status`, `enable`, and `disable` requests for the
fixed `rustdesk.service` unit. The systemd socket is accessible only to the
configured HMI user. The root-owned marker at
`/var/lib/plproject/remote-support/enabled` stores the desired ON state; a
RustDesk unit drop-in checks the marker before startup. On failed enable, the
controller removes the marker and stops the service. On disable, it removes
the marker before stopping the service so OFF remains in effect after reboot.

Install with `sudo packaging/remote_support/install.sh ROBOT_UI_USER`. First
installation stops RustDesk and defaults to OFF. Test the target image for
OFF after reboot, ON after reboot, and OFF during an active session.

Paint builds include a standalone controller installation payload, staged by
`packaging/remote_support/build_payload.py`. See its packaged README for the
product installer contract and RustDesk provisioning prerequisites. Startup
checks verify the service remains active after a short settling interval.
