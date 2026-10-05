# Software Update

Shared MVC application using `ISoftwareUpdateService`. Its model has no Qt or
platform imports. Signed release checks and downloads run through BackgroundWorker;
the controller stops workers on cleanup. The screen supports English/Bulgarian
initial translation and runtime language switching.

Paint, Glue, Welding and Twin wire it into Administration with an administrator permission
policy and a process-state gate. Installation is queued only when the main process
is idle/stopped, then applied outside the GUI after normal shutdown by the independent
launcher. Each target uses its own config and feed. Twin refuses scheduling with an attached runtime until it exposes an idle-state contract; offline CLI installation remains available.

See [installation and operation](../../../packaging/platform/README.md).

Check for updates remains available when updates are disabled or configuration
is missing. Clicking it reports the configuration problem in the screen status.
Checks run in the background and the button is disabled while an operation runs.
Download remains disabled until updates are enabled; installation requires a
staged release and the existing production-state gate.

The same screen supports absolute local release directories for trusted testing,
or signed HTTPS feeds for remote updates. Both paths preserve machine data and
validate release identity/checksums before staging. See the local-feed example in
the packaging guide.

Every explicitly requested check presents its completed result in an information
dialog (new version or up to date), or a critical dialog when the check fails.
The status line retains the same result. Request/completion/failure logs help
diagnose signal or worker issues. Frozen self-tests exercise the Check button and
background result callback without hardware or interactive dialogs.
