from src.applications.base.background_worker import BackgroundWorker
from src.applications.base.i_application_controller import IApplicationController


class SoftwareUpdateController(IApplicationController, BackgroundWorker):
    def __init__(self, model, view):
        BackgroundWorker.__init__(self)
        self._model = model
        self._view = view
        self._stopped = False
        self._busy = False
        self._checking = False
        self._details = {}
        view.check_requested.connect(self._check)
        view.download_requested.connect(self._download)
        view.install_requested.connect(self._install)

    def load(self):
        try:
            self._details = self._model.load()
            self._view.set_details(self._details)
            self._actions()
            result = self._details.get("result", {})
            if result.get("status") == "failed":
                self._view.set_error(result.get("message", ""))
            elif result.get("status") == "recovered":
                self._view.set_status("An interrupted update was recovered.")
            elif result.get("status") == "rolled_back":
                self._view.set_status("Version {version} was restored", version=result["version"])
            elif result.get("status") == "installed":
                self._view.set_status("Version {version} was installed", version=result["version"])
        except Exception as exc:
            self._view.set_error(str(exc))
            self._view.set_actions(False, False, False)

    def stop(self):
        self._stopped = True
        self._stop_threads()

    def _actions(self):
        self._view.set_actions(self._busy, self._details.get("enabled", False), bool(self._details.get("staged")))

    def _run(self, function, callback, status, checking=False):
        if self._busy or self._stopped:
            return
        self._busy = True
        self._checking = checking
        self._actions()
        self._view.set_status(status)
        self._run_in_thread(function, callback, self._failed)

    def _check(self):
        self._logger.info("Check for updates requested")
        self._run(self._model.check, self._checked, "Checking for updates…", checking=True)

    def _download(self):
        self._run(self._model.download, self._downloaded, "Downloading and verifying update…")

    def _install(self):
        # Scheduling checks process state on the GUI thread; activation happens outside Qt.
        if self._busy or self._stopped:
            return
        try:
            self._model.save()
            self._view.set_status("Update scheduled. Close the application normally to install it.")
        except Exception as exc:
            self._view.set_error(str(exc))

    def _checked(self, result):
        if self._stopped:
            return
        self._busy = False
        self._actions()
        self._view.set_status("Version {version} is available" if result["available"] else "The platform is up to date", version=result["version"])
        self._logger.info("Update check completed: version=%s available=%s", result["version"], result["available"])
        self._view.show_check_result()

    def _downloaded(self, result):
        if self._stopped:
            return
        self._busy = False
        self.load()
        self._view.set_status("Version {version} is ready to install", version=result["version"])

    def _failed(self, message):
        if self._stopped:
            return
        self._busy = False
        self._actions()
        self._view.set_error(message)
        self._logger.warning("Update operation failed: %s", message)
        if self._checking:
            self._view.show_check_result(error=True)
