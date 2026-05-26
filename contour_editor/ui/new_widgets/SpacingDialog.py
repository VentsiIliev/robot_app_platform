import sys
from PyQt6.QtWidgets import (
    QApplication, QDialog, QVBoxLayout, QLabel,
    QPushButton, QHBoxLayout
)
from PyQt6.QtCore import QTimer, Qt, QSize
from PyQt6.QtGui import QFont
import qtawesome as qta

from ...persistence.providers.widget_provider import WidgetProvider
from .styles import (
    PRIMARY_DARK, BORDER, ICON_COLOR, BG_COLOR,
    DIALOG_BUTTON_STYLE
)


class SpacingDialog(QDialog):
    def __init__(self, parent=None):
        super().__init__(parent)
        self.setWindowTitle("Spacing")
        self.spacing = 0

        self.setStyleSheet(f"""
            QDialog {{
                background-color: {BG_COLOR};
            }}
        """)

        layout = QVBoxLayout()
        layout.setSpacing(20)
        layout.setContentsMargins(24, 24, 24, 24)

        label = QLabel("Enter value in mm:")
        label.setFont(QFont("Arial", 11))
        label.setStyleSheet(f"color: {PRIMARY_DARK};")
        layout.addWidget(label)

        self.spin_box = WidgetProvider.get().create_spinbox(self)
        self.spin_box.setMinimum(0)
        self.spin_box.setMaximum(1000)
        self.spin_box.setValue(0)
        self.spin_box.setMinimumHeight(42)
        self.spin_box.setStyleSheet(f"""
            QSpinBox {{
                background-color: white;
                border: 1px solid {BORDER};
                border-radius: 6px;
                padding: 8px 12px;
                font-size: 12pt;
            }}
            QSpinBox:hover {{
                border: 1px solid {PRIMARY_DARK};
            }}
            QSpinBox:focus {{
                border: 2px solid {PRIMARY_DARK};
            }}
        """)
        layout.addWidget(self.spin_box)

        button_layout = QHBoxLayout()
        button_layout.setSpacing(12)

        ok_btn = QPushButton(self)
        ok_btn.setIcon(qta.icon("fa5s.check", color=ICON_COLOR))
        ok_btn.setIconSize(QSize(16, 16))
        ok_btn.setText(" OK")
        ok_btn.setFont(QFont("Arial", 11))
        ok_btn.setMinimumHeight(42)
        ok_btn.setCursor(Qt.CursorShape.PointingHandCursor)
        ok_btn.setStyleSheet(DIALOG_BUTTON_STYLE)
        ok_btn.clicked.connect(self.accept)

        cancel_btn = QPushButton(self)
        cancel_btn.setIcon(qta.icon("fa5s.times", color=ICON_COLOR))
        cancel_btn.setIconSize(QSize(16, 16))
        cancel_btn.setText(" Cancel")
        cancel_btn.setFont(QFont("Arial", 11))
        cancel_btn.setMinimumHeight(42)
        cancel_btn.setCursor(Qt.CursorShape.PointingHandCursor)
        cancel_btn.setStyleSheet(DIALOG_BUTTON_STYLE)
        cancel_btn.clicked.connect(self.reject)

        button_layout.addStretch()
        button_layout.addWidget(ok_btn)
        button_layout.addWidget(cancel_btn)

        layout.addLayout(button_layout)
        self.setLayout(layout)

        self.setMinimumWidth(400)

    def get_spacing(self):
        return self.spin_box.value()

    def showEvent(self, event):
        super().showEvent(event)
        # Delay the centering until the event loop processes pending events
        QTimer.singleShot(0, self.center_on_screen)

    def center_on_screen(self):
        screen = self.screen()
        if screen:
            screen_geometry = screen.geometry()
            # Use actual size, not sizeHint
            size = self.size()
            x = screen_geometry.x() + (screen_geometry.width() - size.width()) // 2
            y = screen_geometry.y() + (screen_geometry.height() - size.height()) // 2
            self.move(x, y)


if __name__ == "__main__":
    app = QApplication(sys.argv)
    dialog = SpacingDialog()
    if dialog.exec() == QDialog.DialogCode.Accepted:
        spacing = dialog.get_spacing()
        print("Spacing:", spacing)
    else:
        print("Cancelled")
