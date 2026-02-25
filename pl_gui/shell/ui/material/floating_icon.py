from PyQt6.QtCore import Qt, pyqtSignal, QSize
from PyQt6.QtWidgets import QGraphicsDropShadowEffect, QPushButton
from PyQt6.QtGui import QColor

from pl_gui.shell.ui.styles import (
    PRIMARY, PRIMARY_DARK, PRIMARY_HOVER, SHADOW_FAB,
)
from .animation import AnimationManager


class FloatingFolderIcon(QPushButton):
    """Material Design floating action button for folder icon"""

    clicked_signal = pyqtSignal()

    def __init__(self, folder_name, parent=None):
        super().__init__(parent)
        self.folder_name = folder_name
        self.setFixedSize(80, 80)  # Material Design FAB size
        self.animation_manager = AnimationManager(self)
        self.setup_ui()

    def setup_ui(self):
        """Setup Material Design floating action button"""
        self.setStyleSheet(f"""
            QPushButton {{
                background: {PRIMARY};
                border: none;
                border-radius: 40px;
                font-size: 20px;
                font-weight: 500;
                color: white;
                font-family: 'Roboto', 'Segoe UI', sans-serif;
                padding: 12px;
            }}
            QPushButton:hover {{
                background: {PRIMARY_HOVER};
                transform: scale(1.05);
            }}
            QPushButton:pressed {{
                background: {PRIMARY_DARK};
                transform: scale(0.95);
            }}
        """)

        self.setText("\u2630")

        self.setToolTip(f"Open {self.folder_name} folder")

        # Material Design elevation shadow
        try:
            shadow = QGraphicsDropShadowEffect()
            shadow.setBlurRadius(24)
            shadow.setColor(QColor(*SHADOW_FAB))
            shadow.setOffset(0, 8)
            self.setGraphicsEffect(shadow)
        except Exception as e:
            print(f"Shadow effect failed: {e}")

        self.clicked.connect(self.clicked_signal.emit)

    def show_with_animation(self):
        """Material Design scale-in animation"""
        self.animation_manager.create_floating_icon_show_animation()

    def hide_with_animation(self):
        """Material Design scale-out animation"""
        self.animation_manager.create_floating_icon_hide_animation(
            callback=lambda: None
        )
