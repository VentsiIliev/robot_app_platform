from typing import Optional

from PyQt6.QtCore import QObject, pyqtSignal, QCoreApplication

from src.applications.login.model.login_model import LoginModel
from src.engine.core.i_messaging_service import IMessagingService
from src.shared_contracts.events.vision_events import VisionTopics


class _Bridge(QObject):
    """Safely delivers camera frames from the broker thread to the Qt thread."""
    camera_frame = pyqtSignal(object)


class LoginController:

    def __init__(
        self,
        model: LoginModel,
        view,
        messaging: Optional[IMessagingService] = None,
    ) -> None:
        self._model     = model
        self._view      = view
        self._messaging = messaging
        self._bridge    = _Bridge()
        self._bridge.camera_frame.connect(self._on_camera_frame)

    def load(self) -> None:
        self._view.setup_confirmed.connect(self._on_setup_confirmed)
        self._view.login_submitted.connect(self._on_login_submitted)
        self._view.qr_scan_requested.connect(self._on_qr_scan_requested)
        self._view.qr_tab_activated.connect(self._on_qr_tab_activated)
        self._view.first_admin_submitted.connect(self._on_first_admin_submitted)

        if self._messaging:
            self._messaging.subscribe(
                VisionTopics.LATEST_IMAGE, self._on_camera_frame_raw
            )

        self._view.show_setup()

    # ── Camera frame delivery ────────────────────────────────────────────────

    @staticmethod
    def _t(text: str) -> str:
        translated = QCoreApplication.translate("Login", text)
        return translated or text

    def _on_camera_frame_raw(self, msg) -> None:
        """Broker thread — must not touch Qt. Forward via bridge signal."""
        frame = msg.get("image") if isinstance(msg, dict) else msg
        if frame is not None:
            self._bridge.camera_frame.emit(frame)

    def _on_camera_frame(self, frame) -> None:
        """Qt thread — safe to update the view."""
        self._view.update_camera_frame(frame)

    # ── Navigation slots ─────────────────────────────────────────────────────

    def _on_setup_confirmed(self) -> None:
        if self._model.is_first_run():
            self._view.show_first_run()
        else:
            self._view.show_login()

    # ── Login slots ──────────────────────────────────────────────────────────

    def _on_login_submitted(self, user_id: str, password: str) -> None:
        error = self._model.validate_login_input(user_id, password)
        if error:
            self._view.show_error(self._t(error))
            return
        user = self._model.authenticate(user_id, password)
        if user is None:
            self._view.show_error(self._t("Invalid credentials. Please try again."))
            return
        self._view.accept_login(user)

    def _on_qr_tab_activated(self) -> None:
        self._model.move_to_login_pos()

    def _on_qr_scan_requested(self) -> None:
        result = self._model.try_qr_login()
        if result is None:
            return
        user_id, password = result
        user = self._model.authenticate(user_id, password)
        if user is None:
            self._view.show_error(self._t("QR login failed. Please try again."))
            return
        self._view.stop_qr_scanning()
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
            self._view.show_error(self._t("Admin created but login failed. Please retry."))
            return
        self._view.accept_login(user)
