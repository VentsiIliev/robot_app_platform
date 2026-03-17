from PyQt6.QtCore import QObject, pyqtSignal, QCoreApplication

from src.applications.user_management.model.permissions_model import PermissionsModel


def _t(text: str) -> str:
    translated = QCoreApplication.translate("UserManagement", text)
    return translated or text


class _Bridge(QObject):
    retranslate = pyqtSignal()


class PermissionsController:
    """Wires PermissionsModel to the App Permissions tab view.

    The view must expose:
      - set_permissions(app_ids, role_values, permissions)  — populate table
      - set_notice(text)                                    — show deferral notice
      - permission_toggled signal(app_id, role_value, allowed)
    """

    def __init__(self, model: PermissionsModel, view, messaging=None) -> None:
        self._model     = model
        self._view      = view
        self._messaging = messaging
        self._bridge    = _Bridge()
        self._bridge.retranslate.connect(self._retranslate)

    def load(self) -> None:
        self._view.permission_toggled.connect(self._on_permission_toggled)
        if self._messaging:
            from src.shared_contracts.events.localization_events import LocalizationTopics
            self._messaging.subscribe(LocalizationTopics.LANGUAGE_CHANGED, self._on_language_changed_raw)
        self._view.set_notice(_t("Changes apply at next login."))
        self._refresh()

    def stop(self) -> None:
        if self._messaging:
            from src.shared_contracts.events.localization_events import LocalizationTopics
            self._messaging.unsubscribe(LocalizationTopics.LANGUAGE_CHANGED, self._on_language_changed_raw)

    # ── private ────────────────────────────────────────────────────────────────

    def _on_language_changed_raw(self, _payload) -> None:
        self._bridge.retranslate.emit()

    def _retranslate(self) -> None:
        self._view.retranslateUi()
        self._view.set_notice(_t("Changes apply at next login."))

    def _on_permission_toggled(self, app_id: str, role_value: str, allowed: bool) -> None:
        self._model.set_permission(app_id, role_value, allowed)
        self._refresh()

    def _refresh(self) -> None:
        self._view.set_permissions(
            app_ids     = self._model.get_known_app_ids(),
            role_values = self._model.get_role_values(),
            permissions = self._model.get_permissions(),
        )
