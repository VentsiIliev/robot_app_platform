import qtawesome as qta
from PyQt6.QtCore import Qt, QSize
from PyQt6.QtWidgets import (
    QWidget, QHBoxLayout, QPushButton, QLabel
)
from PyQt6.QtGui import QFont

from ..styles import PRIMARY, PRIMARY_DARK, BORDER, ICON_COLOR


class IndentedWidget(QWidget):
    """Widget with configurable left indentation"""

    def __init__(self, content_widget, indent_level=0, indent_size=20):
        super().__init__()

        layout = QHBoxLayout(self)
        layout.setContentsMargins(indent_level * indent_size, 0, 0, 0)
        layout.setSpacing(0)

        layout.addWidget(content_widget)
        layout.addStretch()


class ExpandableLayerWidget(QWidget):
    """Layer widget with expand/collapse functionality"""

    def __init__(self, layer_name, layer_buttons_widget, on_expand_toggle):
        super().__init__()

        self.layer_name = layer_name
        self.on_expand_toggle = on_expand_toggle
        self.is_expanded = True

        layout = QHBoxLayout(self)
        layout.setContentsMargins(4, 4, 4, 4)
        layout.setSpacing(8)

        # Modern expand/collapse button with qtawesome icon
        self.expand_btn = QPushButton()
        self.expand_btn.setIcon(qta.icon("fa5s.chevron-down", color=ICON_COLOR))
        self.expand_btn.setIconSize(QSize(16, 16))
        self.expand_btn.setFixedSize(40, 56)
        self.expand_btn.setCursor(Qt.CursorShape.PointingHandCursor)
        self.expand_btn.setStyleSheet(f"""
            QPushButton {{
                background: white;
                border: 1px solid {BORDER};
                border-radius: 8px;
            }}
            QPushButton:hover {{
                border: 1px solid {PRIMARY};
                background-color: rgba(122,90,248,0.05);
            }}
            QPushButton:pressed {{
                background-color: rgba(122,90,248,0.10);
            }}
        """)
        self.expand_btn.clicked.connect(self._toggle_expansion)
        layout.addWidget(self.expand_btn, alignment=Qt.AlignmentFlag.AlignVCenter)

        # Layer buttons widget
        layout.addWidget(layer_buttons_widget, alignment=Qt.AlignmentFlag.AlignVCenter)

    def _toggle_expansion(self):
        self.is_expanded = not self.is_expanded
        icon_name = "fa5s.chevron-down" if self.is_expanded else "fa5s.chevron-right"
        self.expand_btn.setIcon(qta.icon(icon_name, color=ICON_COLOR))
        if self.on_expand_toggle:
            self.on_expand_toggle(self.layer_name, self.is_expanded)

    def set_expanded(self, expanded):
        self.is_expanded = expanded
        icon_name = "fa5s.chevron-down" if expanded else "fa5s.chevron-right"
        self.expand_btn.setIcon(qta.icon(icon_name, color=ICON_COLOR))


class ExpandableSegmentWidget(QWidget):
    """Segment widget with expand/collapse functionality"""

    def __init__(self, seg_index, segment_buttons_widget, on_expand_toggle):
        super().__init__()

        self.seg_index = seg_index
        self.on_expand_toggle = on_expand_toggle
        self.is_expanded = True

        layout = QHBoxLayout(self)
        layout.setContentsMargins(4, 6, 4, 6)  # Add vertical margins (top/bottom = 6px)
        layout.setSpacing(8)
        layout.setAlignment(Qt.AlignmentFlag.AlignVCenter)

        # Modern expand/collapse button with qtawesome icon
        self.expand_btn = QPushButton()
        self.expand_btn.setIcon(qta.icon("fa5s.chevron-down", color=ICON_COLOR))
        self.expand_btn.setIconSize(QSize(16, 16))
        self.expand_btn.setFixedSize(40, 40)
        self.expand_btn.setCursor(Qt.CursorShape.PointingHandCursor)
        self.expand_btn.setStyleSheet(f"""
            QPushButton {{
                background: white;
                border: 1px solid {BORDER};
                border-radius: 8px;
            }}
            QPushButton:hover {{
                border: 1px solid {PRIMARY};
                background-color: rgba(122,90,248,0.05);
            }}
            QPushButton:pressed {{
                background-color: rgba(122,90,248,0.10);
            }}
        """)
        self.expand_btn.clicked.connect(self._toggle_expansion)
        layout.addWidget(self.expand_btn)

        # Segment buttons widget
        layout.addWidget(segment_buttons_widget)

    def _toggle_expansion(self):
        self.is_expanded = not self.is_expanded
        icon_name = "fa5s.chevron-down" if self.is_expanded else "fa5s.chevron-right"
        self.expand_btn.setIcon(qta.icon(icon_name, color=ICON_COLOR))
        if self.on_expand_toggle:
            self.on_expand_toggle(self.seg_index, self.is_expanded)

    def set_expanded(self, expanded):
        self.is_expanded = expanded
        icon_name = "fa5s.chevron-down" if expanded else "fa5s.chevron-right"
        self.expand_btn.setIcon(qta.icon(icon_name, color=ICON_COLOR))


class PointWidget(QWidget):
    """Widget for displaying point information"""

    def __init__(self, point_label, coordinates):
        super().__init__()

        layout = QHBoxLayout(self)
        layout.setContentsMargins(8, 8, 8, 8)  # Increased vertical margins from 4 to 8
        layout.setSpacing(12)

        # Point label with modern styling
        label = QLabel(point_label)
        label.setFont(QFont("Arial", 11, QFont.Weight.Bold))

        # Use purple theme colors instead of hardcoded blue/orange
        if point_label.startswith("P"):
            # Anchor points - use primary purple
            label.setStyleSheet(f"color: {PRIMARY};")
        else:
            # Control points - use darker purple
            label.setStyleSheet(f"color: {PRIMARY_DARK};")

        label.setFixedWidth(45)
        layout.addWidget(label)

        # Coordinates with modern styling - use PRIMARY_DARK for better visibility
        coords_label = QLabel(coordinates)
        coords_label.setFont(QFont("Arial", 11))  # Increased from 10 to 11 for better readability
        coords_label.setStyleSheet(f"color: {PRIMARY_DARK}; font-weight: 500;")  # Changed from ICON_COLOR to PRIMARY_DARK
        layout.addWidget(coords_label)

        layout.addStretch()
