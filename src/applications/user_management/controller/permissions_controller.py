from src.applications.user_management.model.permissions_model import PermissionsModel

_DEFERRAL_NOTICE = "Changes apply at next login."


class PermissionsController:
    """Wires PermissionsModel to the App Permissions tab view.

    The view must expose:
      - set_permissions(app_ids, role_values, permissions)  — populate table
      - set_notice(text)                                    — show deferral notice
      - permission_toggled signal(app_id, role_value, allowed)
    """

    def __init__(self, model: PermissionsModel, view) -> None:
        self._model = model
        self._view  = view

    def load(self) -> None:
        self._view.permission_toggled.connect(self._on_permission_toggled)
        self._view.set_notice(_DEFERRAL_NOTICE)
        self._refresh()

    def stop(self) -> None:
        pass

    # ── private ────────────────────────────────────────────────────────────────

    def _on_permission_toggled(self, app_id: str, role_value: str, allowed: bool) -> None:
        self._model.set_permission(app_id, role_value, allowed)
        self._refresh()

    def _refresh(self) -> None:
        self._view.set_permissions(
            app_ids     = self._model.get_known_app_ids(),
            role_values = self._model.get_role_values(),
            permissions = self._model.get_permissions(),
        )
