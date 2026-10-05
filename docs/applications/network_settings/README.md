# Network Settings

`NetworkSettings` is a shared application for host Wi-Fi, Ethernet, and IPv4
settings. Paint, Glue, Welding, and Twin systems register it in their Service
or Setup folder. The standalone `scripts/network_connect.py` launches the same
application; `src/applications/network_settings/example_usage.py` uses an
in-memory stub and does not change host networking.

The application follows the platform MVC flow: view signals → controller →
model → `INetworkSettingsService`. `NetworkSettingsService` selects the Linux
NetworkManager (`nmcli`) or Windows (`netsh`) backend extracted from the
original script. All scans and network changes run through `BackgroundWorker`
threads. The service validates IPv4 values before invoking OS commands.

The Wi-Fi page scans, connects, disconnects, forgets saved profiles, and edits
IPv4 settings for the active connection. The Wired page lists interfaces,
connects or disconnects them, and edits their IPv4 settings. Applying IPv4
settings can briefly interrupt connectivity because the OS backend reactivates
the connection.

The Remote Support page uses the shared switch to show the saved customer
choice and actual state of `rustdesk.service`. It communicates only with the
local Unix socket `/run/plproject/remote-support.sock`; the app never invokes
privileged commands. The socket-activated root helper accepts only `status`,
`enable`, and `disable` requests for that one unit. If saved choice and actual
service state differ, the UI reports that action is needed. The helper lives in
`src/engine/remote_support/` because it is shared platform infrastructure.
If the controller cannot be reached, the Remote Support card shows the error
and disables the switch. Opening the tab requests a fresh state and restores
the switch after a successful response.
Worker completion is delivered through a Qt relay on the UI thread and native
thread teardown is joined before releasing worker references, preventing a
startup freeze when the remote status request finishes immediately.

The installer and systemd units are under `packaging/remote_support/`. Install
them on each Ubuntu robot with
`sudo packaging/remote_support/install.sh ROBOT_UI_USER`, where
`ROBOT_UI_USER` is the account running the HMI. First
installation defaults to OFF and stops RustDesk; reinstalling preserves the
existing choice. The root-owned marker at
`/var/lib/plproject/remote-support/enabled` stores ON. A drop-in condition on
`rustdesk.service` prevents startup when that marker is absent, including at
boot. The socket is owned by the HMI account with mode `0600`; ERP and Android
clients cannot call it directly.

After installation, check OFF across a reboot, then test ON, OFF during an
active session, and a RustDesk package update on the target Ubuntu image.
