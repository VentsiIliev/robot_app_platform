from PyQt6.QtCore import pyqtSignal, Qt
from PyQt6.QtWidgets import QWidget

from pl_gui.shell.ui.styles import OVERLAY_BG
from .animation import AnimationManager


class FolderOverlay(QWidget):
    """Overlay widget that appears when folder is opened"""

    mouse_pressed_outside = pyqtSignal()

    def __init__(self, parent=None):
        super().__init__(parent)
        self.setStyleSheet(f"background-color: {OVERLAY_BG};")
        self.setAttribute(Qt.WidgetAttribute.WA_TranslucentBackground)
        self.animation_manager = AnimationManager(self)

    def fade_in(self):
        """Animate overlay appearance"""
        self.animation_manager.fade_in(
            start_opacity=0.0,
            end_opacity=1.0
        )

    def fade_out(self):
        """Animate overlay disappearance"""
        self.animation_manager.fade_out(
            hide_on_finish=True
        )

    def mousePressEvent(self, event):
        """Close folder when clicking outside"""
        self.mouse_pressed_outside.emit()
