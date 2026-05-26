import qtawesome as qta

from PyQt6.QtCore import pyqtSignal, QSize, Qt
from PyQt6.QtWidgets import QWidget, QHBoxLayout, QPushButton, QSizePolicy, QApplication

from .styles import (
    PRIMARY, ICON_COLOR,
    BUTTON_SIZE, ICON_SIZE, NORMAL_STYLE, ACTIVE_STYLE
)


class BottomToolBar(QWidget):

    zoom_in_requested = pyqtSignal()
    zoom_out_requested = pyqtSignal()
    reset_zoom_requested = pyqtSignal()
    pan_mode_toggle_requested = pyqtSignal()
    hide_points_requested = pyqtSignal()
    show_points_requested = pyqtSignal()

    def __init__(self, parent=None):
        super().__init__(parent)

        self.is_drag_mode = False
        self.points_visible = True

        self.setupUI()

    # ==================================================

    def setupUI(self):
        layout = QHBoxLayout(self)
        layout.setContentsMargins(16, 12, 16, 12)
        layout.setSpacing(16)

        self.setFixedHeight(90)

        # === Buttons ===
        self.hide_points_button = self.create_button(
            "fa5s.circle",
            self.toggle_points_visibility
        )

        self.zoom_out_button = self.create_button(
            "fa5s.search-minus",
            self.zoom_out_requested.emit
        )

        self.reset_zoom_button = self.create_button(
            "fa5s.expand",
            self.reset_zoom_requested.emit
        )

        self.zoom_in_button = self.create_button(
            "fa5s.search-plus",
            self.zoom_in_requested.emit
        )

        self.pan_toggle_button = self.create_button(
            "fa5s.mouse-pointer",
            self.toggle_pan_mode
        )

        for btn in [
            self.hide_points_button,
            self.zoom_out_button,
            self.reset_zoom_button,
            self.zoom_in_button,
            self.pan_toggle_button
        ]:
            layout.addWidget(btn)

        self.setLayout(layout)

    # ==================================================

    def create_button(self, icon_name, handler):
        btn = QPushButton()
        btn.icon_name = icon_name

        btn.setIcon(qta.icon(icon_name, color=ICON_COLOR))
        btn.setIconSize(QSize(ICON_SIZE, ICON_SIZE))
        btn.setFixedSize(BUTTON_SIZE, BUTTON_SIZE)
        btn.setCursor(Qt.CursorShape.PointingHandCursor)
        btn.setSizePolicy(QSizePolicy.Policy.Fixed, QSizePolicy.Policy.Fixed)
        btn.setStyleSheet(NORMAL_STYLE)

        btn.clicked.connect(handler)

        return btn

    # ==================================================
    # PAN TOGGLE
    # ==================================================

    def toggle_pan_mode(self):
        self.is_drag_mode = not self.is_drag_mode

        if self.is_drag_mode:
            self.pan_toggle_button.setStyleSheet(ACTIVE_STYLE)
            self.pan_toggle_button.setIcon(
                qta.icon("fa5s.hand-paper", color=PRIMARY)
            )
        else:
            self.pan_toggle_button.setStyleSheet(NORMAL_STYLE)
            self.pan_toggle_button.setIcon(
                qta.icon("fa5s.mouse-pointer", color=ICON_COLOR)
            )

        self.pan_mode_toggle_requested.emit()

    # ==================================================
    # HIDE / SHOW POINTS
    # ==================================================

    def toggle_points_visibility(self):
        self.points_visible = not self.points_visible

        if self.points_visible:
            self.hide_points_button.setStyleSheet(NORMAL_STYLE)
            self.hide_points_button.setIcon(
                qta.icon("fa5s.circle", color=ICON_COLOR)
            )
            self.hide_points_requested.emit()
        else:
            self.hide_points_button.setStyleSheet(ACTIVE_STYLE)
            self.hide_points_button.setIcon(
                qta.icon("fa5s.slash", color=PRIMARY)
            )
            self.show_points_requested.emit()

if __name__ == "__main__":
    import sys
    app = QApplication(sys.argv)
    window = BottomToolBar()

    window.zoom_in_requested.connect(lambda: print("🔍+ Zoom in"))
    window.zoom_out_requested.connect(lambda: print("🔍- Zoom out"))
    window.reset_zoom_requested.connect(lambda: print("🔍⌂ Reset zoom"))
    window.pan_mode_toggle_requested.connect(lambda: print(f"🖐️ Pan mode: {window.is_drag_mode}"))
    window.hide_points_requested.connect(lambda: print("👁️‍🗨️ Hide points"))
    window.show_points_requested.connect(lambda: print("👁️ Show points"))

    window.setWindowTitle("BottomToolBar Demo")
    window.show()
    sys.exit(app.exec())
