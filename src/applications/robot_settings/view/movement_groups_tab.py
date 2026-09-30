from typing import Callable, Dict, List, Optional

from PyQt6.QtCore import QCoreApplication, QEvent, QSize, Qt, QTimer, pyqtSignal
from PyQt6.QtWidgets import (
    QDialog, QGridLayout, QHBoxLayout, QLabel, QLineEdit,
    QListWidget, QListWidgetItem, QPushButton, QButtonGroup, QSizePolicy, QStackedWidget,
    QScrollArea, QVBoxLayout, QWidget, QFrame, QComboBox,
)

from src.engine.robot.configuration import MovementGroup
from src.shared_contracts.declarations import (
    MovementGroupDefinition,
    MovementGroupType,
)

from pl_gui.settings.settings_view.styles import (
    ACTION_BTN_STYLE, BG_COLOR, BORDER, GHOST_BTN_STYLE,
    GROUP_STYLE, LABEL_STYLE, PRIMARY, PRIMARY_DARK, PRIMARY_LIGHT,
    SECONDARY_BG, TEXT_COLOR,
)
from src.applications.base.widgets.custom_virtual_keyboard import KeyboardDoubleSpinBox
from src.applications.base.widgets.keyboard_number_field import KeyboardNumberField
from pl_gui.utils.utils_widgets.touch_spinbox import TouchSpinBox


_ACTION_BTN_STYLE = ACTION_BTN_STYLE
_GHOST_BTN_STYLE  = GHOST_BTN_STYLE


def _t(text: str) -> str:
    return QCoreApplication.translate("RobotSettings", text) or text

# ── Styles ────────────────────────────────────────────────────────────────────

_LIST_STYLE = f"""
QListWidget {{
    background: white;
    border: 2px solid {BORDER};
    border-radius: 8px;
    padding: 4px;
    font-size: 11pt;
}}
QListWidget::item:selected {{
    background: {PRIMARY_LIGHT};
    color: {PRIMARY_DARK};
}}
"""

_GROUP_NAV_STYLE = f"""
QListWidget {{
    background: white;
    border: 1px solid {BORDER};
    border-radius: 12px;
    padding: 4px;
    font-size: 11pt;
}}
QListWidget::item {{
    border-left: 4px solid transparent;
    padding-left: 12px;
}}
QListWidget::item:selected {{
    background: {PRIMARY_LIGHT};
    color: {PRIMARY_DARK};
    border-left: 4px solid {PRIMARY};
}}
"""

_POSITION_STYLE = f"""
QLineEdit {{
    background: white;
    color: #333333;
    border: 2px solid {BORDER};
    border-radius: 8px;
    padding: 8px 16px;
    font-size: 11pt;
    min-height: 44px;
}}
"""

_COORDINATE_SPIN_STYLE = f"""
QDoubleSpinBox {{
    background: white;
    color: #333333;
    border: 2px solid {BORDER};
    border-radius: 8px;
    padding: 8px 16px;
    font-size: 11pt;
    min-height: 56px;
}}
QDoubleSpinBox:focus {{
    border-color: {PRIMARY};
}}
"""

_COMBO_STYLE = f"""
QComboBox {{
    background: white;
    color: {TEXT_COLOR};
    border: 2px solid {BORDER};
    border-radius: 8px;
    padding: 8px 16px;
    font-size: 11pt;
    min-height: 44px;
}}
QComboBox:focus {{
    border-color: {PRIMARY};
}}
"""


# ── Position editor dialog ────────────────────────────────────────────────────

