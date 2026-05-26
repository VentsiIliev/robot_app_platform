"""
Small overlay widget that appears when clicking on a segment line,
offering options to add either a control point or an anchor point.
Uses radial menu for selection.
"""

import qtawesome as qta
import math
from PyQt6.QtWidgets import QPushButton
from PyQt6.QtCore import Qt, pyqtSignal, QPoint, QSize
from PyQt6.QtGui import QPainter, QColor, QPen, QBrush
from ...tests.examples.radial_menu_demo import RadialMenu
from .styles import PRIMARY, PRIMARY_DARK, ICON_COLOR

class SegmentClickOverlay(RadialMenu):
    """Radial menu overlay for choosing what to add to a segment"""

    control_point_requested = pyqtSignal()
    anchor_point_requested = pyqtSignal()
    delete_segment_requested = pyqtSignal()
    disconnect_line_requested = pyqtSignal()
    def __init__(self, parent=None):
        # Initialize RadialMenu with empty tools - will create custom buttons
        super().__init__([], center_icon="", radius=70, parent=parent)

        # Hide the center button
        self.center_btn.hide()

        # Setup as a floating top-level overlay
        self.setWindowFlags(
            Qt.WindowType.Tool |
            Qt.WindowType.FramelessWindowHint |
            Qt.WindowType.WindowStaysOnTopHint
        )
        self.setAttribute(Qt.WidgetAttribute.WA_TranslucentBackground)

        # Make background transparent
        self.setStyleSheet("background-color: transparent;")

        # Reduce size for compact overlay
        self.resize(200, 200)

        # Create custom buttons with circle icons
        self._create_buttons()

        # Menu state
        self.menu_open = False

    def _create_buttons(self):
        """Create custom buttons for control point and anchor point"""
        # Control point button (hollow circle)
        self.control_btn = QPushButton(self)
        self.control_btn.setFixedSize(50, 50)
        self.control_btn.setToolTip("Add Control Point")
        self.control_btn.clicked.connect(self._on_control_point_clicked)
        # Make fully transparent so only the painted circle is visible
        self.control_btn.setFlat(True)
        self.control_btn.setStyleSheet("background: transparent; border: none;")
        self.control_btn.setFocusPolicy(Qt.FocusPolicy.NoFocus)
        self.control_btn.setCursor(Qt.CursorShape.PointingHandCursor)
        self.control_btn.hide()

        # Disconnect line button with modern purple theme
        self.disconnect_btn = QPushButton(self)
        self.disconnect_btn.setIcon(qta.icon("fa5s.unlink", color="white"))
        self.disconnect_btn.setIconSize(QSize(24, 24))
        self.disconnect_btn.setFixedSize(50, 50)
        self.disconnect_btn.setStyleSheet(f"""
            QPushButton {{
                background-color: {PRIMARY};
                color: white;
                border-radius: 25px;
                border: 2px solid white;
                font-family: Arial;
            }}
            QPushButton:hover {{
                background-color: {PRIMARY_DARK};
            }}
        """)
        self.disconnect_btn.setToolTip("Disconnect Line")
        self.disconnect_btn.clicked.connect(self.disconnect_line_requested.emit)
        self.disconnect_btn.hide()

        # Delete segment button with trash icon
        self.delete_btn = QPushButton(self)
        self.delete_btn.setIcon(qta.icon("fa5s.trash", color="white"))
        self.delete_btn.setIconSize(QSize(24, 24))
        self.delete_btn.setFixedSize(50, 50)
        self.delete_btn.setStyleSheet("""
            QPushButton {
                background-color: #FF5252;
                color: white;
                border-radius: 25px;
                border: 2px solid white;
                font-family: Arial;
            }
            QPushButton:hover {
                background-color: #FF6666;
            }
        """)
        self.delete_btn.setToolTip("Delete Segment")
        self.delete_btn.clicked.connect(self._on_delete_clicked)
        self.delete_btn.hide()
        # Anchor point button (filled circle)
        self.anchor_btn = QPushButton(self)
        self.anchor_btn.setFixedSize(50, 50)
        self.anchor_btn.setToolTip("Add Anchor Point")
        self.anchor_btn.clicked.connect(self._on_anchor_point_clicked)
        # Make fully transparent so only the painted circle is visible
        self.anchor_btn.setFlat(True)
        self.anchor_btn.setStyleSheet("background: transparent; border: none;")
        self.anchor_btn.setFocusPolicy(Qt.FocusPolicy.NoFocus)
        self.anchor_btn.setCursor(Qt.CursorShape.PointingHandCursor)
        self.anchor_btn.hide()

        # Cancel button (centered, not in radial arrangement)
        self.cancel_btn = QPushButton(self)
        self.cancel_btn.setIcon(qta.icon("fa5s.times", color="white"))
        self.cancel_btn.setIconSize(QSize(24, 24))
        self.cancel_btn.setFixedSize(50, 50)
        self.cancel_btn.setStyleSheet(f"""
            QPushButton {{
                background-color: {ICON_COLOR};
                color: white;
                border-radius: 25px;
                border: 2px solid white;
                font-family: Arial;
            }}
            QPushButton:hover {{
                background-color: {PRIMARY_DARK};
            }}
        """)
        self.cancel_btn.setToolTip("Cancel (ESC)")
        self.cancel_btn.clicked.connect(self._on_cancel_clicked)
        self.cancel_btn.hide()

        # Add to tool buttons list for radial positioning (only control and anchor)
        self.tool_buttons = [self.control_btn, self.anchor_btn,self.delete_btn,self.disconnect_btn]

    def _on_delete_clicked(self):
        """Handle delete button click"""
        self.delete_segment_requested.emit()
        self.hide()

    def _on_control_point_clicked(self):
        """Handle control point button click"""
        self.control_point_requested.emit()
        self.hide()

    def _on_anchor_point_clicked(self):
        """Handle anchor point button click"""
        self.anchor_point_requested.emit()
        self.hide()

    def _on_cancel_clicked(self):
        """Handle cancel button click"""
        self.hide()

    def paintEvent(self, event):
        """Custom paint event to draw circle icons on buttons"""
        super().paintEvent(event)

        painter = QPainter(self)
        painter.setRenderHint(QPainter.RenderHint.Antialiasing)

        # Draw hollow circle on control button
        if self.control_btn.isVisible():
            rect = self.control_btn.geometry()
            center_x = rect.center().x()
            center_y = rect.center().y()

            # Background circle (50x50) with purple theme
            painter.setPen(Qt.PenStyle.NoPen)
            painter.setBrush(QBrush(QColor(PRIMARY)))
            painter.drawEllipse(center_x - 25, center_y - 25, 50, 50)

            # Hollow circle (white border, transparent inside)
            painter.setPen(QPen(QColor("white"), 4))
            painter.setBrush(Qt.BrushStyle.NoBrush)
            painter.drawEllipse(center_x - 12, center_y - 12, 24, 24)

        # Draw filled circle on anchor button
        if self.anchor_btn.isVisible():
            rect = self.anchor_btn.geometry()
            center_x = rect.center().x()
            center_y = rect.center().y()

            # Background circle (50x50) with purple theme
            painter.setPen(Qt.PenStyle.NoPen)
            painter.setBrush(QBrush(QColor(PRIMARY)))
            painter.drawEllipse(center_x - 25, center_y - 25, 50, 50)

            # Filled circle
            painter.setBrush(QBrush(QColor("white")))
            painter.drawEllipse(center_x - 12, center_y - 12, 24, 24)

        painter.end()

    def show_at(self, global_pos: QPoint):
        """Show the radial overlay centered at the click position"""
        # Center the widget on the click position
        center_offset = QPoint(self.width() // 2, self.height() // 2)
        self.move(global_pos - center_offset)

        # Show the widget
        self.show()
        self.raise_()
        self.activateWindow()

        # Automatically show tools immediately
        if not self.menu_open:
            self._show_tools_immediately()

    def _show_tools_immediately(self):
        """Show tools without animation, directly positioned"""
        self.menu_open = True
        center_x, center_y = self.width() // 2, self.height() // 2
        count = len(self.tool_buttons)

        if count == 0:
            return

        angle_step = 360 / count

        # Position radial buttons (control and anchor)
        for i, btn in enumerate(self.tool_buttons):
            btn.show()
            angle_deg = i * angle_step - 90  # Start from top
            angle_rad = math.radians(angle_deg)
            target_x = center_x + self.radius * math.cos(angle_rad) - btn.width() / 2
            target_y = center_y + self.radius * math.sin(angle_rad) - btn.height() / 2

            # Set geometry directly (no animation)
            btn.setGeometry(int(target_x), int(target_y), btn.width(), btn.height())

        # Position cancel button at the center
        self.cancel_btn.show()
        cancel_x = center_x - self.cancel_btn.width() / 2
        cancel_y = center_y - self.cancel_btn.height() / 2
        self.cancel_btn.setGeometry(int(cancel_x), int(cancel_y), self.cancel_btn.width(), self.cancel_btn.height())

    def keyPressEvent(self, event):
        """Handle key press events - close on Esc"""
        if event.key() == Qt.Key.Key_Escape:
            self.hide()
            event.accept()
        else:
            super().keyPressEvent(event)

    def hideEvent(self, event):
        """Reset menu state when hiding"""
        self.menu_open = False
        for btn in self.tool_buttons:
            btn.hide()
        self.cancel_btn.hide()
        super().hideEvent(event)
