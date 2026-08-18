from __future__ import annotations

import logging
from collections.abc import Callable

from PyQt6.QtCore import QCoreApplication
from PyQt6.QtWidgets import QWidget

from pl_gui.shell.AppShell import AppShell
from pl_gui.shell.session_drawer_view import SessionDrawerView
from src.engine.auth.i_authenticated_user import IAuthenticatedUser
from src.engine.auth.i_session_service import ISessionService


class ShellSessionController:
    """Owns shell account-button, session drawer, and logout wiring."""

    def __init__(
        self,
        *,
        shell: AppShell,
        session: ISessionService,
        dev_skip_login: bool,
        show_account_button_when_dev_skip_login: bool,
        show_login_view: Callable[[], None],
        can_close_running_apps: Callable[[], bool],
    ) -> None:
        self._shell = shell
        self._session = session
        self._dev_skip_login = dev_skip_login
        self._show_account_button_when_dev_skip_login = show_account_button_when_dev_skip_login
        self._show_login_view = show_login_view
        self._can_close_running_apps = can_close_running_apps
        self._logger = logging.getLogger(self.__class__.__name__)

        self._drawer = SessionDrawerView(shell)

    def start(self) -> None:
        self._shell.header.user_account_clicked.connect(self._toggle_drawer)
        self._drawer.logout_requested.connect(self._on_logout_requested)
        self._shell.header.language_selector.languageChanged.connect(self.retranslateUi)
        self.retranslateUi()
        self.refresh_account_button()

    def login(self, user: IAuthenticatedUser) -> None:
        self._session.login(user)
        self.refresh_account_button()

    def refresh_account_button(self) -> None:
        visible = self._session.is_authenticated() and (
            not self._dev_skip_login or self._show_account_button_when_dev_skip_login
        )
        self._shell.header.userAccountButton.setVisible(visible)

    def _toggle_drawer(self) -> None:
        self._refresh_drawer()
        self._drawer.position_below(self._shell.stacked_widget)
        self._drawer.toggle()

    def _refresh_drawer(self) -> None:
        user = self._session.current_user
        self._drawer.set_logout_enabled(self._session.is_authenticated() and not self._dev_skip_login)
        if user is None:
            self._drawer.set_logged_out()
            return

        payload = self._payload(user)
        self._drawer.set_session_info(
            name=self._display_name(user, payload),
            user_id=str(getattr(user, "user_id", "-")),
            role=self._role_text(user),
            email=str(payload.get("email") or "-"),
        )

    def _on_logout_requested(self) -> None:
        if self._dev_skip_login or not self._session.is_authenticated():
            return
        if not self._can_close_running_apps():
            self._logger.info("Logout blocked by an application can_close() veto")
            return

        self._shell.close_all_apps()
        self._session.logout()
        self.refresh_account_button()
        self._shell._app_descriptors = []
        self._shell._widget_factory = lambda _: QWidget()
        self._shell.create_folders_page()
        if self._drawer.is_open:
            self._drawer.toggle()
        self._show_login_view()

    @staticmethod
    def _role_text(user: IAuthenticatedUser) -> str:
        role = getattr(user, "role", None)
        return str(getattr(role, "value", role) or "-")

    @staticmethod
    def _payload(user: IAuthenticatedUser) -> dict:
        record = getattr(user, "record", None)
        payload = getattr(record, "payload", None)
        return payload if isinstance(payload, dict) else {}

    @staticmethod
    def _display_name(user: IAuthenticatedUser, payload: dict) -> str:
        parts = [
            str(payload.get("firstName") or "").strip(),
            str(payload.get("lastName") or "").strip(),
        ]
        name = " ".join(part for part in parts if part)
        return name or f"User {getattr(user, 'user_id', '-')}"

    def retranslateUi(self, *_) -> None:
        self._shell.header.userAccountButton.setToolTip(self._t("Session"))
        self._drawer.retranslateUi()

    @staticmethod
    def _t(text: str) -> str:
        translated = QCoreApplication.translate("SessionDrawer", text)
        return translated or text
