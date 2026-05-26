import qtawesome as qta
from types import SimpleNamespace

from PyQt6.QtCore import Qt, QSize, QTimer, QPoint
from PyQt6.QtGui import QFont
from PyQt6.QtWidgets import (
    QApplication, QWidget, QHBoxLayout,
    QPushButton, QSizePolicy, QMenu
)

from .styles import PRIMARY, PRIMARY_DARK, BORDER, ICON_COLOR, NORMAL_STYLE, ACTIVE_STYLE


class LayerSelectionPopup(QMenu):
    """Custom popup menu for layer selection"""

    def __init__(self, current_layer, layer_options, on_layer_change, parent=None):
        super().__init__(parent)
        self.on_layer_change = on_layer_change
        self.current_layer = current_layer
        self.layer_options = list(layer_options)

        # Modern purple theme styling
        self.setStyleSheet(f"""
            QMenu {{
                background-color: white;
                border: 2px solid {PRIMARY};
                border-radius: 8px;
                padding: 8px;
                font-size: 11pt;
                font-family: Arial;
            }}
            QMenu::item {{
                padding: 10px 24px;
                margin: 2px;
                border-radius: 6px;
                color: {ICON_COLOR};
            }}
            QMenu::item:selected {{
                background-color: rgba(122,90,248,0.15);
                color: {PRIMARY_DARK};
            }}
            QMenu::item:pressed {{
                background-color: rgba(122,90,248,0.25);
            }}
        """)

        # ...existing code...

        # Add layer options
        for layer in self.layer_options:
            action = self.addAction(layer)
            action.triggered.connect(lambda checked, l=layer: self._on_layer_selected(l))

            # Mark current layer
            if layer == current_layer:
                action.setText(f"✓ {layer}")

    def _on_layer_selected(self, layer):
        if self.on_layer_change:
            self.on_layer_change(layer)

class PressAndHoldButton(QPushButton):
    """Custom button that supports press and hold functionality"""

    def __init__(self, text="", parent=None):
        super().__init__(text, parent)

        self.press_timer = QTimer()
        self.press_timer.timeout.connect(self._on_long_press)
        self.press_timer.setSingleShot(True)
        self.long_press_duration = 500  # milliseconds
        self.is_long_press = False

        # Callbacks
        self.on_click_callback = None
        self.on_long_press_callback = None

        # Apply modern styling
        self.setCursor(Qt.CursorShape.PointingHandCursor)
        self.setFont(QFont("Arial", 11, QFont.Weight.Bold))
        self.setStyleSheet(f"""
            QPushButton {{
                background: white;
                border: 1px solid {BORDER};
                border-radius: 8px;
                color: {PRIMARY};
            }}
            QPushButton:hover {{
                border: 1px solid {PRIMARY};
                background-color: rgba(122,90,248,0.05);
            }}
            QPushButton:pressed {{
                background-color: rgba(122,90,248,0.10);
            }}
        """)

    def set_click_callback(self, callback):
        """Set callback for normal click"""
        self.on_click_callback = callback

    def set_long_press_callback(self, callback):
        """Set callback for long press"""
        self.on_long_press_callback = callback

    def mousePressEvent(self, event):
        if event.button() == Qt.MouseButton.LeftButton:
            self.is_long_press = False
            self.press_timer.start(self.long_press_duration)
        super().mousePressEvent(event)

    def mouseReleaseEvent(self, event):
        if event.button() == Qt.MouseButton.LeftButton:
            self.press_timer.stop()

            if not self.is_long_press:
                # Normal click
                if self.on_click_callback:
                    self.on_click_callback()

        super().mouseReleaseEvent(event)

    def _on_long_press(self):
        """Handle long press event"""
        self.is_long_press = True
        if self.on_long_press_callback:
            self.on_long_press_callback()

