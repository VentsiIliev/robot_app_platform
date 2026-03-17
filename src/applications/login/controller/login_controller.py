from src.applications.login.model.login_model import LoginModel


class LoginController:

    def __init__(self, model: LoginModel, view) -> None:
        self._model = model
        self._view  = view

    def load(self) -> None:
        self._view.login_submitted.connect(self._on_login_submitted)
        self._view.qr_login_requested.connect(self._on_qr_login_requested)
        self._view.first_admin_submitted.connect(self._on_first_admin_submitted)
        self._model.move_to_login_pos()
        if self._model.is_first_run():
            self._view.show_first_run()
        else:
            self._view.show_login()

    # ── Slots ────────────────────────────────────────────────────────────────

    def _on_login_submitted(self, user_id: str, password: str) -> None:
        error = self._model.validate_login_input(user_id, password)
        if error:
            self._view.show_error(error)
            return
        user = self._model.authenticate(user_id, password)
        if user is None:
            self._view.show_error("Invalid credentials. Please try again.")
            return
        self._view.accept_login(user)

    def _on_qr_login_requested(self, qr_payload: str) -> None:
        user = self._model.authenticate_qr(qr_payload)
        if user is None:
            self._view.show_error("QR login failed. Please try again.")
            return
        self._view.accept_login(user)

    def _on_first_admin_submitted(
        self, user_id: str, first_name: str, last_name: str, password: str
    ) -> None:
        ok, msg = self._model.create_first_admin(user_id, first_name, last_name, password)
        if not ok:
            self._view.show_error(msg)
            return
        user = self._model.authenticate(user_id, password)
        if user is None:
            self._view.show_error("Admin created but login failed. Please retry.")
            return
        self._view.accept_login(user)
