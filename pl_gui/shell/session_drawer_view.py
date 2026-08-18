from __future__ import annotations

from PyQt6.QtCore import QCoreApplication, QEvent, QPoint, Qt, pyqtSignal
from PyQt6.QtWidgets import QLabel, QPushButton, QVBoxLayout, QWidget

from pl_gui.shell.ui.styles import PRIMARY, PRIMARY_DARK
from pl_gui.utils.utils_widgets.Drawer import Drawer


class SessionDrawerView(Drawer):
    """Generic shell drawer for displaying session details."""

    logout_requested = pyqtSignal()

    def __init__(self, parent: QWidget) -> None:
        super().__init__(parent, side="right")
        self.setObjectName("SessionDrawer")
        self.setAttribute(Qt.WidgetAttribute.WA_StyledBackground, True)
        self.setFixedWidth(360)
        self._labels: dict[str, QLabel] = {}
        self._field_labels: dict[str, QLabel] = {}
        self._logged_out = True

        self._setup_ui()
        self.retranslateUi()
        self.hide()

    def set_logged_out(self) -> None:
        self._logged_out = True
        self._labels["name"].setText(self._t("Not logged in"))
        self._labels["user_id"].setText("-")
        self._labels["role"].setText("-")
        self._labels["email"].setText("-")

    def set_session_info(self, *, name: str, user_id: str, role: str, email: str) -> None:
        self._logged_out = False
        self._labels["name"].setText(name or self._t("Not logged in"))
        self._labels["user_id"].setText(user_id or "-")
        self._labels["role"].setText(role or "-")
        self._labels["email"].setText(email or "-")

    def set_logout_enabled(self, enabled: bool) -> None:
        self._logout_btn.setEnabled(enabled)

    def position_below(self, anchor: QWidget) -> None:
        self.heightOffset = anchor.mapTo(self.parent(), QPoint(0, 0)).y()
        self.resize_to_parent_height()

    def _setup_ui(self) -> None:
        self.setStyleSheet(f"""
            QWidget {{
                background-color: #FFFFFF;
                color: #202124;
            }}
            QWidget#SessionDrawer {{
                border-left: 1px solid #E0E0E0;
            }}
            QLabel#DrawerTitle {{
                font-size: 18pt;
                font-weight: bold;
                padding-bottom: 8px;
            }}
            QLabel#DrawerLabel {{
                color: #5F6368;
                font-size: 10pt;
            }}
            QLabel#DrawerValue {{
                font-size: 13pt;
                font-weight: bold;
            }}
            QPushButton#LogoutButton {{
                background-color: {PRIMARY};
                color: white;
                border: none;
                border-radius: 8px;
                font-size: 11pt;
                font-weight: bold;
                min-height: 44px;
                padding: 0 16px;
            }}
            QPushButton#LogoutButton:hover {{
                background-color: {PRIMARY_DARK};
            }}
            QPushButton#LogoutButton:pressed {{
                background-color: {PRIMARY_DARK};
            }}
            QPushButton#LogoutButton:disabled {{
                background-color: #E0E0E0;
                color: #777777;
            }}
        """)

        layout = QVBoxLayout(self)
        layout.setContentsMargins(24, 24, 24, 24)
        layout.setSpacing(16)

        self._title = QLabel()
        self._title.setObjectName("DrawerTitle")
        layout.addWidget(self._title)

        for key, label_text in (
            ("name", "Name"),
            ("user_id", "User ID"),
            ("role", "Role"),
            ("email", "Email"),
        ):
            label = QLabel()
            label.setObjectName("DrawerLabel")
            value = QLabel("-")
            value.setObjectName("DrawerValue")
            value.setWordWrap(True)
            layout.addWidget(label)
            layout.addWidget(value)
            self._field_labels[key] = label
            self._labels[key] = value

        layout.addStretch(1)

        self._logout_btn = QPushButton()
        self._logout_btn.setObjectName("LogoutButton")
        self._logout_btn.setCursor(Qt.CursorShape.PointingHandCursor)
        self._logout_btn.clicked.connect(self._on_logout_clicked)
        layout.addWidget(self._logout_btn)

    def _on_logout_clicked(self, checked: bool = False) -> None:
        self.logout_requested.emit()

    def retranslateUi(self) -> None:
        self._title.setText(self._t("Session"))
        self._field_labels["name"].setText(self._t("Name"))
        self._field_labels["user_id"].setText(self._t("User ID"))
        self._field_labels["role"].setText(self._t("Role"))
        self._field_labels["email"].setText(self._t("Email"))
        self._logout_btn.setText(self._t("Logout"))
        if self._logged_out:
            self._labels["name"].setText(self._t("Not logged in"))

    def changeEvent(self, event) -> None:
        if event.type() == QEvent.Type.LanguageChange:
            self.retranslateUi()
        super().changeEvent(event)

    @staticmethod
    def _t(text: str) -> str:
        translated = QCoreApplication.translate("SessionDrawer", text)
        return translated or text