class SegmentButtonsAndComboWidget(QWidget):
    def __init__(self, seg_index, segment, layer_name,
                 on_visibility, on_activate, on_delete, on_settings, on_layer_change, on_long_press,
                 layer_options=None):
        super().__init__()

        self.segment = segment
        self.on_visibility = on_visibility
        self.on_layer_change = on_layer_change
        self.seg_index = seg_index
        self.current_layer = layer_name
        self.layer_options = list(layer_options or ["Main", "Contour", "Fill"])

        layout = QHBoxLayout(self)
        layout.setContentsMargins(0, 0, 0, 0)
        layout.setSpacing(8)
        layout.setAlignment(Qt.AlignmentFlag.AlignLeft | Qt.AlignmentFlag.AlignVCenter)

        # Use custom press and hold button for index label
        self.index_label = PressAndHoldButton(f"S{seg_index}")
        self.index_label.setSizePolicy(QSizePolicy.Policy.Fixed, QSizePolicy.Policy.Fixed)
        self.index_label.setFixedHeight(48)
        self.index_label.setFixedWidth(48)
        self.index_label.setToolTip(
            f"Segment {seg_index} - Click to activate, Hold for layer options")

        # Set callbacks for press and hold
        self.index_label.set_click_callback(on_activate)
        self.index_label.set_long_press_callback(self._show_layer_popup)

        layout.addWidget(self.index_label)

        # Buttons with qtawesome icons
        self.visibility_btn = self._create_visibility_button()
        layout.addWidget(self.visibility_btn)

        self.delete_btn = self._create_icon_button(
            "fa5s.trash", "Delete this segment", on_delete
        )
        layout.addWidget(self.delete_btn)

        # Settings button with gear icon
        self.settings_btn = self._create_icon_button(
            "fa5s.cog", "Segment settings", on_settings
        )
        layout.addWidget(self.settings_btn)

        layout.addStretch()

    def _show_layer_popup(self):
        """Show layer selection popup on long press"""
        popup = LayerSelectionPopup(
            current_layer=self.current_layer,
            layer_options=self.layer_options,
            on_layer_change=self._handle_layer_change,
            parent=self
        )

        # Position popup near the button
        button_pos = self.index_label.mapToGlobal(QPoint(0, 0))
        popup_pos = QPoint(button_pos.x(), button_pos.y() + self.index_label.height() + 5)
        popup.exec(popup_pos)

    def _handle_layer_change(self, new_layer):
        """Handle layer change from popup"""
        self.current_layer = new_layer
        if self.on_layer_change:
            self.on_layer_change(new_layer)
        print(f"Layer changed to: {new_layer}")

    def update_layer(self, new_layer):
        """Update the current layer (call this from parent when layer changes)"""
        self.current_layer = new_layer

    def _create_icon_button(self, icon_name, tooltip, callback):
        """Create a button with qtawesome icon and modern styling"""
        button = QPushButton()
        button.setIcon(qta.icon(icon_name, color=ICON_COLOR))
        button.setIconSize(QSize(20, 20))
        button.setToolTip(tooltip)
        button.setFixedSize(48, 48)
        button.setCursor(Qt.CursorShape.PointingHandCursor)
        button.setStyleSheet(NORMAL_STYLE)
        button.clicked.connect(callback)
        return button

    def _create_visibility_button(self):
        """Create visibility toggle button with modern styling"""
        button = QPushButton()
        button.setCheckable(True)
        is_visible = getattr(self.segment, "visible", True)
        button.setChecked(is_visible)

        # Use eye icons from qtawesome
        icon_name = "fa5s.eye" if is_visible else "fa5s.eye-slash"
        button.setIcon(qta.icon(icon_name, color=ICON_COLOR))
        button.setIconSize(QSize(20, 20))
        button.setToolTip("Toggle segment visibility")
        button.setFixedSize(48, 48)
        button.setCursor(Qt.CursorShape.PointingHandCursor)
        button.setStyleSheet(NORMAL_STYLE)
        button.clicked.connect(lambda: self._toggle_visibility(button))
        return button

    def _toggle_visibility(self, button):
        """Toggle visibility icon and call callback"""
        is_visible = button.isChecked()
        icon_name = "fa5s.eye" if is_visible else "fa5s.eye-slash"
        button.setIcon(qta.icon(icon_name, color=ICON_COLOR))

        # Apply active style when hidden
        if is_visible:
            button.setStyleSheet(NORMAL_STYLE)
        else:
            button.setStyleSheet(ACTIVE_STYLE)

        self.on_visibility(button)


# --- Testing ---
if __name__ == "__main__":
    import sys
    app = QApplication(sys.argv)

    segment = SimpleNamespace(visible=True, is_active=False)
    layer_name = "Contour"


    def on_visibility(btn):
        print("Visibility toggled:", btn.isChecked())


    def on_activate():
        print("Activated")


    def on_delete():
        print("Deleted")


    def on_settings():
        print("Settings opened")


    def on_layer_change(value):
        print("Layer changed to:", value)


    def on_long_press():
        print(f"Long press detected!")



    widget = SegmentButtonsAndComboWidget(
        seg_index=0,
        segment=segment,
        layer_name=layer_name,
        on_visibility=on_visibility,
        on_activate=on_activate,
        on_delete=on_delete,
        on_settings=on_settings,
        on_layer_change=on_layer_change,
        on_long_press=on_long_press
    )
    widget.show()
    sys.exit(app.exec())