class PositionEditorDialog(QDialog):
    """
    Touch-friendly 6-DOF position editor.

    Layout: two columns — X / Y / Z on the left, RX / RY / RZ on the right.
    Each coordinate gets a keyboard-aware spin box with the configured range.
    """

    # (label, min, max, decimals, suffix, step, step_options)
    _COORDS = [
        ("X",  -2000.0, 2000.0, 3, " mm", 0.1, [0.1, 1.0, 10.0]),
        ("Y",  -2000.0, 2000.0, 3, " mm", 0.1, [0.1, 1.0, 10.0]),
        ("Z",  -2000.0, 2000.0, 3, " mm", 0.1, [0.1, 1.0, 10.0]),
        ("RX",  -180.0,  180.0, 2, " °",  1.0, [1.0, 5.0, 10.0]),
        ("RY",  -180.0,  180.0, 2, " °",  1.0, [1.0, 5.0, 10.0]),
        ("RZ",  -180.0,  180.0, 2, " °",  1.0, [1.0, 5.0, 10.0]),
    ]

    def __init__(self, title: str, position_str: str = "", parent=None):
        super().__init__(parent)
        self.setWindowTitle(title)
        self.setModal(True)
        self.setMinimumWidth(720)
        self.setStyleSheet(f"background: {BG_COLOR};")
        self._virtual_keyboard_dock_window = parent.window() if parent is not None else None
        self._keyboard_bottom_spacer: Optional[QWidget] = None
        self._keyboard_scroll_area: Optional[QScrollArea] = None

        values = self._parse(position_str)
        self._spinboxes: List[KeyboardDoubleSpinBox] = []

        root = QVBoxLayout(self)
        root.setContentsMargins(24, 24, 24, 24)
        root.setSpacing(20)

        # ── 2-column coordinate grid ──────────────────────────────────────
        grid_widget = QWidget()
        grid_widget.setStyleSheet("background: transparent;")
        grid = QGridLayout(grid_widget)
        grid.setHorizontalSpacing(24)
        grid.setVerticalSpacing(12)
        grid.setColumnStretch(0, 1)
        grid.setColumnStretch(1, 1)

        for i, (lbl_text, mn, mx, dec, sfx, stp, _opts) in enumerate(self._COORDS):
            col = 0 if i < 3 else 1
            row = i % 3

            cell = QWidget()
            cell.setStyleSheet("background: transparent;")
            cell_layout = QVBoxLayout(cell)
            cell_layout.setContentsMargins(0, 0, 0, 0)
            cell_layout.setSpacing(4)

            lbl = QLabel(lbl_text)
            lbl.setStyleSheet(LABEL_STYLE)
            cell_layout.addWidget(lbl)

            spin = KeyboardDoubleSpinBox()
            spin.setRange(mn, mx)
            spin.setDecimals(dec)
            spin.setSingleStep(stp)
            spin.setSuffix(sfx)
            spin.setValue(values[i])
            spin.setStyleSheet(_COORDINATE_SPIN_STYLE)
            cell_layout.addWidget(spin)
            self._spinboxes.append(spin)

            grid.addWidget(cell, row, col)

        self._keyboard_bottom_spacer = QWidget(grid_widget)
        self._keyboard_bottom_spacer.setFixedHeight(0)
        grid.addWidget(self._keyboard_bottom_spacer, 3, 0, 1, 2)

        scroll = QScrollArea(self)
        scroll.setWidgetResizable(True)
        scroll.setFrameShape(QScrollArea.Shape.NoFrame)
        scroll.setHorizontalScrollBarPolicy(Qt.ScrollBarPolicy.ScrollBarAlwaysOff)
        scroll.setWidget(grid_widget)
        self._keyboard_scroll_area = scroll
        root.addWidget(scroll)

        # ── Cancel / OK buttons ───────────────────────────────────────────
        btn_row = QWidget()
        btn_row.setStyleSheet("background: transparent;")
        btn_layout = QHBoxLayout(btn_row)
        btn_layout.setContentsMargins(0, 0, 0, 0)
        btn_layout.setSpacing(12)
        btn_layout.addStretch()

        cancel_btn = QPushButton("Cancel")
        cancel_btn.setStyleSheet(_GHOST_BTN_STYLE)
        cancel_btn.setMinimumWidth(120)
        cancel_btn.setCursor(Qt.CursorShape.PointingHandCursor)
        cancel_btn.clicked.connect(self.reject)
        btn_layout.addWidget(cancel_btn)

        ok_btn = QPushButton("OK")
        ok_btn.setStyleSheet(_ACTION_BTN_STYLE)
        ok_btn.setMinimumWidth(120)
        ok_btn.setCursor(Qt.CursorShape.PointingHandCursor)
        ok_btn.clicked.connect(self.accept)
        btn_layout.addWidget(ok_btn)

        root.addWidget(btn_row)

    def _on_virtual_keyboard_shown(self, keyboard_rect) -> None:
        if self._keyboard_scroll_area is None:
            return

        viewport = self._keyboard_scroll_area.viewport()
        overlap = viewport.mapToGlobal(viewport.rect().bottomLeft()).y() - keyboard_rect.top() + 24
        if self._keyboard_bottom_spacer is not None:
            self._keyboard_bottom_spacer.setFixedHeight(max(0, overlap))

        focused = self.focusWidget()
        if focused is not None:
            QTimer.singleShot(
                0,
                lambda: self._keyboard_scroll_area.ensureWidgetVisible(focused, 12, 12),
            )

    def _on_virtual_keyboard_hidden(self) -> None:
        if self._keyboard_bottom_spacer is not None:
            self._keyboard_bottom_spacer.setFixedHeight(0)

    # ── Helpers ───────────────────────────────────────────────────────────

    @staticmethod
    def _parse(position_str: str) -> List[float]:
        try:
            values = [float(x.strip()) for x in position_str.strip("[] ").split(",")]
            if len(values) == 6:
                return values
        except (ValueError, AttributeError):
            pass
        return [0.0, 0.0, 0.0, 0.0, 0.0, 0.0]

    def get_position_str(self) -> str:
        return "[" + ", ".join(f"{s.value():.3f}" for s in self._spinboxes) + "]"


