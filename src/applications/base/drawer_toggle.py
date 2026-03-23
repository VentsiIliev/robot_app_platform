from PyQt6.QtCore import QObject, QPropertyAnimation, QEasingCurve, QPoint, QEvent, Qt
from PyQt6.QtWidgets import QFrame, QPushButton, QVBoxLayout

from pl_gui.settings.settings_view.styles import BG_COLOR, BORDER, PRIMARY, PRIMARY_DARK


class DrawerToggle(QObject):
    _BTN_W = 26
    _BTN_H = 64

    def __init__(self, parent_widget, side="right", width=300, height_offset=0):
        super().__init__(parent_widget)
        self._host = parent_widget
        self._side = side
        self._width = width
        self._height_offset = height_offset
        self._is_open = False

        self._panel = QFrame(parent_widget)
        self._panel.setFixedWidth(width)
        self._panel.setObjectName("DrawerPanel")
        self._panel.setStyleSheet(f"""
            QFrame#DrawerPanel {{
                background-color: {BG_COLOR};
                border-left: 2px solid {BORDER};
            }}
        """)
        self._content = QVBoxLayout(self._panel)
        self._content.setContentsMargins(8, 8, 8, 8)
        self._content.setSpacing(6)
        self._content.addStretch(1)

        self._btn = QPushButton(parent_widget)
        self._btn.setFixedSize(self._BTN_W, self._BTN_H)
        self._btn.setObjectName("DrawerToggleBtn")
        self._btn.setCursor(Qt.CursorShape.PointingHandCursor)
        self._btn.setStyleSheet(f"""
            QPushButton#DrawerToggleBtn {{
                background-color: {PRIMARY};
                border: none;
                border-radius: 4px;
                font-size: 13px;
                font-weight: bold;
                color: white;
            }}
            QPushButton#DrawerToggleBtn:hover {{ background-color: {PRIMARY_DARK}; }}
            QPushButton#DrawerToggleBtn:pressed {{ background-color: {PRIMARY_DARK}; }}
        """)
        self._btn.clicked.connect(self._on_toggle)

        self._anim = QPropertyAnimation(self._panel, b"pos")
        self._anim.setDuration(280)
        self._anim.setEasingCurve(QEasingCurve.Type.InOutCubic)
        self._anim.valueChanged.connect(self._follow_btn)
        self._anim.finished.connect(self._reposition)

        parent_widget.installEventFilter(self)
        self._update_arrow()
        self._reposition()

    def add_widget(self, widget):
        self._content.insertWidget(self._content.count() - 1, widget)

    def set_visible(self, visible: bool) -> None:
        if not visible:
            self._is_open = False
            self._anim.stop()
            self._panel.hide()
            self._btn.hide()
            return
        self._update_arrow()
        self._reposition()
        self._panel.hide()
        self._btn.show()

    def eventFilter(self, obj, event):
        if obj is self._host and event.type() == QEvent.Type.Resize:
            self._reposition()
        return False

    def _on_toggle(self):
        self._is_open = not self._is_open
        self._update_arrow()
        self._animate()

    def _animate(self):
        pw = self._host.width()
        h = max(1, self._host.height() - self._height_offset)
        self._panel.setFixedHeight(h)

        if self._side == "right":
            start_x = pw if self._is_open else pw - self._width
            end_x = pw - self._width if self._is_open else pw
        else:
            start_x = -self._width if self._is_open else 0
            end_x = 0 if self._is_open else -self._width

        self._anim.stop()
        self._anim.setStartValue(QPoint(start_x, self._height_offset))
        self._anim.setEndValue(QPoint(end_x, self._height_offset))
        self._panel.show()
        self._panel.raise_()
        self._btn.raise_()
        self._anim.start()

    def _follow_btn(self, pos: QPoint):
        h = max(1, self._host.height() - self._height_offset)
        btn_x = pos.x() - self._BTN_W if self._side == "right" else pos.x() + self._width
        btn_y = self._height_offset + (h - self._BTN_H) // 2
        self._btn.move(btn_x, btn_y)

    def _reposition(self):
        if self._host.height() == 0:
            return
        pw = self._host.width()
        h = max(1, self._host.height() - self._height_offset)
        self._panel.setFixedHeight(h)

        if self._side == "right":
            panel_x = pw - self._width if self._is_open else pw
            btn_x = panel_x - self._BTN_W
        else:
            panel_x = 0 if self._is_open else -self._width
            btn_x = panel_x + self._width

        btn_y = self._height_offset + (h - self._BTN_H) // 2
        self._panel.move(panel_x, self._height_offset)
        self._btn.move(btn_x, btn_y)
        self._panel.raise_()
        self._btn.raise_()

    def _update_arrow(self):
        if self._side == "right":
            self._btn.setText("▶" if self._is_open else "◀")
        else:
            self._btn.setText("◀" if self._is_open else "▶")
