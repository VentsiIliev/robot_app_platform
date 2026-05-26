import qtawesome as qta

from PyQt6.QtCore import pyqtSignal, Qt, QTimer, QSize
from PyQt6.QtWidgets import (
    QWidget, QHBoxLayout, QPushButton, QSizePolicy
)

from .styles import (
    PRIMARY, BORDER, ICON_COLOR, TOPBAR_BG, GROUP_BG,
    BUTTON_SIZE, ICON_SIZE, NORMAL_STYLE, PRIMARY_STYLE, ACTIVE_STYLE
)


class TopBarWidget(QWidget):

    capture_requested = pyqtSignal()
    save_requested = pyqtSignal()
    start_requested = pyqtSignal()
    undo_requested = pyqtSignal()
    redo_requested = pyqtSignal()
    preview_requested = pyqtSignal()
    multi_select_mode_requested = pyqtSignal()
    remove_points_requested = pyqtSignal()
    settings_requested = pyqtSignal()
    tools_requested = pyqtSignal()
    generate_pattern_requested = pyqtSignal()

    def __init__(self):
        super().__init__()

        self.setMinimumHeight(88)
        self.setStyleSheet(f"""
            QWidget {{
                background-color: {TOPBAR_BG};
                border-bottom: 1px solid {BORDER};
            }}
        """)

        main_layout = QHBoxLayout(self)
        main_layout.setContentsMargins(20, 8, 20, 8)
        main_layout.setSpacing(40)

        # ================= LEFT GROUP =================
        left_group = self.create_group()

        self.undo_button = self.create_icon_button("fa5s.undo", self.undo_requested.emit)
        self.redo_button = self.create_icon_button("fa5s.redo", self.redo_requested.emit)

        left_group.layout().addWidget(self.undo_button)
        left_group.layout().addWidget(self.redo_button)

        # ================= CENTER GROUP =================
        center_group = self.create_group()

        self.tools_button = self.create_icon_button("fa5s.tools", self.tools_requested.emit)
        self.settings_button = self.create_icon_button("fa5s.cog", self.settings_requested.emit)
        self.capture_button = self.create_icon_button("fa5s.camera", self.capture_requested.emit)
        self.remove_button = self.create_icon_button("fa5s.trash", None)

        self.pickup_button = self.create_icon_button("fa5s.mouse-pointer", None)
        self.pickup_button.setCheckable(True)
        self.pickup_button.toggled.connect(
            lambda checked: self.update_toggle_style(
                self.pickup_button,
                checked,
                "fa5s.mouse-pointer"
            )
        )

        self.preview_button = self.create_icon_button("fa5s.eye", self.preview_requested.emit)

        self.generate_button = self.create_icon_button(
            "fa5s.project-diagram",
            self.generate_pattern_requested.emit
        )

        for btn in [
            self.tools_button,
            self.settings_button,
            self.capture_button,
            self.remove_button,
            self.pickup_button,
            self.preview_button,
            self.generate_button
        ]:
            center_group.layout().addWidget(btn)

        # ================= RIGHT GROUP =================
        right_group = self.create_group()

        self.start_button = self.create_icon_button(
            "fa5s.play",
            self.start_requested.emit,
            primary=True
        )

        self.save_button = self.create_icon_button(
            "fa5s.save",
            self.save_requested.emit
        )

        right_group.layout().addWidget(self.start_button)
        right_group.layout().addWidget(self.save_button)

        # ================= ASSEMBLY =================
        main_layout.addWidget(left_group)
        main_layout.addStretch()
        main_layout.addWidget(center_group)
        main_layout.addStretch()
        main_layout.addWidget(right_group)

        self.setup_remove_button_long_press()

        self.buttons = [
            self.undo_button,
            self.redo_button,
            self.tools_button,
            self.settings_button,
            self.capture_button,
            self.remove_button,
            self.pickup_button,
            self.preview_button,
            self.generate_button,
            self.start_button,
            self.save_button
        ]

    # ==================================================

    def create_group(self):
        group = QWidget()
        group.setStyleSheet(f"""
            QWidget {{
                background: {GROUP_BG};
                border-radius: 14px;
            }}
        """)
        layout = QHBoxLayout(group)
        layout.setContentsMargins(14, 10, 14, 10)
        layout.setSpacing(14)
        return group

    def create_icon_button(self, icon_name, handler=None, primary=False):
        btn = QPushButton()

        icon_color = "white" if primary else ICON_COLOR
        btn.setIcon(qta.icon(icon_name, color=icon_color))

        btn.setIconSize(QSize(ICON_SIZE, ICON_SIZE))
        btn.setFixedSize(BUTTON_SIZE, BUTTON_SIZE)
        btn.setCursor(Qt.CursorShape.PointingHandCursor)
        btn.setSizePolicy(QSizePolicy.Policy.Fixed, QSizePolicy.Policy.Fixed)

        btn.setStyleSheet(PRIMARY_STYLE if primary else NORMAL_STYLE)

        if handler:
            btn.clicked.connect(handler)

        return btn

    def update_toggle_style(self, button, checked, icon_name):
        if checked:
            button.setStyleSheet(ACTIVE_STYLE)
            button.setIcon(qta.icon(icon_name, color=PRIMARY))
        else:
            button.setStyleSheet(NORMAL_STYLE)
            button.setIcon(qta.icon(icon_name, color=ICON_COLOR))

    # ==================================================
    # Long Press Remove
    # ==================================================

    def setup_remove_button_long_press(self):
        self.long_press_timer = QTimer()
        self.long_press_timer.setSingleShot(True)
        self.long_press_timer.timeout.connect(
            lambda: self.multi_select_mode_requested.emit()
        )

        self.remove_button.mousePressEvent = self.remove_press
        self.remove_button.mouseReleaseEvent = self.remove_release

    def remove_press(self, event):
        if event.button() == Qt.MouseButton.LeftButton:
            self.long_press_timer.start(800)
            QPushButton.mousePressEvent(self.remove_button, event)

    def remove_release(self, event):
        if event.button() == Qt.MouseButton.LeftButton:
            if self.long_press_timer.isActive():
                self.long_press_timer.stop()
                self.remove_points_requested.emit()
            QPushButton.mouseReleaseEvent(self.remove_button, event)
