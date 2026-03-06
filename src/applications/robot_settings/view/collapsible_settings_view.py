from typing import List

from PyQt6.QtCore import pyqtSignal, Qt
from PyQt6.QtWidgets import (
    QFrame, QPushButton, QScrollArea,
    QSizePolicy, QVBoxLayout, QWidget,
)

from pl_gui.settings.settings_view.group_widget import GenericSettingGroup
from pl_gui.settings.settings_view.schema import SettingGroup
from pl_gui.settings.settings_view.settings_view import SettingsView
from pl_gui.settings.settings_view.styles import BG_COLOR, BORDER, PRIMARY_DARK, PRIMARY_LIGHT


class CollapsibleGroup(QWidget):
    value_changed = pyqtSignal(str, object)

    def __init__(self, schema: SettingGroup, parent=None):
        super().__init__(parent)
        self._expanded = False
        self._title    = schema.title
        self.setSizePolicy(QSizePolicy.Policy.Expanding, QSizePolicy.Policy.Preferred)
        self.setStyleSheet("background: transparent;")

        outer = QVBoxLayout(self)
        outer.setContentsMargins(0, 0, 0, 0)
        outer.setSpacing(0)

        # ── Header ────────────────────────────────────────────────────
        self._header = QPushButton()
        self._header.setSizePolicy(QSizePolicy.Policy.Expanding, QSizePolicy.Policy.Fixed)
        self._header.setMinimumHeight(44)
        self._header.setCursor(Qt.CursorShape.PointingHandCursor)
        self._header.clicked.connect(self._toggle)
        outer.addWidget(self._header)
        self._refresh_header()

        # ── Body ──────────────────────────────────────────────────────
        self._body = QFrame()
        self._body.setObjectName("cgBody")
        self._body.setStyleSheet(f"""
            QFrame#cgBody {{
                background: white;
                border: 2px solid {BORDER};
                border-top: none;
                border-radius: 0 0 8px 8px;
            }}
        """)
        body_layout = QVBoxLayout(self._body)
        body_layout.setContentsMargins(4, 4, 4, 12)
        body_layout.setSpacing(0)

        self._inner = GenericSettingGroup(schema)
        self._inner.setTitle("")
        self._inner.setStyleSheet("""
            QGroupBox {
                border: none;
                margin-top: 0;
                padding-top: 8px;
                background: white;
            }
        """)
        self._inner.value_changed.connect(self.value_changed)
        body_layout.addWidget(self._inner)

        self._body.setVisible(False)
        outer.addWidget(self._body)

    def _refresh_header(self) -> None:
        arrow   = "▲" if self._expanded else "▼"
        radius  = "8px 8px 0 0" if self._expanded else "8px"
        self._header.setText(f"  {arrow}   {self._title}")
        self._header.setStyleSheet(f"""
            QPushButton {{
                background: {PRIMARY_LIGHT};
                color: {PRIMARY_DARK};
                border: 2px solid {BORDER};
                border-radius: {radius};
                text-align: left;
                padding-left: 12px;
                font-size: 11pt;
                font-weight: bold;
            }}
            QPushButton:hover {{ background: {BORDER}; }}
        """)

    def _toggle(self) -> None:
        self._expanded = not self._expanded
        self._body.setVisible(self._expanded)
        self._refresh_header()

    # ── duck-typed to match GenericSettingGroup ───────────────────────

    def set_values(self, flat: dict) -> None:
        self._inner.set_values(flat)

    def get_values(self) -> dict:
        return self._inner.get_values()


class CollapsibleSettingsView(SettingsView):

    def add_tab(self, title: str, groups: List[SettingGroup]) -> None:
        content = QWidget()
        content.setStyleSheet(f"background: {BG_COLOR};")
        layout = QVBoxLayout(content)
        layout.setContentsMargins(16, 16, 16, 16)
        layout.setSpacing(10)

        for schema in groups:
            widget = CollapsibleGroup(schema)
            widget.value_changed.connect(
                lambda k, v: self.value_changed_signal.emit(k, v, self._component_name)
            )
            self._groups.append(widget)
            layout.addWidget(widget)

        layout.addStretch()

        scroll = QScrollArea()
        scroll.setWidgetResizable(True)
        scroll.setStyleSheet("QScrollArea { border: none; background: transparent; }")
        scroll.setWidget(content)
        self._tabs.addTab(scroll, title)