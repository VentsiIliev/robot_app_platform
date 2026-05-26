import qtawesome as qta
from PyQt6.QtCore import Qt, QSize
from PyQt6.QtGui import QFont
from PyQt6.QtWidgets import QWidget, QHBoxLayout, QSizePolicy, QPushButton, QLabel

from .styles import (
    PRIMARY, ICON_COLOR, BORDER,
    NORMAL_STYLE, ACTIVE_STYLE
)



class LayerButtonsWidget(QWidget):
    def __init__(self, layer_name, layer_item, on_visibility_toggle, on_add_segment, on_lock_toggle, is_locked=False):
        super().__init__()

        self.layer_name = layer_name
        self.layer_item = layer_item
        self.on_visibility_toggle = on_visibility_toggle
        self.on_add_segment = on_add_segment
        self.on_lock_toggle = on_lock_toggle
        self.is_locked = is_locked
        self.is_visible = True

        self.setStyleSheet(f"""
            QWidget {{
                background: white;
                border: 1px solid {BORDER};
                border-radius: 8px;
            }}
        """)
        self.setFixedHeight(56)

        layout = QHBoxLayout(self)
        layout.setContentsMargins(12, 4, 12, 4)
        layout.setSpacing(10)
        layout.setAlignment(Qt.AlignmentFlag.AlignVCenter)

        # Layer name label
        self.layer_name_label = QLabel(layer_name)
        self.layer_name_label.setFont(QFont("Arial", 11, QFont.Weight.Bold))
        self.layer_name_label.setSizePolicy(QSizePolicy.Policy.Expanding, QSizePolicy.Policy.Fixed)
        self.layer_name_label.setStyleSheet(f"""
            QLabel {{
                color: {PRIMARY};
                background: transparent;
                padding-left: 8px;
            }}
        """)
        layout.addWidget(self.layer_name_label)

        # Visibility Button
        self.visibility_btn = QPushButton()
        self.visibility_btn.setIcon(qta.icon("fa5s.eye", color=ICON_COLOR))
        self.visibility_btn.setCheckable(True)
        self.visibility_btn.setChecked(True)
        self.visibility_btn.setIconSize(QSize(20, 20))
        self.visibility_btn.setFixedSize(48, 48)
        self.visibility_btn.setToolTip(f"Toggle {layer_name} visibility")
        self.visibility_btn.setCursor(Qt.CursorShape.PointingHandCursor)
        self.visibility_btn.setStyleSheet(NORMAL_STYLE)
        self.visibility_btn.clicked.connect(self._handle_visibility_toggle)
        layout.addWidget(self.visibility_btn)

        # Add Segment Button
        self.add_segment_btn = QPushButton()
        self.add_segment_btn.setIcon(qta.icon("fa5s.plus", color=ICON_COLOR))
        self.add_segment_btn.setIconSize(QSize(20, 20))
        self.add_segment_btn.setFixedSize(48, 48)
        self.add_segment_btn.setToolTip(f"Add new segment to {layer_name}")
        self.add_segment_btn.setCursor(Qt.CursorShape.PointingHandCursor)
        self.add_segment_btn.setStyleSheet(NORMAL_STYLE)
        self.add_segment_btn.clicked.connect(self._handle_add_segment)
        layout.addWidget(self.add_segment_btn)

        # Lock Button
        self.lock_btn = QPushButton()
        self.lock_btn.setCheckable(True)
        self.lock_btn.setChecked(is_locked)
        lock_icon = "fa5s.lock" if is_locked else "fa5s.lock-open"
        self.lock_btn.setIcon(qta.icon(lock_icon, color=ICON_COLOR))
        self.lock_btn.setIconSize(QSize(20, 20))
        self.lock_btn.setFixedSize(48, 48)
        self.lock_btn.setToolTip(f"Lock/unlock {layer_name}")
        self.lock_btn.setCursor(Qt.CursorShape.PointingHandCursor)
        self.lock_btn.setStyleSheet(NORMAL_STYLE)
        self.lock_btn.clicked.connect(self._handle_lock_toggle)
        layout.addWidget(self.lock_btn)

    def _handle_visibility_toggle(self):
        self.is_visible = self.visibility_btn.isChecked()

        if self.is_visible:
            self.visibility_btn.setIcon(qta.icon("fa5s.eye", color=ICON_COLOR))
            self.visibility_btn.setStyleSheet(NORMAL_STYLE)
        else:
            self.visibility_btn.setIcon(qta.icon("fa5s.eye-slash", color=ICON_COLOR))
            self.visibility_btn.setStyleSheet(ACTIVE_STYLE)

        if self.on_visibility_toggle:
            self.on_visibility_toggle(self.is_visible)

    def _handle_add_segment(self):
        if self.on_add_segment:
            self.on_add_segment()

    def _handle_lock_toggle(self):
        self.is_locked = self.lock_btn.isChecked()

        if self.is_locked:
            self.lock_btn.setIcon(qta.icon("fa5s.lock", color=ICON_COLOR))
            self.lock_btn.setStyleSheet(ACTIVE_STYLE)
        else:
            self.lock_btn.setIcon(qta.icon("fa5s.lock-open", color=ICON_COLOR))
            self.lock_btn.setStyleSheet(NORMAL_STYLE)

        if self.on_lock_toggle:
            self.on_lock_toggle(self.is_locked)



if __name__ == "__main__":
    from PyQt6.QtWidgets import QApplication
    app = QApplication([])

    def on_visibility_toggle(visible):
        print(f"Visibility toggled: {visible}")

    def on_add_segment():
        print("Add segment clicked")

    def on_lock_toggle(locked):
        print(f"Lock toggled: {locked}")

    widget = LayerButtonsWidget("Layer 1", None, on_visibility_toggle, on_add_segment, on_lock_toggle)
    widget.show()
    app.exec()