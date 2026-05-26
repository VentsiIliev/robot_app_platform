from PyQt6.QtCore import pyqtSignal
from PyQt6.QtWidgets import QWidget, QVBoxLayout
from .point_manager_coordinator import PointManagerCoordinator

from ..styles import PRIMARY, PRIMARY_DARK, BORDER, BG_COLOR


class PointManagerWidget(QWidget):
    """
    Backward-compatible wrapper around PointManagerCoordinator.
    Maintains the same API for existing code while using the refactored components.
    """
    point_selected_signal = pyqtSignal(dict)

    def __init__(self, contour_editor=None, parent=None):
        super().__init__()
        # Set up layout
        self.setLayout(QVBoxLayout())
        self.layout().setContentsMargins(0, 0, 0, 0)
        self.layout().setSpacing(0)
        # Apply modern styling matching other new_widgets
        self.setStyleSheet(f"""
            QWidget {{
                font-size: 11pt;
                font-family: Arial;
                background-color: {BG_COLOR};
            }}
            QPushButton:hover {{
                border: 1px solid {PRIMARY};
                background-color: rgba(122,90,248,0.05);
            }}
            QPushButton:pressed {{
                background-color: rgba(122,90,248,0.10);
            }}
            QComboBox {{
                background-color: white;
                color: #000000;
                border: 1px solid {BORDER};
                border-radius: 6px;
                padding: 6px 10px;
                min-height: 36px;
                font-size: 10pt;
            }}
            QComboBox:hover {{
                border: 1px solid {PRIMARY};
            }}
            QComboBox::drop-down {{
                border: none;
                padding-right: 8px;
            }}
            QComboBox QAbstractItemView {{
                background: white;
                color: #000000;
                border: 1px solid {BORDER};
                selection-background-color: rgba(122,90,248,0.15);
                selection-color: {PRIMARY_DARK};
            }}
            QListWidget {{
                outline: none;
                border: 1px solid {BORDER};
                background-color: white;
                border-radius: 8px;
            }}
            QListWidget::item {{
                border: none;
                padding: 8px;
                margin: 2px;
                border-radius: 6px;
            }}
            QListWidget::item:selected {{
                background-color: rgba(122,90,248,0.15);
                border: 1px solid {PRIMARY};
                color: {PRIMARY_DARK};
            }}
            QListWidget::item:hover {{
                background-color: rgba(122,90,248,0.05);
            }}
        """)
        # Create the coordinator which does all the work
        self.coordinator = PointManagerCoordinator(contour_editor, parent)
        self.layout().addWidget(self.coordinator)
        # Forward signals
        self.coordinator.point_selected_signal.connect(self.point_selected_signal.emit)

    # --- Public API (delegate to coordinator) ---
    def refresh_points(self):
        """Refresh the points display in the list"""
        self.coordinator.refresh_points()

    def update_all_segments_settings(self, settings):
        """Apply settings to all segments (called by GlobalSettingsDialog)"""
        self.coordinator.update_all_segments_settings(settings)

    def get_current_selected_layer(self):
        """Get the currently selected layer name"""
        return self.coordinator.get_current_selected_layer()
