"""
Settings dialog for customizing all constants from constants.py
Opens with Ctrl+S shortcut
Saves to JSON file instead of modifying constants.py
"""
import qtawesome as qta
from PyQt6.QtWidgets import (QDialog, QVBoxLayout, QHBoxLayout, QTabWidget,
                             QLabel, QCheckBox,
                             QPushButton, QWidget, QGridLayout, QGroupBox,
                             QColorDialog, QScrollArea, QComboBox, QSizeGrip)
from PyQt6.QtCore import Qt, QSize
from PyQt6.QtGui import QFont, QColor
from ...persistence.config.constants_manager import ConstantsManager

from .styles import (
    PRIMARY, BORDER, ICON_COLOR, BG_COLOR,
    DIALOG_BUTTON_STYLE, TAB_WIDGET_STYLE
)
from .touch_widgets import TouchSpinBox


class ColorButton(QPushButton):
    """Button that shows a color and opens a color picker when clicked"""

    def __init__(self, color, parent=None):
        super().__init__(parent)
        self.color = color
        self.setFixedSize(100, 36)
        self.setCursor(Qt.CursorShape.PointingHandCursor)
        self.update_color(color)
        self.clicked.connect(self.choose_color)

    def update_color(self, color):
        """Update the button's background color"""
        self.color = color
        self.setStyleSheet(f"""
            QPushButton {{
                background-color: rgba({color.red()}, {color.green()}, {color.blue()}, {color.alpha()});
                border: 2px solid {BORDER};
                border-radius: 8px;
            }}
            QPushButton:hover {{
                border: 2px solid {PRIMARY};
            }}
        """)

    def choose_color(self):
        """Open color picker dialog"""
        options = QColorDialog.ColorDialogOption.ShowAlphaChannel
        color = QColorDialog.getColor(self.color, self, "Choose Color", options)
        if color.isValid():
            self.update_color(color)

    def get_color(self):
        """Get the current color"""
        return self.color


