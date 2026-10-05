from functools import partial

from PyQt6.QtCore import QCoreApplication, QTimer

from src.applications.base.background_worker import BackgroundWorker
from src.applications.base.i_application_controller import IApplicationController
from src.applications.network_settings.model.network_settings_model import NetworkSettingsModel
from src.applications.network_settings.view.network_settings_view import NetworkSettingsView


class NetworkSettingsController(IApplicationController, BackgroundWorker):
    def __init__(self, model: NetworkSettingsModel, view: NetworkSettingsView) -> None:
        BackgroundWorker.__init__(self)
        self._model = model
        self._view = view
        self._stopped = False
        self._busy = {"wifi": False, "wired": False, "remote": False}
        self._remote_timer = QTimer(view)
        self._remote_timer.setInterval(3000)
        self._remote_timer.timeout.connect(self._refresh_remote_if_visible)
        view.refresh_wifi_requested.connect(self._refresh_wifi)
        view.refresh_wired_requested.connect(self._refresh_wired)
        view.connect_wifi_requested.connect(self._connect_wifi)
        view.disconnect_wifi_requested.connect(self._disconnect_wifi)
        view.forget_wifi_requested.connect(self._forget_wifi)
        view.connect_wired_requested.connect(self._connect_wired)
        view.disconnect_wired_requested.connect(self._disconnect_wired)
        view.wifi_ipv4_requested.connect(self._edit_wifi_ipv4)
        view.wired_ipv4_requested.connect(self._edit_wired_ipv4)
        view.remote_support_requested.connect(self._set_remote_support)
        view.remote_support_refresh_requested.connect(self._refresh_remote_support)

    def load(self) -> None:
        self._model.load()
        QTimer.singleShot(0, self._refresh_all)
        self._remote_timer.start()

    def stop(self) -> None:
        self._stopped = True
        self._remote_timer.stop()
        self._stop_threads()

    def _refresh_remote_if_visible(self) -> None:
        if self._view.is_remote_support_visible():
            self._refresh_remote_support()

    @staticmethod
    def _t(source: str) -> str:
        return QCoreApplication.translate("NetworkSettingsController", source) or source

    def _refresh_all(self) -> None:
        if not self._stopped:
            self._refresh_wifi()
            self._refresh_wired()
            self._refresh_remote_support()

    def _refresh_remote_support(self) -> None:
        if self._stopped or self._busy["remote"]:
            return
        self._set_busy("remote", True)
        self._run_in_thread(
            self._model.get_remote_support_status,
            self._remote_support_loaded,
            partial(self._on_error, "remote"),
        )

    def _remote_support_loaded(self, status: dict) -> None:
        if self._stopped:
            return
        self._view.set_remote_support_status(status)
        self._set_busy("remote", False)

    def _set_remote_support(self, enabled: bool) -> None:
        if self._stopped or self._busy["remote"]:
            return
        self._set_busy("remote", True)
        self._view.set_status(self._t("Starting remote support…" if enabled else "Stopping remote support…"))
        self._run_in_thread(
            partial(self._model.set_remote_support_enabled, enabled),
            self._remote_support_changed,
            self._on_remote_change_error,
        )

    def _on_remote_change_error(self, message: str) -> None:
        self._on_error("remote", message)
        self._refresh_remote_support()

    def _remote_support_changed(self, status: dict) -> None:
        if self._stopped:
            return
        self._remote_support_loaded(status)
        self._view.set_status(self._t("Remote support service updated"))

    def _refresh_wifi(self) -> None:
        if self._stopped or self._busy["wifi"]:
            return
        self._set_busy("wifi", True)
        self._view.set_status(self._t("Scanning Wi-Fi networks…"))
        self._run_in_thread(self._model.scan_wifi, self._wifi_loaded, partial(self._on_error, "wifi"))

    def _refresh_wired(self) -> None:
        if self._stopped or self._busy["wired"]:
            return
        self._set_busy("wired", True)
        self._run_in_thread(self._model.list_wired, self._wired_loaded, partial(self._on_error, "wired"))

    def _wifi_loaded(self, networks: list[dict]) -> None:
        if self._stopped:
            return
        self._view.set_wifi_networks(networks)
        self._set_busy("wifi", False)
        self._view.set_status(self._t("{count} Wi-Fi networks found").format(count=len(networks)))

    def _wired_loaded(self, devices: list[dict]) -> None:
        if self._stopped:
            return
        self._view.set_wired_devices(devices)
        self._set_busy("wired", False)
        self._view.set_status(self._t("{count} wired interfaces found").format(count=len(devices)))

    def _run_action(self, kind: str, fn, status: str) -> None:
        if self._stopped or self._busy[kind]:
            return
        self._set_busy(kind, True)
        self._view.set_status(self._t(status))
        self._run_in_thread(
            fn, partial(self._action_finished, kind), partial(self._on_error, kind)
        )

    def _action_finished(self, kind: str, _result) -> None:
        if self._stopped:
            return
        self._set_busy(kind, False)
        self._view.set_status(self._t("Network change completed"))
        self._refresh_all()

    def _on_error(self, kind: str, message: str) -> None:
        if self._stopped:
            return
        self._set_busy(kind, False)
        if kind == "remote":
            self._view.set_remote_support_error(message)
        self._view.set_error(message)

    def _connect_wifi(self, ssid: str, password: str, secure: bool) -> None:
        self._run_action(
            "wifi", partial(self._model.connect_wifi, ssid, password, secure),
            "Connecting to Wi-Fi…",
        )

    def _disconnect_wifi(self) -> None:
        self._run_action("wifi", self._model.disconnect_wifi, "Disconnecting Wi-Fi…")

    def _forget_wifi(self, ssid: str) -> None:
        self._run_action("wifi", partial(self._model.forget_wifi, ssid), "Forgetting Wi-Fi network…")

    def _connect_wired(self, device: str) -> None:
        self._run_action("wired", partial(self._model.connect_wired, device), "Connecting wired interface…")

    def _disconnect_wired(self, device: str) -> None:
        self._run_action("wired", partial(self._model.disconnect_wired, device), "Disconnecting wired interface…")

    def _edit_wifi_ipv4(self) -> None:
        self._load_ipv4("wifi", self._model.get_wifi_ipv4)

    def _edit_wired_ipv4(self, device: dict) -> None:
        self._load_ipv4("wired", partial(self._model.get_wired_ipv4, device))

    def _load_ipv4(self, kind: str, fn) -> None:
        if self._stopped or self._busy[kind]:
            return
        self._set_busy(kind, True)
        self._view.set_status(self._t("Loading IPv4 settings…"))
        self._run_in_thread(
            fn, partial(self._ipv4_loaded, kind), partial(self._on_error, kind)
        )

    def _ipv4_loaded(self, kind: str, result: dict) -> None:
        if self._stopped:
            return
        self._set_busy(kind, False)
        settings = self._view.edit_ipv4(result["settings"])
        if settings is not None:
            self._run_action(
                kind, partial(self._model.save, result["target"], settings),
                "Applying IPv4 settings…",
            )
        else:
            self._view.set_status(self._t("Ready"))

    def _set_busy(self, kind: str, busy: bool) -> None:
        self._busy[kind] = busy
        self._view.set_busy(kind, busy)