# ── MovementGroupWidget ───────────────────────────────────────────────────────

class MovementGroupWidget(QWidget):
    """
    Collapsible widget for a single movement group.
    Collapsed by default — click the header to expand/collapse.
    """

    # Value-change signals
    velocity_changed     = pyqtSignal(str, int)
    acceleration_changed = pyqtSignal(str, int)
    motion_type_changed = pyqtSignal(str, str)
    iterations_changed   = pyqtSignal(str, int)
    position_changed     = pyqtSignal(str, str)
    points_changed       = pyqtSignal(str, list)

    # Action-request signals
    set_current_requested        = pyqtSignal(str)  # group_name — single position
    move_to_requested = pyqtSignal(str, object)  # group_name, point_str (None for single-pos)

    execute_trajectory_requested = pyqtSignal(str)
    remove_requested             = pyqtSignal(str)
    add_current_requested        = pyqtSignal(str)  # group_name — multi position

    def __init__(self, definition: MovementGroupDefinition, parent=None):
        super().__init__(parent)
        self._def      = definition
        self._name     = definition.id
        self._expanded = False
        self._card_mode = False
        self._position_section = None
        self._coordinate_fields: list[KeyboardNumberField] = []

        self.setSizePolicy(QSizePolicy.Policy.Expanding, QSizePolicy.Policy.Preferred)
        self.setStyleSheet("background: transparent;")

        outer = QVBoxLayout(self)
        self._outer_layout = outer
        outer.setContentsMargins(0, 0, 0, 0)
        outer.setSpacing(0)

        # ── Header ────────────────────────────────────────────────────
        self._header = QPushButton()
        self._header.setCheckable(True)
        self._header.setChecked(False)
        self._header.setSizePolicy(QSizePolicy.Policy.Expanding, QSizePolicy.Policy.Fixed)
        self._header.setMinimumHeight(44)
        self._header.setCursor(Qt.CursorShape.PointingHandCursor)
        self._header.clicked.connect(self._toggle)
        outer.addWidget(self._header)
        self._update_header_style(False)

        # ── Body ──────────────────────────────────────────────────────
        self._body = QFrame()
        self._body.setObjectName("mgBody")
        self._body.setStyleSheet(f"""
            QFrame#mgBody {{
                background: white;
                border: 1px solid {BORDER};
                border-top: none;
                border-radius: 0 0 8px 8px;
            }}
        """)
        self._body.setVisible(False)
        self._body_layout = QVBoxLayout(self._body)
        self._body_layout.setContentsMargins(12, 12, 12, 12)
        self._body_layout.setSpacing(12)
        outer.addWidget(self._body)

        # initialise optional widget references before _build_body
        self._velocity_spin:     Optional[KeyboardNumberField] = None
        self._acceleration_spin: Optional[KeyboardNumberField] = None
        self._motion_type_combo: Optional[QComboBox] = None
        self._iterations_spin:   Optional[TouchSpinBox] = None
        self._position_display:  Optional[QLineEdit]    = None
        self._points_list:       Optional[QListWidget]  = None

        self._build_body()
        outer.addStretch()

    def _update_header_style(self, expanded: bool) -> None:
        if self._card_mode:
            self._header.setText(f"  {(self._def.label or self._name).upper()} · {_t('Speed').upper()}")
            self._header.setStyleSheet(f"""
                QPushButton {{
                    background: {SECONDARY_BG}; color: {PRIMARY};
                    border: 1px solid {BORDER}; border-radius: 12px 12px 0 0;
                    text-align: left; padding-left: 12px;
                    font-size: 10pt; font-weight: bold;
                }}
            """)
            return
        arrow = "▲" if expanded else "▼"
        title = self._def.label or self._def.id
        self._header.setText(f"  {arrow}   {title}")
        self._header.setStyleSheet(f"""
            QPushButton {{
                background: {GROUP_STYLE.split('background:')[1].split(';')[0].strip()
                             if 'background:' in GROUP_STYLE else PRIMARY_LIGHT};
                color: {PRIMARY_DARK};
                border: 1px solid {BORDER};
                border-radius: {'0px' if expanded else '8px'};
                border-bottom-left-radius: {'0px' if expanded else '8px'};
                border-bottom-right-radius: {'0px' if expanded else '8px'};
                text-align: left;
                padding-left: 12px;
                font-size: 11pt;
                font-weight: bold;
            }}
            QPushButton:hover {{
                background: {BORDER};
            }}
        """)

    def _toggle(self) -> None:
        self._expanded = not self._expanded
        self._body.setVisible(self._expanded)
        self._update_header_style(self._expanded)
        # collapse the button check state to match
        self._header.setChecked(self._expanded)

    # ── UI construction ───────────────────────────────────────────────────

    def _build_body(self):
        # ── Remove button ──────────────────────────────────────────────
        if self._def.removable:
            rm_row = QHBoxLayout()
            rm_row.addStretch()
            rm_btn = QPushButton("✕ Remove Group")
            rm_btn.setStyleSheet(_GHOST_BTN_STYLE)
            rm_btn.setCursor(Qt.CursorShape.PointingHandCursor)
            rm_btn.clicked.connect(lambda: self.remove_requested.emit(self._name))
            rm_row.addWidget(rm_btn)
            self._body_layout.addLayout(rm_row)

        self._body_layout.addWidget(self._build_vel_acc_row())
        self._body_layout.addWidget(self._build_speed_step_row())
        self._body_layout.addWidget(self._build_motion_type_row())

        if self._def.has_iterations:
            self._body_layout.addWidget(self._build_iterations_row())

        if self._def.group_type == MovementGroupType.SINGLE_POSITION:
            self._position_section = self._build_single_position_section()
            self._body_layout.addWidget(self._position_section)
        elif self._def.group_type == MovementGroupType.MULTI_POSITION:
            self._position_section = self._build_multi_position_section()
            self._body_layout.addWidget(self._position_section)

    def use_card_layout(self) -> None:
        if self._card_mode:
            return
        self._card_mode = True
        self._header.setAttribute(Qt.WidgetAttribute.WA_TransparentForMouseEvents, True)
        self._update_header_style(True)
        if self._position_section is None:
            return
        self._body_layout.removeWidget(self._position_section)
        card = QFrame()
        card.setObjectName("movementPositionCard")
        card.setStyleSheet(f"""
            QFrame#movementPositionCard {{
                background: white; border: 1px solid {BORDER}; border-radius: 12px;
            }}
            QLabel#positionCardTitle {{
                background: {SECONDARY_BG}; color: {PRIMARY};
                padding: 10px 16px; font-size: 10pt; font-weight: bold;
            }}
        """)
        card_layout = QVBoxLayout(card)
        card_layout.setContentsMargins(0, 0, 0, 0)
        card_layout.setSpacing(0)
        self._position_card_title = QLabel()
        self._position_card_title.setObjectName("positionCardTitle")
        self._retranslate_card_title()
        card_layout.addWidget(self._position_card_title)
        body = QWidget()
        body_layout = QVBoxLayout(body)
        body_layout.setContentsMargins(16, 14, 16, 16)
        body_layout.addWidget(self._position_section)
        card_layout.addWidget(body)
        self._outer_layout.insertWidget(self._outer_layout.count() - 1, card)
        if hasattr(self, "_position_label"):
            self._position_label.hide()

    def _retranslate_card_title(self) -> None:
        section_name = "Points" if self._def.group_type == MovementGroupType.MULTI_POSITION else "Position"
        self._position_card_title.setText(
            f"{(self._def.label or self._name).upper()} · {_t(section_name).upper()}"
        )

    def changeEvent(self, event) -> None:
        if event.type() == QEvent.Type.LanguageChange and getattr(self, "_card_mode", False):
            self._update_header_style(self._expanded)
            if hasattr(self, "_position_card_title"):
                self._retranslate_card_title()
        super().changeEvent(event)


    def _build_vel_acc_row(self) -> QWidget:
        row = QWidget()
        row.setStyleSheet("background: transparent;")
        layout = QHBoxLayout(row)
        layout.setContentsMargins(0, 0, 0, 0)
        layout.setSpacing(16)

        vel_cell = self._labeled_cell("Velocity")
        self._velocity_spin = KeyboardNumberField()
        self._velocity_spin.setRange(0, 1000)
        self._velocity_spin.setSuffix(" %")
        self._velocity_spin.valueChanged.connect(
            lambda v: self.velocity_changed.emit(self._name, int(v))
        )
        vel_cell.layout().addWidget(self._velocity_spin)
        layout.addWidget(vel_cell)

        acc_cell = self._labeled_cell("Acceleration")
        self._acceleration_spin = KeyboardNumberField()
        self._acceleration_spin.setRange(0, 1000)
        self._acceleration_spin.setSuffix(" %")
        self._acceleration_spin.valueChanged.connect(
            lambda v: self.acceleration_changed.emit(self._name, int(v))
        )
        acc_cell.layout().addWidget(self._acceleration_spin)
        layout.addWidget(acc_cell)

        return row

    def _build_speed_step_row(self) -> QWidget:
        row = QWidget()
        layout = QHBoxLayout(row)
        layout.setContentsMargins(0, 0, 0, 0)
        layout.setSpacing(0)
        layout.addStretch()
        label = QLabel(_t("Step"))
        label.setStyleSheet(f"color: {PRIMARY}; font-size: 9pt; margin-right: 8px;")
        layout.addWidget(label)
        self._speed_step_buttons = QButtonGroup(row)
        self._speed_step_buttons.setExclusive(True)
        for step in (1, 5, 10, 50):
            button = QPushButton(str(step))
            button.setCheckable(True)
            button.setChecked(step == 1)
            button.setMinimumSize(44, 36)
            button.setCursor(Qt.CursorShape.PointingHandCursor)
            button.setStyleSheet(f"""
                QPushButton {{ background: white; color: {PRIMARY}; border: 1px solid {BORDER}; }}
                QPushButton:checked {{ background: {PRIMARY}; color: white; border-color: {PRIMARY}; }}
            """)
            button.clicked.connect(lambda _checked, value=step: self._set_speed_step(value))
            self._speed_step_buttons.addButton(button)
            layout.addWidget(button)
        return row

    def _set_speed_step(self, step: int) -> None:
        self._velocity_spin.setSingleStep(step)
        self._acceleration_spin.setSingleStep(step)

    def _build_motion_type_row(self) -> QWidget:
        row = QWidget()
        row.setStyleSheet("background: transparent;")
        layout = QHBoxLayout(row)
        layout.setContentsMargins(0, 0, 0, 0)
        layout.setSpacing(16)

        type_cell = self._labeled_cell("Type")
        self._motion_type_combo = QComboBox()
        self._motion_type_combo.addItem("PTP", "ptp")
        self._motion_type_combo.addItem("Linear", "linear")
        self._motion_type_combo.addItem("Fast LIN", "fast_lin")
        self._motion_type_combo.setStyleSheet(_COMBO_STYLE)
        self._motion_type_combo.currentIndexChanged.connect(self._on_motion_type_changed)
        type_cell.layout().addWidget(self._motion_type_combo)
        layout.addWidget(type_cell)
        layout.addStretch()

        return row

    def _build_iterations_row(self) -> QWidget:
        row = QWidget()
        row.setStyleSheet("background: transparent;")
        layout = QHBoxLayout(row)
        layout.setContentsMargins(0, 0, 0, 0)
        layout.setSpacing(16)

        iter_cell = self._labeled_cell("Iterations")
        self._iterations_spin = TouchSpinBox(
            min_val=1, max_val=100, initial=1,
            step=1, decimals=0, step_options=[1],
        )
        self._iterations_spin.valueChanged.connect(
            lambda v: self.iterations_changed.emit(self._name, int(v))
        )
        iter_cell.layout().addWidget(self._iterations_spin)
        layout.addWidget(iter_cell)
        layout.addStretch()

        return row

    def _build_single_position_section(self) -> QWidget:
        section = QWidget()
        section.setStyleSheet("background: transparent;")
        layout = QVBoxLayout(section)
        layout.setContentsMargins(0, 0, 0, 0)
        layout.setSpacing(8)

        self._position_label = QLabel("Position")
        self._position_label.setStyleSheet(LABEL_STYLE)
        layout.addWidget(self._position_label)

        coordinates = QGridLayout()
        coordinates.setHorizontalSpacing(12)
        coordinates.setVerticalSpacing(12)
        for index, axis in enumerate(("X", "Y", "Z", "RX", "RY", "RZ")):
            cell = self._labeled_cell(axis)
            field = KeyboardNumberField(decimal=True, button_width=38)
            field.setRange(-2000 if index < 3 else -180, 2000 if index < 3 else 180)
            field.setDecimals(3 if index < 3 else 2)
            field.setSingleStep(1 if index < 3 else 0.1)
            field.setSuffix(" mm" if index < 3 else " °")
            field.valueChanged.connect(self._on_coordinate_changed)
            cell.layout().addWidget(field)
            self._coordinate_fields.append(field)
            coordinates.addWidget(cell, index // 4, index % 4)
        layout.addLayout(coordinates)

        row = QWidget()
        row.setStyleSheet("background: transparent;")
        row_layout = QHBoxLayout(row)
        row_layout.setContentsMargins(0, 0, 0, 0)
        row_layout.setSpacing(8)

        self._position_display = QLineEdit()
        self._position_display.hide()
        self._position_display.setReadOnly(True)
        self._position_display.setStyleSheet(_POSITION_STYLE)
        self._position_display.setPlaceholderText("No position set")
        row_layout.addWidget(self._position_display)

        set_btn = QPushButton("Set Current")
        set_btn.setStyleSheet(_ACTION_BTN_STYLE)
        set_btn.setCursor(Qt.CursorShape.PointingHandCursor)
        set_btn.clicked.connect(self._on_set_current_clicked)
        row_layout.addWidget(set_btn)

        move_btn = QPushButton("Move To")
        move_btn.setStyleSheet(_ACTION_BTN_STYLE)
        move_btn.setCursor(Qt.CursorShape.PointingHandCursor)
        move_btn.clicked.connect(self._on_move_to_clicked)
        row_layout.addWidget(move_btn)

        row_layout.addStretch()

        layout.addWidget(row)
        return section

    def _on_coordinate_changed(self, _value) -> None:
        position = "[" + ", ".join(f"{field.value():.3f}" for field in self._coordinate_fields) + "]"
        self._position_display.setText(position)
        self.position_changed.emit(self._name, position)

    def _set_coordinate_fields(self, position_str: str) -> None:
        values = PositionEditorDialog._parse(position_str)
        for field, value in zip(self._coordinate_fields, values):
            field.blockSignals(True)
            field.setValue(value)
            field.blockSignals(False)

    def _build_multi_position_section(self) -> QWidget:
        section = QWidget()
        section.setStyleSheet("background: transparent;")
        layout = QVBoxLayout(section)
        layout.setContentsMargins(0, 0, 0, 0)
        layout.setSpacing(8)

        lbl = QLabel("Points")
        lbl.setStyleSheet(LABEL_STYLE)
        layout.addWidget(lbl)

        self._points_list = QListWidget()
        self._points_list.setFixedHeight(140)
        self._points_list.setStyleSheet(_LIST_STYLE)
        layout.addWidget(self._points_list)

        btn_row = QWidget()
        btn_row.setStyleSheet("background: transparent;")
        btn_layout = QHBoxLayout(btn_row)
        btn_layout.setContentsMargins(0, 0, 0, 0)
        btn_layout.setSpacing(8)

        add_btn = QPushButton("Add")
        add_btn.setStyleSheet(_GHOST_BTN_STYLE)
        add_btn.setCursor(Qt.CursorShape.PointingHandCursor)
        add_btn.clicked.connect(self._on_add_point)
        btn_layout.addWidget(add_btn)

        edit_btn = QPushButton("Edit")
        edit_btn.setStyleSheet(_GHOST_BTN_STYLE)
        edit_btn.setCursor(Qt.CursorShape.PointingHandCursor)
        edit_btn.clicked.connect(self._on_edit_selected_point)
        btn_layout.addWidget(edit_btn)

        for label, slot in [
            ("Remove", self._on_remove_point),
            ("Move To", self._on_move_to_point),  # ← named method
            ("Set Current", self._on_add_current),
        ]:
            btn = QPushButton(label)
            btn.setStyleSheet(_ACTION_BTN_STYLE)
            btn.setCursor(Qt.CursorShape.PointingHandCursor)
            btn.clicked.connect(slot)
            btn_layout.addWidget(btn)

        if self._def.has_trajectory_execution:
            exec_btn = QPushButton("Execute")
            exec_btn.setStyleSheet(_ACTION_BTN_STYLE)
            exec_btn.setCursor(Qt.CursorShape.PointingHandCursor)
            exec_btn.clicked.connect(lambda: self.execute_trajectory_requested.emit(self._name))
            btn_layout.addWidget(exec_btn)

        btn_layout.addStretch()
        layout.addWidget(btn_row)
        return section

    # ── Position editing ──────────────────────────────────────────────────

    def _open_editor(self, title: str, position_str: str, on_accept: Callable[[str], None]):
        dlg = PositionEditorDialog(title, position_str, parent=self)
        if dlg.exec() == QDialog.DialogCode.Accepted:
            on_accept(dlg.get_position_str())

    def _on_set_current_clicked(self) -> None:
        self.set_current_requested.emit(self._name)

    def _on_move_to_clicked(self) -> None:
        self.move_to_requested.emit(self._name, None)

    def _on_edit_single_position(self) -> None:
        current = self._position_display.text() if self._position_display else ""
        self._open_editor(
            f"Edit Position — {self._name}",
            current,
            lambda pos: (
                self._position_display.setText(pos),
                self.position_changed.emit(self._name, pos),
            ),
        )

    def _on_add_point(self):
        self._open_editor(
            f"Add Point — {self._name}",
            "",
            self._append_point,
        )

    def _on_edit_selected_point(self):
        row = self._points_list.currentRow()
        if row < 0:
            return
        current = self._points_list.item(row).text()
        self._open_editor(
            f"Edit Point {row} — {self._name}",
            current,
            lambda pos: self._update_point(row, pos),
        )

    def _append_point(self, pos: str):
        item = QListWidgetItem(pos)
        self._points_list.addItem(item)
        self._points_list.setCurrentItem(item)
        self.points_changed.emit(self._name, self._collect_points())

    def _update_point(self, row: int, pos: str):
        self._points_list.item(row).setText(pos)
        self.points_changed.emit(self._name, self._collect_points())

    def _on_move_to_point(self) -> None:
        if self._points_list is None:
            return
        row = self._points_list.currentRow()
        if row < 0:
            self.move_to_requested.emit(self._name, None)   # controller will warn "no point selected"
            return
        point_str = self._points_list.item(row).text()
        self.move_to_requested.emit(self._name, point_str)
    # ── Internal helpers ──────────────────────────────────────────────────

    @staticmethod
    def _labeled_cell(label_text: str) -> QWidget:
        cell = QWidget()
        cell.setStyleSheet("background: transparent;")
        layout = QVBoxLayout(cell)
        layout.setContentsMargins(0, 0, 0, 0)
        layout.setSpacing(6)
        lbl = QLabel(label_text)
        lbl.setStyleSheet(LABEL_STYLE)
        layout.addWidget(lbl)
        return cell

    def _on_remove_point(self):
        if self._points_list is not None:
            row = self._points_list.currentRow()
            if row >= 0:
                self._points_list.takeItem(row)
                self.points_changed.emit(self._name, self._collect_points())

    def _on_add_current(self):
        self.add_current_requested.emit(self._name)

    def _on_motion_type_changed(self) -> None:
        if self._motion_type_combo is None:
            return
        self.motion_type_changed.emit(self._name, str(self._motion_type_combo.currentData() or "ptp"))

    def _collect_points(self) -> List[str]:
        return [self._points_list.item(i).text() for i in range(self._points_list.count())]

    # ── Public API ────────────────────────────────────────────────────────

    def load(self, group: MovementGroup) -> None:
        """Populate all widgets from a model — no signals emitted."""
        for spin, val in [
            (self._velocity_spin,     int(group.velocity)),
            (self._acceleration_spin, int(group.acceleration)),
        ]:
            if spin:
                spin.blockSignals(True)
                spin.setValue(val)
                spin.blockSignals(False)

        if self._iterations_spin:
            self._iterations_spin.blockSignals(True)
            self._iterations_spin.setValue(float(group.iterations))
            self._iterations_spin.blockSignals(False)

        if self._motion_type_combo:
            self._motion_type_combo.blockSignals(True)
            motion_type = MovementGroup._normalize_motion_type(getattr(group, "motion_type", "ptp"))
            index = self._motion_type_combo.findData(motion_type)
            self._motion_type_combo.setCurrentIndex(max(0, index))
            self._motion_type_combo.blockSignals(False)

        if self._position_display is not None:
            self._position_display.setText(group.position or "")
            self._set_coordinate_fields(group.position or "")

        if self._points_list is not None:
            self._points_list.clear()
            for pt in group.points:
                self._points_list.addItem(QListWidgetItem(pt))

    def get_values(self) -> MovementGroup:
        return MovementGroup(
            velocity=int(self._velocity_spin.value()) if self._velocity_spin else 0,
            acceleration=int(self._acceleration_spin.value()) if self._acceleration_spin else 0,
            motion_type=str(self._motion_type_combo.currentData() or "ptp") if self._motion_type_combo else "ptp",
            iterations=int(self._iterations_spin.value()) if self._iterations_spin else 1,
            position=self._position_display.text() or None if self._position_display else None,
            points=self._collect_points() if self._points_list else [],
            has_iterations=self._def.has_iterations,
            has_trajectory_execution=self._def.has_trajectory_execution,
        )

    def set_position(self, position_str: str) -> None:
        """Called by controller after handling set_current_requested."""
        if self._position_display is not None:
            self._position_display.setText(position_str)
            self._set_coordinate_fields(position_str)
            self.position_changed.emit(self._name, position_str)

    def add_point(self, point_str: str) -> None:
        """Called by controller after handling set_current_requested on a multi-pos group."""
        if self._points_list is not None:
            item = QListWidgetItem(point_str)
            self._points_list.addItem(item)
            self._points_list.scrollToItem(item)
            self._points_list.setCurrentItem(item)
            self.points_changed.emit(self._name, self._collect_points())


# ── MovementGroupsTab ─────────────────────────────────────────────────────────

class MovementGroupsTab(QWidget):
    """
    Group selector and editor driven by RobotConfig.movement_groups.

    Usage:
        tab = MovementGroupsTab()
        tab.load(config.movement_groups)

        # Wire actions to controller externally:
        tab.set_current_requested.connect(controller.handle_set_current)
        tab.execute_trajectory_requested.connect(controller.handle_execute)
    """

    values_changed               = pyqtSignal(str, object)  # "GROUP_NAME.field", value
    set_current_requested        = pyqtSignal(str)           # group_name
    move_to_requested = pyqtSignal(str, object)  # group_name, point_str or None

    execute_trajectory_requested = pyqtSignal(str)           # group_name
    remove_group_requested = pyqtSignal(str)  # group_name
    add_current_requested = pyqtSignal(str)   # group_name — for multi-position

    def __init__(self, parent=None):
        super().__init__(parent)
        self.setStyleSheet(f"background: {BG_COLOR};")
        self._widgets: Dict[str, MovementGroupWidget] = {}
        self._definitions: Dict[str, MovementGroupDefinition] = {}

        self._layout = QHBoxLayout(self)
        self._layout.setContentsMargins(16, 16, 16, 16)
        self._layout.setSpacing(14)

        self._group_list = QListWidget()
        self._group_list.setFixedWidth(270)
        self._group_list.setStyleSheet(_GROUP_NAV_STYLE)
        self._group_list.setSpacing(2)
        self._group_list.currentRowChanged.connect(self._show_group)
        self._layout.addWidget(self._group_list)

        self._group_pages = QStackedWidget()
        self._layout.addWidget(self._group_pages, 1)

    def _show_group(self, index: int) -> None:
        if index < 0:
            return
        self._group_pages.setCurrentIndex(index)
        widget = self._group_pages.currentWidget()
        if isinstance(widget, MovementGroupWidget) and not widget._expanded:
            widget._toggle()
        if isinstance(widget, MovementGroupWidget):
            widget.use_card_layout()

    def load(
        self,
        groups: Dict[str, MovementGroup],
        definitions: List[MovementGroupDefinition] | None = None,
    ) -> None:
        definitions = list(definitions or [])
        self._definitions = {definition.id: definition for definition in definitions}

        ordered_names = [definition.id for definition in definitions]
        for name in groups:
            if name not in self._definitions:
                inferred = self._infer_def(name, groups[name])
                self._definitions[name] = inferred
                ordered_names.append(name)

        for name in list(self._widgets):
            if name not in ordered_names:
                self.remove_group(name)

        for name in ordered_names:
            group = groups.get(name, self._definitions[name].build_default_group())
            if name not in self._widgets:
                widget = MovementGroupWidget(self._definitions[name])
                self._connect_widget(widget)
                self._widgets[name] = widget
                self._group_pages.addWidget(widget)
                self._add_group_item(self._definitions[name].label or name)
            self._widgets[name].load(group)
        if self._group_list.currentRow() < 0 and self._group_list.count():
            self._group_list.setCurrentRow(0)

    def get_values(self) -> Dict[str, MovementGroup]:
        return {name: w.get_values() for name, w in self._widgets.items()}

    def get_widget(self, group_name: str) -> Optional[MovementGroupWidget]:
        return self._widgets.get(group_name)

    def add_group(self, name: str, defn: MovementGroupDefinition, group: MovementGroup) -> None:
        if name in self._widgets:
            return
        widget = MovementGroupWidget(defn)
        self._connect_widget(widget)
        self._widgets[name] = widget
        self._definitions[name] = defn
        self._group_pages.addWidget(widget)
        self._add_group_item(defn.label or name)
        widget.load(group)
        if self._group_list.currentRow() < 0:
            self._group_list.setCurrentRow(0)

    def remove_group(self, name: str) -> None:
        widget = self._widgets.pop(name, None)
        if widget is not None:
            index = self._group_pages.indexOf(widget)
            self._group_pages.removeWidget(widget)
            self._group_list.takeItem(index)
            widget.deleteLater()

    # ── Private ───────────────────────────────────────────────────────────

    def _add_group_item(self, label: str) -> None:
        item = QListWidgetItem(label)
        item.setSizeHint(QSize(0, 54))
        self._group_list.addItem(item)

    @staticmethod
    def _infer_def(name: str, group: MovementGroup) -> MovementGroupDefinition:
        upper = name.upper()
        if "PICKUP" in upper or "DROPOFF" in upper:
            return MovementGroupDefinition(
                id=name,
                label=name,
                group_type=MovementGroupType.MULTI_POSITION,
                has_trajectory_execution=True,
            )
        if group.position is not None:
            gtype = MovementGroupType.SINGLE_POSITION
        elif group.points:
            gtype = MovementGroupType.MULTI_POSITION
        else:
            gtype = MovementGroupType.VELOCITY_ONLY
        return MovementGroupDefinition(
            id=name,
            label=name,
            group_type=gtype,
            has_iterations=group.has_iterations,
            has_trajectory_execution=group.has_trajectory_execution,
            removable=True,
        )

    def _connect_widget(self, w: MovementGroupWidget) -> None:
        w.velocity_changed.connect(
            lambda n, v: self.values_changed.emit(f"{n}.velocity", v)
        )
        w.acceleration_changed.connect(
            lambda n, v: self.values_changed.emit(f"{n}.acceleration", v)
        )
        w.motion_type_changed.connect(
            lambda n, v: self.values_changed.emit(f"{n}.motion_type", v)
        )
        w.iterations_changed.connect(
            lambda n, v: self.values_changed.emit(f"{n}.iterations", v)
        )
        w.position_changed.connect(
            lambda n, v: self.values_changed.emit(f"{n}.position", v)
        )
        w.points_changed.connect(
            lambda n, v: self.values_changed.emit(f"{n}.points", v)
        )
        w.set_current_requested.connect(self.set_current_requested)
        w.move_to_requested.connect(self.move_to_requested)
        w.execute_trajectory_requested.connect(self.execute_trajectory_requested)
        w.remove_requested.connect(self.remove_group_requested)
        w.add_current_requested.connect(self.set_current_requested)  # reuse same signal