class ConstantsSettingsDialog(QDialog):
    """Dialog for editing all constants from constants.py"""

    def __init__(self, parent=None):
        super().__init__(parent)
        self.setWindowTitle("Contour Editor Settings")
        self.setModal(False)
        self.setMinimumSize(800, 700)

        self.setStyleSheet(f"""
            QDialog {{
                background-color: {BG_COLOR};
            }}
        """)

        self.setWindowFlags(Qt.WindowType.Window)

        self.inputs = {}
        self._float_inputs = set()   # tracks which const_names are float fields

        main_layout = QVBoxLayout(self)
        main_layout.setSpacing(20)
        main_layout.setContentsMargins(24, 24, 24, 24)

        self.tabs = QTabWidget(self)
        self.tabs.setStyleSheet(TAB_WIDGET_STYLE)
        main_layout.addWidget(self.tabs)

        # Create tabs
        self._create_visualization_toggles_tab()
        self._create_axes_and_angles_tab()
        self._create_segment_length_tab()
        self._create_highlighted_line_tab()
        self._create_crosshair_tab()
        self._create_point_rendering_tab()
        self._create_overlays_tab()
        self._create_measurement_timing_tab()

        button_layout = QHBoxLayout()
        button_layout.setSpacing(12)

        self.reset_button = QPushButton(self)
        self.reset_button.setIcon(qta.icon("fa5s.undo-alt", color=ICON_COLOR))
        self.reset_button.setIconSize(QSize(16, 16))
        self.reset_button.setText(" Reset to Defaults")
        self.reset_button.setFont(QFont("Arial", 11))
        self.reset_button.setMinimumHeight(52)
        self.reset_button.setCursor(Qt.CursorShape.PointingHandCursor)
        self.reset_button.setStyleSheet(DIALOG_BUTTON_STYLE)
        self.reset_button.clicked.connect(self._on_reset_clicked)

        self.apply_button = QPushButton(self)
        self.apply_button.setIcon(qta.icon("fa5s.check", color=ICON_COLOR))
        self.apply_button.setIconSize(QSize(16, 16))
        self.apply_button.setText(" Apply")
        self.apply_button.setFont(QFont("Arial", 11))
        self.apply_button.setMinimumHeight(52)
        self.apply_button.setCursor(Qt.CursorShape.PointingHandCursor)
        self.apply_button.setStyleSheet(DIALOG_BUTTON_STYLE)
        self.apply_button.clicked.connect(self._on_apply_clicked)

        self.ok_button = QPushButton(self)
        self.ok_button.setIcon(qta.icon("fa5s.check-circle", color=ICON_COLOR))
        self.ok_button.setIconSize(QSize(16, 16))
        self.ok_button.setText(" OK")
        self.ok_button.setFont(QFont("Arial", 11))
        self.ok_button.setMinimumHeight(52)
        self.ok_button.setCursor(Qt.CursorShape.PointingHandCursor)
        self.ok_button.setStyleSheet(DIALOG_BUTTON_STYLE)
        self.ok_button.clicked.connect(self._on_ok_clicked)

        self.cancel_button = QPushButton(self)
        self.cancel_button.setIcon(qta.icon("fa5s.times", color=ICON_COLOR))
        self.cancel_button.setIconSize(QSize(16, 16))
        self.cancel_button.setText(" Cancel")
        self.cancel_button.setFont(QFont("Arial", 11))
        self.cancel_button.setMinimumHeight(52)
        self.cancel_button.setCursor(Qt.CursorShape.PointingHandCursor)
        self.cancel_button.setStyleSheet(DIALOG_BUTTON_STYLE)
        self.cancel_button.clicked.connect(self.reject)

        button_layout.addWidget(self.reset_button)
        button_layout.addStretch()
        button_layout.addWidget(self.apply_button)
        button_layout.addWidget(self.ok_button)
        button_layout.addWidget(self.cancel_button)

        main_layout.addLayout(button_layout)

        # Add custom resize handle at a bottom right corner with qtawesome icon
        self.resize_grip = QSizeGrip(self)
        self.resize_grip.setFixedSize(32, 32)
        self.resize_grip.setStyleSheet(f"""
            QSizeGrip {{
                background-color: transparent;
                border: none;
            }}
            QSizeGrip:hover {{
                background-color: rgba(122,90,248,0.1);
                border-radius: 4px;
            }}
        """)

        # Add qtawesome icon on top of the resize grip
        self.resize_icon = QLabel(self.resize_grip)
        self.resize_icon.setPixmap(
            qta.icon("fa5s.grip-lines", color=PRIMARY).pixmap(QSize(20, 20))
        )
        self.resize_icon.setAlignment(Qt.AlignmentFlag.AlignCenter)
        self.resize_icon.setGeometry(0, 0, 32, 32)
        self.resize_icon.setAttribute(Qt.WidgetAttribute.WA_TransparentForMouseEvents)  # Let clicks pass through

        # Position resize grip at bottom right corner
        self.resize_grip.raise_()  # Bring to front

        # Update resize grip position when dialog is resized
        def update_grip_position():
            self.resize_grip.move(
                self.width() - self.resize_grip.width(),
                self.height() - self.resize_grip.height()
            )

        self.resizeEvent = lambda event: (
            QDialog.resizeEvent(self, event),
            update_grip_position()
        )[1]

        update_grip_position()

        # Load current values
        self.load_current_values()

    def _create_scrollable_tab(self, title):
        """Create a scrollable tab widget"""
        scroll = QScrollArea()
        scroll.setWidgetResizable(True)
        scroll.setHorizontalScrollBarPolicy(Qt.ScrollBarPolicy.ScrollBarAlwaysOff)

        widget = QWidget()
        layout = QVBoxLayout(widget)
        layout.setSpacing(15)
        layout.setContentsMargins(10, 10, 10, 10)

        scroll.setWidget(widget)
        self.tabs.addTab(scroll, title)

        return layout

    def _create_visualization_toggles_tab(self):
        """Create tab for visualization enable/disable flags"""
        layout = self._create_scrollable_tab("Visibility")

        group = QGroupBox("Visualization Toggles")
        group_layout = QGridLayout()
        group_layout.setSpacing(10)

        row = 0

        # Point rendering toggles
        self._add_checkbox(group_layout, row, "SHOW_CONTROL_POINTS", "Show Control Points")
        row += 1
        self._add_checkbox(group_layout, row, "SHOW_ANCHOR_POINTS", "Show Anchor Points")
        row += 1

        # Drag visualization toggles
        group_layout.addWidget(QLabel("<b>During Drag:</b>"), row, 0, 1, 2)
        row += 1
        self._add_checkbox(group_layout, row, "SHOW_AXES_ON_DRAG", "Show Axes on Drag")
        row += 1
        self._add_checkbox(group_layout, row, "SHOW_LENGTH_ON_DRAG", "Show Length on Drag")
        row += 1
        self._add_checkbox(group_layout, row, "SHOW_ANGLE_ON_DRAG", "Show Angle on Drag")
        row += 1

        # Overlay visualization toggles
        group_layout.addWidget(QLabel("<b>In Point Info Overlay:</b>"), row, 0, 1, 2)
        row += 1
        self._add_checkbox(group_layout, row, "SHOW_AXES_ON_OVERLAY", "Show Axes on Overlay")
        row += 1
        self._add_checkbox(group_layout, row, "SHOW_LENGTH_ON_OVERLAY", "Show Length on Overlay")
        row += 1
        self._add_checkbox(group_layout, row, "SHOW_ANGLE_ON_OVERLAY", "Show Angle on Overlay")

        group.setLayout(group_layout)
        layout.addWidget(group)
        layout.addStretch()

    def _create_axes_and_angles_tab(self):
        """Create tab for coordinate axes and angle visualization"""
        layout = self._create_scrollable_tab("Axes & Angles")

        # Colors group
        colors_group = QGroupBox("Colors")
        colors_layout = QGridLayout()
        colors_layout.setSpacing(10)

        row = 0
        self._add_color(colors_layout, row, "AXIS_X_COLOR", "X Axis Color")
        row += 1
        self._add_color(colors_layout, row, "AXIS_Y_COLOR", "Y Axis Color")
        row += 1
        self._add_color(colors_layout, row, "AXIS_ANGLE_ARC_COLOR", "Angle Arc Color")
        row += 1
        self._add_color(colors_layout, row, "AXIS_VECTOR_LINE_COLOR", "Vector Line Color")
        row += 1
        self._add_color(colors_layout, row, "AXIS_LABEL_BG_COLOR", "Label Background Color")

        colors_group.setLayout(colors_layout)
        layout.addWidget(colors_group)

        # Line properties group
        lines_group = QGroupBox("Line Properties")
        lines_layout = QGridLayout()
        lines_layout.setSpacing(16)

        row = 0
        self._add_spinbox(lines_layout, row, "AXIS_LINE_THICKNESS", "Axis Line Thickness", 1, 20, False)
        row += 1
        self._add_spinbox(lines_layout, row, "AXIS_VECTOR_LINE_THICKNESS", "Vector Line Thickness", 1, 20, False)
        row += 1
        self._add_spinbox(lines_layout, row, "AXIS_ARC_RADIUS", "Arc Radius", 10, 200, False)

        lines_group.setLayout(lines_layout)
        layout.addWidget(lines_group)

        # Label properties group
        labels_group = QGroupBox("Label Properties")
        labels_layout = QGridLayout()
        labels_layout.setSpacing(16)

        row = 0
        self._add_spinbox(labels_layout, row, "AXIS_LABEL_FONT_SIZE", "Font Size", 6, 24, False)
        row += 1
        self._add_spinbox(labels_layout, row, "AXIS_LABEL_PADDING_X", "Padding X", 0, 20, False)
        row += 1
        self._add_spinbox(labels_layout, row, "AXIS_LABEL_PADDING_Y", "Padding Y", 0, 20, False)
        row += 1
        self._add_spinbox(labels_layout, row, "AXIS_LABEL_BORDER_RADIUS", "Border Radius", 0, 20, False)

        labels_group.setLayout(labels_layout)
        layout.addWidget(labels_group)

        layout.addStretch()

    def _create_segment_length_tab(self):
        """Create tab for segment length measurement"""
        layout = self._create_scrollable_tab("Length Measurement")

        group = QGroupBox("Segment Length Measurement")
        group_layout = QGridLayout()
        group_layout.setSpacing(16)

        row = 0
        self._add_color(group_layout, row, "SEGMENT_LENGTH_COLOR", "Line Color")
        row += 1
        self._add_color(group_layout, row, "SEGMENT_LENGTH_BG_COLOR", "Background Color")
        row += 1
        self._add_spinbox(group_layout, row, "SEGMENT_LENGTH_LINE_THICKNESS", "Line Thickness", 1, 10, False)
        row += 1
        self._add_spinbox(group_layout, row, "SEGMENT_LENGTH_OFFSET_DISTANCE", "Offset Distance", 5, 100, False)
        row += 1
        self._add_spinbox(group_layout, row, "SEGMENT_LENGTH_TICK_SIZE", "Tick Size", 1, 20, False)
        row += 1
        self._add_spinbox(group_layout, row, "SEGMENT_LENGTH_FONT_SIZE", "Font Size", 6, 24, False)

        group.setLayout(group_layout)
        layout.addWidget(group)
        layout.addStretch()

    def _create_highlighted_line_tab(self):
        """Create tab for highlighted line segment"""
        layout = self._create_scrollable_tab("Highlighted Line")

        group = QGroupBox("Highlighted Line Segment")
        group_layout = QGridLayout()
        group_layout.setSpacing(16)

        row = 0
        self._add_color(group_layout, row, "HIGHLIGHTED_LINE_COLOR", "Line Color")
        row += 1
        self._add_spinbox(group_layout, row, "HIGHLIGHTED_LINE_THICKNESS", "Line Thickness", 1, 20, False)

        group.setLayout(group_layout)
        layout.addWidget(group)
        layout.addStretch()

    def _create_crosshair_tab(self):
        """Create tab for drag crosshair"""
        layout = self._create_scrollable_tab("Crosshair")

        # Style options group
        style_group = QGroupBox("Crosshair Style")
        style_layout = QGridLayout()
        style_layout.setSpacing(10)

        row = 0
        self._add_combobox(style_layout, row, "CROSSHAIR_STYLE", "Crosshair Type", ["circle", "simple"])
        row += 1
        self._add_combobox(style_layout, row, "CROSSHAIR_LINE_STYLE", "Line Style", ["solid", "dashed"])

        style_group.setLayout(style_layout)
        layout.addWidget(style_group)

        # Colors group
        colors_group = QGroupBox("Colors")
        colors_layout = QGridLayout()
        colors_layout.setSpacing(10)

        row = 0
        self._add_color(colors_layout, row, "CROSSHAIR_COLOR", "Crosshair Color")
        row += 1
        self._add_color(colors_layout, row, "CROSSHAIR_CONNECTOR_COLOR", "Connector Color")

        colors_group.setLayout(colors_layout)
        layout.addWidget(colors_group)

        # Properties group
        props_group = QGroupBox("Properties")
        props_layout = QGridLayout()
        props_layout.setSpacing(16)

        row = 0
        self._add_spinbox(props_layout, row, "CROSSHAIR_LINE_THICKNESS", "Line Thickness", 1, 10, False)
        row += 1
        self._add_spinbox(props_layout, row, "CROSSHAIR_SIZE", "Crosshair Size", 10, 50, False)
        row += 1
        self._add_spinbox(props_layout, row, "CROSSHAIR_OFFSET_Y", "Offset Y", -200, 200, False)
        row += 1
        self._add_spinbox(props_layout, row, "CROSSHAIR_CIRCLE_RADIUS", "Circle Radius", 2, 30, False)
        row += 1
        self._add_spinbox(props_layout, row, "CROSSHAIR_CONNECTOR_THICKNESS", "Connector Thickness", 1, 10, False)

        props_group.setLayout(props_layout)
        layout.addWidget(props_group)

        layout.addStretch()

    def _create_point_rendering_tab(self):
        """Create tab for point rendering"""
        layout = self._create_scrollable_tab("Points")

        group = QGroupBox("Point Rendering")
        group_layout = QGridLayout()
        group_layout.setSpacing(16)

        row = 0
        self._add_color(group_layout, row, "POINT_HANDLE_COLOR", "Handle Color")
        row += 1
        self._add_color(group_layout, row, "POINT_HANDLE_SELECTED_COLOR", "Selected Handle Color")
        row += 1
        self._add_spinbox(group_layout, row, "POINT_HANDLE_RADIUS", "Handle Radius", 2, 20, False)
        row += 1
        self._add_spinbox(
            group_layout, row, "POINT_MIN_DISPLAY_SCALE", "Min Display Scale",
            0.1, 10.0, True, step_options=[0.001, 0.01, 0.1, 1]
        )

        group.setLayout(group_layout)
        layout.addWidget(group)
        layout.addStretch()

    def _create_overlays_tab(self):
        """Create tab for overlay settings"""
        layout = self._create_scrollable_tab("Overlays")

        # Button sizes group
        sizes_group = QGroupBox("Button Sizes")
        sizes_layout = QGridLayout()
        sizes_layout.setSpacing(16)

        row = 0
        self._add_spinbox(sizes_layout, row, "OVERLAY_BUTTON_SIZE", "Button Size", 20, 100, False)
        row += 1
        self._add_spinbox(sizes_layout, row, "OVERLAY_RADIUS", "Overlay Radius", 30, 150, False)
        row += 1
        self._add_spinbox(sizes_layout, row, "OVERLAY_BUTTON_BORDER_WIDTH", "Border Width", 1, 10, False)
        row += 1
        self._add_spinbox(sizes_layout, row, "OVERLAY_BUTTON_SELECTED_BORDER_WIDTH", "Selected Border Width", 1, 10, False)

        sizes_group.setLayout(sizes_layout)
        layout.addWidget(sizes_group)

        # Button colors group
        colors_group = QGroupBox("Button Colors")
        colors_layout = QGridLayout()
        colors_layout.setSpacing(10)

        row = 0
        self._add_color(colors_layout, row, "OVERLAY_BUTTON_PRIMARY_COLOR", "Primary Color")
        row += 1
        self._add_color(colors_layout, row, "OVERLAY_BUTTON_PRIMARY_HOVER", "Primary Hover")
        row += 1
        self._add_color(colors_layout, row, "OVERLAY_BUTTON_SELECTED_COLOR", "Selected Color")
        row += 1
        self._add_color(colors_layout, row, "OVERLAY_BUTTON_SELECTED_BORDER", "Selected Border")
        row += 1
        self._add_color(colors_layout, row, "OVERLAY_BUTTON_DELETE_COLOR", "Delete Color")
        row += 1
        self._add_color(colors_layout, row, "OVERLAY_BUTTON_DELETE_HOVER", "Delete Hover")
        row += 1
        self._add_color(colors_layout, row, "OVERLAY_BUTTON_SET_LENGTH_COLOR", "Set Length Color")
        row += 1
        self._add_color(colors_layout, row, "OVERLAY_BUTTON_SET_LENGTH_HOVER", "Set Length Hover")
        row += 1
        self._add_color(colors_layout, row, "OVERLAY_BUTTON_CANCEL_COLOR", "Cancel Color")
        row += 1
        self._add_color(colors_layout, row, "OVERLAY_BUTTON_CANCEL_HOVER", "Cancel Hover")

        colors_group.setLayout(colors_layout)
        layout.addWidget(colors_group)

        layout.addStretch()

    def _create_measurement_timing_tab(self):
        """Create tab for measurement and timing settings"""
        layout = self._create_scrollable_tab("Measurement & Timing")

        # Measurement group
        measurement_group = QGroupBox("Measurement & Conversion")
        measurement_layout = QGridLayout()
        measurement_layout.setSpacing(16)

        row = 0
        self._add_spinbox(measurement_layout, row, "PIXELS_PER_MM", "Pixels per MM", 0.1, 10.0, True)

        measurement_group.setLayout(measurement_layout)
        layout.addWidget(measurement_group)

        # Drag & Selection group
        drag_group = QGroupBox("Drag & Selection")
        drag_layout = QGridLayout()
        drag_layout.setSpacing(16)

        row = 0
        self._add_spinbox(drag_layout, row, "DRAG_THRESHOLD_PX", "Drag Threshold (px)", 1, 50, False)
        row += 1
        self._add_spinbox(drag_layout, row, "POINT_HIT_RADIUS_PX", "Point Hit Radius (px)", 1, 50, False)
        row += 1
        self._add_spinbox(drag_layout, row, "CLUSTER_DISTANCE_PX", "Cluster Distance (px)", 1, 50, False)

        drag_group.setLayout(drag_layout)
        layout.addWidget(drag_group)

        # Timing group
        timing_group = QGroupBox("Timing")
        timing_layout = QGridLayout()
        timing_layout.setSpacing(16)

        row = 0
        self._add_spinbox(timing_layout, row, "DRAG_UPDATE_INTERVAL_MS", "Drag Update Interval (ms)", 8, 100, False)
        row += 1
        self._add_spinbox(timing_layout, row, "POINT_INFO_HOLD_DURATION_MS", "Point Info Hold Duration (ms)", 100, 2000, False)
        row += 1
        self._add_spinbox(timing_layout, row, "PRESS_HOLD_MOVEMENT_THRESHOLD_PX", "Press Hold Movement Threshold (px)", 1, 50, False)

        timing_group.setLayout(timing_layout)
        layout.addWidget(timing_group)

        layout.addStretch()

    # ------------------------------------------------------------------
    # Widget factory helpers
    # ------------------------------------------------------------------

    def _add_checkbox(self, layout, row, const_name, label):
        """Add a checkbox for a boolean constant"""
        checkbox = QCheckBox(label, self)
        checkbox.setFont(QFont("Arial", 10))
        layout.addWidget(checkbox, row, 0, 1, 2)
        self.inputs[const_name] = checkbox

    def _add_color(self, layout, row, const_name, label):
        """Add a color picker button"""
        label_widget = QLabel(label + ":", self)
        label_widget.setFont(QFont("Arial", 10))

        color_button = ColorButton(QColor(255, 255, 255), self)

        layout.addWidget(label_widget, row, 0)
        layout.addWidget(color_button, row, 1)

        self.inputs[const_name] = color_button

    def _add_spinbox(self, layout, row, const_name, label,
                     min_val, max_val, is_float, step_options=None):
        """Add a touch spinbox for numeric constants.

        Integer fields get a fixed step of 1 with no step pills.
        Float fields get step=0.1 with decimals=3.
        Only fields that explicitly pass step_options get the pill row.
        """
        label_widget = QLabel(label + ":", self)
        label_widget.setFont(QFont("Arial", 10))
        label_widget.setAlignment(
            Qt.AlignmentFlag.AlignTop | Qt.AlignmentFlag.AlignLeft
        )

        if is_float:
            spinbox = TouchSpinBox(
                min_val=min_val, max_val=max_val,
                step=0.1, decimals=3,
                step_options=step_options,
            )
            self._float_inputs.add(const_name)
        else:
            spinbox = TouchSpinBox(
                min_val=min_val, max_val=max_val,
                step=1, decimals=0,
            )

        layout.addWidget(label_widget, row, 0, Qt.AlignmentFlag.AlignTop)
        layout.addWidget(spinbox, row, 1)

        self.inputs[const_name] = spinbox

    def _add_combobox(self, layout, row, const_name, label, options):
        """Add a combobox for string constants with predefined options"""
        label_widget = QLabel(label + ":", self)
        label_widget.setFont(QFont("Arial", 10))

        combobox = QComboBox(self)
        combobox.addItems(options)
        combobox.setFont(QFont("Arial", 10))
        combobox.setMinimumWidth(100)

        layout.addWidget(label_widget, row, 0)
        layout.addWidget(combobox, row, 1)

        self.inputs[const_name] = combobox

    # ------------------------------------------------------------------
    # Data access
    # ------------------------------------------------------------------

    def load_current_values(self):
        """Load current values from constants module (with JSON overrides if they exist)"""
        try:
            current_values = ConstantsManager.get_all_constants()

            for const_name, widget in self.inputs.items():
                if const_name in current_values:
                    value = current_values[const_name]

                    if isinstance(widget, QCheckBox):
                        widget.setChecked(value)
                    elif isinstance(widget, ColorButton):
                        widget.update_color(value)
                    elif isinstance(widget, TouchSpinBox):
                        try:
                            widget.setValue(float(value))
                        except (ValueError, TypeError):
                            pass
                    elif isinstance(widget, QComboBox):
                        index = widget.findText(value)
                        if index >= 0:
                            widget.setCurrentIndex(index)

        except Exception as e:
            print(f"Error loading constants: {e}")
            import traceback
            traceback.print_exc()

    def get_values(self):
        """Get all values from input widgets as a dictionary"""
        values = {}
        for const_name, widget in self.inputs.items():
            if isinstance(widget, QCheckBox):
                values[const_name] = widget.isChecked()
            elif isinstance(widget, ColorButton):
                values[const_name] = widget.get_color()
            elif isinstance(widget, TouchSpinBox):
                v = widget.value()
                # Return int for integer fields, float for float fields
                values[const_name] = (
                    v if const_name in self._float_inputs else int(round(v))
                )
            elif isinstance(widget, QComboBox):
                values[const_name] = widget.currentText()
        return values

    def apply_changes(self):
        """Apply changes by saving to JSON and updating the constants module"""
        try:
            values = self.get_values()

            if not ConstantsManager.save_settings(values):
                print("Failed to save settings to JSON")
                return False

            ConstantsManager.apply_settings(values)

            if self.parent():
                if hasattr(self.parent(), '_reload_constants'):
                    self.parent()._reload_constants()
                else:
                    self.parent().update()

            print("Settings applied successfully!")
            return True

        except Exception as e:
            print(f"Error applying settings: {e}")
            import traceback
            traceback.print_exc()
            return False

    def reset_to_defaults(self):
        """Reset all settings to default values"""
        if ConstantsManager.reset_to_defaults():
            self.load_current_values()

            if self.parent():
                if hasattr(self.parent(), '_reload_constants'):
                    self.parent()._reload_constants()
                else:
                    self.parent().update()

            print("Settings reset to defaults")
            return True
        return False

    def _on_apply_clicked(self):
        self.apply_changes()

    def _on_ok_clicked(self):
        if self.apply_changes():
            self.accept()

    def _on_reset_clicked(self):
        from PyQt6.QtWidgets import QMessageBox
        reply = QMessageBox.question(
            self,
            "Reset to Defaults",
            "Are you sure you want to reset all settings to their default values?",
            QMessageBox.StandardButton.Yes | QMessageBox.StandardButton.No,
            QMessageBox.StandardButton.No
        )

        if reply == QMessageBox.StandardButton.Yes:
            self.reset_to_defaults()