from functools import partial
from typing import List, Optional, Sequence

from PyQt6.QtCore import QCoreApplication, QEvent, Qt, QTimer, pyqtSignal
from PyQt6.QtWidgets import (
    QFrame, QVBoxLayout, QHBoxLayout, QGridLayout,
    QPushButton, QLabel, QSlider, QSizePolicy, QSpacerItem,
    QButtonGroup, QComboBox, QWidget, QTabWidget,
)

from pl_gui.settings.settings_view.styles import (
    PRIMARY, PRIMARY_DARK, BG_COLOR, BORDER,
    TEXT_COLOR, SECONDARY_BG, SECONDARY_HOVER,
)

_LINEAR_STEPS:   list[float] = [0.1,0.2, 0.5, 1.0, 5.0, 10.0, 50.0,100,250]
_ROTATION_STEPS: list[float] = [0.1,0.2, 0.5, 1.0, 5.0, 10.0, 45.0, 90.0,180,360]
_JOINT_STEPS:    list[float] = [0.1, 0.5, 1.0, 5.0, 10.0, 45.0, 90.0]
_LINEAR_AXES  = {"X", "Y", "Z"}
_JOG_INTERVAL_MS = 100

_AXES = [
    ("x_plus",  "X",  "Plus"),
    ("x_minus", "X",  "Minus"),
    ("y_plus",  "Y",  "Plus"),
    ("y_minus", "Y",  "Minus"),
    ("z_plus",  "Z",  "Plus"),
    ("z_minus", "Z",  "Minus"),
    ("rx_plus",  "RX", "Plus"),
    ("rx_minus", "RX", "Minus"),
    ("ry_plus",  "RY", "Plus"),
    ("ry_minus", "RY", "Minus"),
    ("rz_plus",  "RZ", "Plus"),
    ("rz_minus", "RZ", "Minus"),
]

_JOINT_NAMES = ["J1", "J2", "J3", "J4", "J5", "J6"]

_SLIDER_STYLE = f"""
    QSlider::groove:horizontal {{
        border: 1px solid {BORDER};
        height: 6px;
        background: #F5F5F5;
        border-radius: 3px;
    }}
    QSlider::handle:horizontal {{
        background: {PRIMARY};
        border: 1px solid {PRIMARY};
        width: 22px; height: 22px;
        border-radius: 11px;
        margin: -8px 0;
    }}
    QSlider::handle:horizontal:hover {{ background: {PRIMARY_DARK}; }}
    QSlider::sub-page:horizontal {{
        background: {PRIMARY};
        height: 6px;
        border-radius: 3px;
    }}
    QSlider::add-page:horizontal {{
        background: #F5F5F5;
        border: 1px solid {BORDER};
        height: 6px;
        border-radius: 3px;
    }}
"""

_POS_AXES = [
    ("X",  0), ("Y",  1), ("Z",  2),
    ("RX", 3), ("RY", 4), ("RZ", 5),
]


class RobotJogWidget(QFrame):
    jog_requested        = pyqtSignal(str, str, str, float)  # command, axis, direction, step
    jog_started          = pyqtSignal(str)
    jog_stopped          = pyqtSignal(str)
    frame_changed        = pyqtSignal(str)   # emitted when the frame/point selector changes

    joint_jog_requested  = pyqtSignal(str, str, str, float)  # command, joint, direction, step
    joint_jog_started    = pyqtSignal(str)
    joint_jog_stopped    = pyqtSignal(str)

    def __init__(self, parent=None):
        super().__init__(parent)
        self._timers:   dict[str, QTimer]       = {}
        self._axis_map: dict[str, tuple[str, str]] = {}
        self._joint_timers:   dict[str, QTimer]       = {}
        self._joint_axis_map: dict[str, tuple[str, str]] = {}
        self._joint_btns:     dict[str, QPushButton]     = {}
        self._frame_label: Optional[QLabel]     = None
        self._frame_combo: Optional[QComboBox]  = None
        self._jog_mode_group: Optional[QButtonGroup] = None
        self._linear_title_label: Optional[QLabel] = None
        self._rotation_title_label: Optional[QLabel] = None
        self._joint_step_title_label: Optional[QLabel] = None
        self._setup_ui()
        self._setup_timers()
        self.retranslateUi()

    # ── UI ────────────────────────────────────────────────────────────────────

    def _setup_ui(self) -> None:
        self.setObjectName("RobotJogWidget")
        self.setStyleSheet(f"""
            QFrame#RobotJogWidget {{
                background-color: {BG_COLOR};
                border: 1px solid {BORDER};
                border-radius: 6px;
            }}
        """)
        root = QVBoxLayout(self)
        root.setSpacing(14)
        root.setContentsMargins(14, 14, 14, 14)

        root.addWidget(self._build_position_display())
        root.addWidget(self._build_divider())

        self._tabs = QTabWidget()
        self._tabs.setStyleSheet(f"""
            QTabWidget::pane {{
                border: 1px solid {BORDER};
                border-radius: 4px;
                top: -1px;
            }}
            QTabBar::tab {{
                background: {SECONDARY_BG};
                color: {TEXT_COLOR};
                padding: 6px 18px;
                border: 1px solid {BORDER};
                border-bottom: none;
                border-top-left-radius: 4px;
                border-top-right-radius: 4px;
                font-size: 12px;
                font-weight: 600;
            }}
            QTabBar::tab:selected {{
                background: {PRIMARY};
                color: white;
                border-color: {PRIMARY};
            }}
            QTabBar::tab:hover:!selected {{ background: {SECONDARY_HOVER}; }}
        """)
        self._tabs.addTab(self._build_cartesian_tab(), "Cartesian")
        self._tabs.addTab(self._build_joint_tab(), "Joint")
        root.addWidget(self._tabs, 1)

        root.addWidget(self._build_divider())
        root.addLayout(self._build_bottom_row())

    def _build_cartesian_tab(self) -> QWidget:
        page = QWidget()
        layout = QVBoxLayout(page)
        layout.setSpacing(14)
        layout.setContentsMargins(4, 10, 4, 4)

        layout.addWidget(self._build_slider_row(
            "Linear Step", _LINEAR_STEPS, "mm", "_linear_slider", "_linear_label", 2))
        layout.addWidget(self._build_divider())
        layout.addLayout(self._build_linear_section())

        layout.addSpacing(12)
        layout.addWidget(self._build_divider())
        layout.addSpacing(4)

        layout.addWidget(self._build_slider_row(
            "Rotation Step", _ROTATION_STEPS, "°", "_rotation_slider", "_rotation_label", 2))
        layout.addWidget(self._build_divider())
        layout.addLayout(self._build_rotational_section())
        return page

    def _build_joint_tab(self) -> QWidget:
        page = QWidget()
        layout = QVBoxLayout(page)
        layout.setSpacing(14)
        layout.setContentsMargins(4, 10, 4, 4)

        layout.addWidget(self._build_slider_row(
            "Joint Step", _JOINT_STEPS, "°", "_joint_slider", "_joint_step_label", 3))
        layout.addWidget(self._build_divider())
        layout.addWidget(self._build_joint_position_display())
        layout.addWidget(self._build_divider())
        layout.addLayout(self._build_joint_section())
        layout.addStretch(1)
        return page

    def _build_position_display(self) -> QFrame:
        frame = QFrame()
        frame.setStyleSheet(f"""
            QFrame {{
                background: white;
                border: 1px solid {BORDER};
                border-radius: 4px;
            }}
        """)
        outer = QVBoxLayout(frame)
        outer.setContentsMargins(10, 8, 10, 8)
        outer.setSpacing(6)

        self._position_title_label = QLabel()
        self._position_title_label.setStyleSheet(f"font-size: 11px; font-weight: 700; color: {TEXT_COLOR};")
        outer.addWidget(self._position_title_label)

        self._pos_labels: dict[str, QLabel] = {}
        grid = QGridLayout()
        grid.setSpacing(4)
        grid.setHorizontalSpacing(8)

        for i, (name, _) in enumerate(_POS_AXES):
            row, col = divmod(i, 3)

            name_lbl = QLabel(f"{name}:")
            name_lbl.setStyleSheet("font-size: 10px; font-weight: 600; color: #888;")
            name_lbl.setAlignment(Qt.AlignmentFlag.AlignRight | Qt.AlignmentFlag.AlignVCenter)

            val_lbl = QLabel("—")
            val_lbl.setStyleSheet(
                f"font-size: 11px; font-weight: 600; font-family: monospace;"
                f" color: {TEXT_COLOR}; min-width: 62px;"
            )
            val_lbl.setAlignment(Qt.AlignmentFlag.AlignLeft | Qt.AlignmentFlag.AlignVCenter)

            grid.addWidget(name_lbl, row, col * 2)
            grid.addWidget(val_lbl,  row, col * 2 + 1)
            self._pos_labels[name] = val_lbl

        outer.addLayout(grid)
        return frame

    def _build_joint_position_display(self) -> QFrame:
        frame = QFrame()
        frame.setStyleSheet(f"""
            QFrame {{
                background: white;
                border: 1px solid {BORDER};
                border-radius: 4px;
            }}
        """)
        outer = QVBoxLayout(frame)
        outer.setContentsMargins(10, 8, 10, 8)
        outer.setSpacing(6)

        self._joint_positions_title_label = QLabel()
        self._joint_positions_title_label.setStyleSheet(f"font-size: 11px; font-weight: 700; color: {TEXT_COLOR};")
        outer.addWidget(self._joint_positions_title_label)

        self._joint_pos_labels: dict[str, QLabel] = {}
        grid = QGridLayout()
        grid.setSpacing(4)
        grid.setHorizontalSpacing(8)

        for i, name in enumerate(_JOINT_NAMES):
            row, col = divmod(i, 3)

            name_lbl = QLabel(f"{name}:")
            name_lbl.setStyleSheet("font-size: 10px; font-weight: 600; color: #888;")
            name_lbl.setAlignment(Qt.AlignmentFlag.AlignRight | Qt.AlignmentFlag.AlignVCenter)

            val_lbl = QLabel("—")
            val_lbl.setStyleSheet(
                f"font-size: 11px; font-weight: 600; font-family: monospace;"
                f" color: {TEXT_COLOR}; min-width: 62px;"
            )
            val_lbl.setAlignment(Qt.AlignmentFlag.AlignLeft | Qt.AlignmentFlag.AlignVCenter)

            grid.addWidget(name_lbl, row, col * 2)
            grid.addWidget(val_lbl,  row, col * 2 + 1)
            self._joint_pos_labels[name] = val_lbl

        outer.addLayout(grid)
        return frame

    def set_position(self, pos: list) -> None:
        if not pos or len(pos) < 6:
            for lbl in self._pos_labels.values():
                lbl.setText("—")
            return
        for name, idx in _POS_AXES:
            self._pos_labels[name].setText(f"{pos[idx]:.3f}")

    def set_joint_position(self, joints: list) -> None:
        if isinstance(joints, str) or not isinstance(joints, (list, tuple)) or len(joints) < len(_JOINT_NAMES):
            for lbl in self._joint_pos_labels.values():
                lbl.setText("—")
            return
        try:
            values = [float(value) for value in joints[:len(_JOINT_NAMES)]]
        except (TypeError, ValueError):
            for lbl in self._joint_pos_labels.values():
                lbl.setText("—")
            return
        for i, name in enumerate(_JOINT_NAMES):
            self._joint_pos_labels[name].setText(f"{values[i]:.3f}")

    def set_frame_options(self, names: Sequence[object], default: Optional[str] = None) -> None:
        """Populate the frame selector combo box."""
        if self._frame_combo is None:
            return
        self._frame_combo.blockSignals(True)
        self._frame_combo.clear()
        values: list[str] = []
        for item in names:
            if isinstance(item, tuple) and len(item) >= 2:
                label = str(item[0])
                value = str(item[1])
                self._frame_combo.addItem(label, value)
                values.append(value)
            else:
                value = str(item)
                self._frame_combo.addItem(value, value)
                values.append(value)
        if default and default in values:
            index = self._frame_combo.findData(default)
            if index >= 0:
                self._frame_combo.setCurrentIndex(index)
        self._frame_combo.blockSignals(False)
        self.enable_frame_selector(bool(values))

    def enable_frame_selector(self, enabled: bool) -> None:
        """Show or hide the optional frame selector."""
        is_visible = bool(enabled)
        if self._frame_label is not None:
            self._frame_label.setVisible(is_visible)
        if self._frame_combo is not None:
            self._frame_combo.setVisible(is_visible)

    def set_frame(self, name: str) -> None:
        """Programmatically select a frame without emitting frame_changed."""
        if self._frame_combo is None:
            return
        self._frame_combo.blockSignals(True)
        index = self._frame_combo.findData(name)
        if index >= 0:
            self._frame_combo.setCurrentIndex(index)
        else:
            self._frame_combo.setCurrentText(name)
        self._frame_combo.blockSignals(False)

    def get_frame(self) -> str:
        """Return the currently selected frame name, or empty string if none."""
        if self._frame_combo is None or self._frame_combo.count() == 0:
            return ""
        data = self._frame_combo.currentData()
        return str(data) if data is not None else self._frame_combo.currentText()

    def _on_frame_combo_changed(self, text: str) -> None:
        if text:
            self.frame_changed.emit(text)


    def _build_slider_row(
        self,
        label_text: str,
        steps: list[float],
        unit: str,
        slider_attr: str,
        label_attr: str,
        default_idx: int,
    ) -> QFrame:
        frame = QFrame()
        layout = QHBoxLayout(frame)
        layout.setContentsMargins(0, 0, 0, 0)
        layout.setSpacing(10)

        lbl = QLabel(f"{label_text}:")
        lbl.setStyleSheet(f"font-size: 12px; font-weight: 600; color: {TEXT_COLOR};")
        lbl.setFixedWidth(112)
        if slider_attr == "_linear_slider":
            self._linear_title_label = lbl
        elif slider_attr == "_rotation_slider":
            self._rotation_title_label = lbl
        elif slider_attr == "_joint_slider":
            self._joint_step_title_label = lbl

        slider = QSlider(Qt.Orientation.Horizontal)
        slider.setMinimum(0)
        slider.setMaximum(len(steps) - 1)
        slider.setValue(default_idx)
        slider.setTickInterval(1)
        slider.setTickPosition(QSlider.TickPosition.TicksBelow)
        slider.setStyleSheet(_SLIDER_STYLE)
        setattr(self, slider_attr, slider)

        val_label = QLabel(f"{steps[default_idx]} {unit}")
        val_label.setFixedWidth(64)
        val_label.setAlignment(Qt.AlignmentFlag.AlignLeft | Qt.AlignmentFlag.AlignVCenter)
        val_label.setStyleSheet(f"font-size: 12px; color: {TEXT_COLOR};")
        setattr(self, label_attr, val_label)

        slider.valueChanged.connect(
            partial(self._on_slider_changed, steps, unit, val_label)
        )

        layout.addWidget(lbl)
        layout.addWidget(slider, 1)
        layout.addWidget(val_label)
        return frame

    def _build_linear_section(self) -> QVBoxLayout:
        layout = self._build_axes_section(
            title="Linear",
            vert_label="Z",
            vert_plus_attr="btn_z_plus", vert_plus_text="Z+",
            vert_minus_attr="btn_z_minus", vert_minus_text="Z−",
            grid_label="X / Y",
            top_attr="btn_y_plus", top_text="Y+",
            left_attr="btn_x_minus", left_text="X−",
            right_attr="btn_x_plus", right_text="X+",
            bottom_attr="btn_y_minus", bottom_text="Y−",
        )

        self._invert_z_btn = QPushButton()
        self._invert_z_btn.setCheckable(True)
        self._invert_z_btn.setFixedHeight(36)
        self._invert_z_btn.setStyleSheet(f"""
            QPushButton {{
                background-color: {SECONDARY_BG};
                color: {TEXT_COLOR};
                border: 1px solid {BORDER};
                border-radius: 4px;
                font-size: 11px;
                font-weight: 600;
                padding: 0 14px;
            }}
            QPushButton:checked {{
                background-color: {PRIMARY};
                color: white;
                border-color: {PRIMARY};
            }}
            QPushButton:hover:!checked {{ background-color: {SECONDARY_HOVER}; }}
        """)

        row = QHBoxLayout()
        row.setContentsMargins(0, 4, 0, 0)
        row.addStretch(1)
        row.addWidget(self._invert_z_btn)
        row.addStretch(1)
        layout.addLayout(row)
        return layout

    def _build_rotational_section(self) -> QVBoxLayout:
        return self._build_axes_section(
            title="Rotational",
            vert_label="RZ",
            vert_plus_attr="btn_rz_plus",   vert_plus_text="RZ+",
            vert_minus_attr="btn_rz_minus", vert_minus_text="RZ−",
            grid_label="RX / RY",
            top_attr="btn_ry_plus",    top_text="RY+",
            left_attr="btn_rx_minus",  left_text="RX−",
            right_attr="btn_rx_plus",  right_text="RX+",
            bottom_attr="btn_ry_minus", bottom_text="RY−",
        )

    def _build_axes_section(
        self,
        title: str,
        vert_label: str,
        vert_plus_attr: str,  vert_plus_text: str,
        vert_minus_attr: str, vert_minus_text: str,
        grid_label: str,
        top_attr: str,    top_text: str,
        left_attr: str,   left_text: str,
        right_attr: str,  right_text: str,
        bottom_attr: str, bottom_text: str,
    ) -> QVBoxLayout:
        outer = QVBoxLayout()
        outer.setSpacing(8)

        header = QLabel()
        header.setProperty("translation_source", title)
        header.setAlignment(Qt.AlignmentFlag.AlignCenter)
        header.setStyleSheet(
            f"font-size: 11px; font-weight: 700; color: {TEXT_COLOR}; letter-spacing: 0.5px;"
        )
        if title == "Linear":
            self._linear_section_label = header
        elif title == "Rotational":
            self._rotational_section_label = header
        outer.addWidget(header)

        body = QHBoxLayout()
        body.setSpacing(18)
        body.addStretch(1)

        # Vertical axis (Z / RZ)
        vert_col = QVBoxLayout()
        vert_col.setAlignment(Qt.AlignmentFlag.AlignCenter)
        vert_col.addStretch(1)
        vert_col.addWidget(self._axis_label(vert_label))
        plus_btn  = self._make_jog_btn(vert_plus_text,  primary=True)
        minus_btn = self._make_jog_btn(vert_minus_text, primary=True)
        setattr(self, vert_plus_attr,  plus_btn)
        setattr(self, vert_minus_attr, minus_btn)
        vert_col.addWidget(plus_btn)
        vert_col.addSpacing(8)
        vert_col.addWidget(minus_btn)
        vert_col.addStretch(1)
        body.addLayout(vert_col)

        body.addSpacing(8)
        body.addWidget(self._build_vertical_divider())
        body.addSpacing(8)

        # Grid axes (XY / RXRY)
        grid_col = QVBoxLayout()
        grid_col.setSpacing(4)
        grid_col.addWidget(self._axis_label(grid_label))

        grid = QGridLayout()
        grid.setSpacing(10)
        top_btn    = self._make_jog_btn(top_text)
        left_btn   = self._make_jog_btn(left_text)
        right_btn  = self._make_jog_btn(right_text)
        bottom_btn = self._make_jog_btn(bottom_text)
        setattr(self, top_attr,    top_btn)
        setattr(self, left_attr,   left_btn)
        setattr(self, right_attr,  right_btn)
        setattr(self, bottom_attr, bottom_btn)
        grid.addWidget(top_btn,    0, 1)
        grid.addWidget(left_btn,   1, 0)
        grid.addItem(
            QSpacerItem(50, 50, QSizePolicy.Policy.Fixed, QSizePolicy.Policy.Fixed), 1, 1
        )
        grid.addWidget(right_btn,  1, 2)
        grid.addWidget(bottom_btn, 2, 1)
        grid_col.addLayout(grid)

        body.addLayout(grid_col)
        body.addStretch(1)
        outer.addLayout(body)
        return outer

    def _build_joint_section(self) -> QVBoxLayout:
        outer = QVBoxLayout()
        outer.setSpacing(10)

        self._joints_section_label = QLabel()
        header = self._joints_section_label
        header.setAlignment(Qt.AlignmentFlag.AlignCenter)
        header.setStyleSheet(
            f"font-size: 11px; font-weight: 700; color: {TEXT_COLOR}; letter-spacing: 0.5px;"
        )
        outer.addWidget(header)

        grid = QGridLayout()
        grid.setSpacing(10)
        grid.setColumnStretch(0, 0)
        grid.setColumnStretch(1, 1)
        grid.setColumnStretch(2, 1)

        for row, name in enumerate(_JOINT_NAMES):
            name_lbl = QLabel(name)
            name_lbl.setFixedWidth(34)
            name_lbl.setAlignment(Qt.AlignmentFlag.AlignCenter)
            name_lbl.setStyleSheet(f"font-size: 12px; font-weight: 700; color: {TEXT_COLOR};")

            minus_btn = self._make_jog_btn(f"{name}−", primary=True)
            plus_btn  = self._make_jog_btn(f"{name}+", primary=True)
            minus_btn.setFixedSize(84, 44)
            plus_btn.setFixedSize(84, 44)

            key_minus = f"{name.lower()}_minus"
            key_plus  = f"{name.lower()}_plus"
            self._joint_btns[key_minus] = minus_btn
            self._joint_btns[key_plus]  = plus_btn

            grid.addWidget(name_lbl,  row, 0)
            grid.addWidget(minus_btn, row, 1)
            grid.addWidget(plus_btn,  row, 2)

        outer.addLayout(grid)
        return outer

    def _build_bottom_row(self) -> QVBoxLayout:
        layout = QVBoxLayout()
        layout.setSpacing(8)

        mode_row = QHBoxLayout()
        mode_row.setSpacing(8)
        mode_row.setAlignment(Qt.AlignmentFlag.AlignCenter)

        self._mode_label = QLabel()
        self._mode_label.setStyleSheet(f"font-size: 11px; font-weight: 600; color: {TEXT_COLOR};")
        mode_row.addWidget(self._mode_label)

        mode_selector = QFrame()
        mode_selector.setObjectName("JogModeSelector")
        mode_selector.setStyleSheet(f"""
            QFrame#JogModeSelector {{
                background: {SECONDARY_BG};
                border: 1px solid {BORDER};
                border-radius: 8px;
            }}
            QFrame#JogModeSelector QPushButton {{
                background: transparent;
                color: {TEXT_COLOR};
                border: none;
                border-radius: 6px;
                min-height: 44px;
                min-width: 88px;
                padding: 0 14px;
                font-size: 11pt;
                font-weight: bold;
            }}
            QFrame#JogModeSelector QPushButton:hover:!checked {{
                background: {SECONDARY_HOVER};
            }}
            QFrame#JogModeSelector QPushButton:checked {{
                background: {PRIMARY};
                color: white;
            }}
        """)
        selector_layout = QHBoxLayout(mode_selector)
        selector_layout.setContentsMargins(3, 3, 3, 3)
        selector_layout.setSpacing(3)

        self._step_mode_btn = QPushButton()
        self._step_mode_btn.setCheckable(True)
        self._step_mode_btn.setCursor(Qt.CursorShape.PointingHandCursor)
        self._servo_mode_btn = QPushButton()
        self._servo_mode_btn.setCheckable(True)
        self._servo_mode_btn.setCursor(Qt.CursorShape.PointingHandCursor)
        selector_layout.addWidget(self._step_mode_btn)
        selector_layout.addWidget(self._servo_mode_btn)

        self._jog_mode_group = QButtonGroup(self)
        self._jog_mode_group.setExclusive(True)
        self._jog_mode_group.addButton(self._step_mode_btn, 0)
        self._jog_mode_group.addButton(self._servo_mode_btn, 1)
        self._step_mode_btn.setChecked(True)
        self._jog_mode_group.idClicked.connect(self._on_jog_mode_selected)
        mode_row.addWidget(mode_selector)
        mode_row.addStretch(1)
        layout.addLayout(mode_row)

        frame_row = QHBoxLayout()
        frame_row.setSpacing(8)

        self._frame_label = QLabel("Frame:")
        self._frame_label.setStyleSheet(f"font-size: 11px; font-weight: 600; color: {TEXT_COLOR};")
        frame_row.addWidget(self._frame_label)

        self._frame_combo = QComboBox()
        self._frame_combo.setFixedHeight(32)
        self._frame_combo.setStyleSheet(f"""
            QComboBox {{
                border: 1px solid {BORDER};
                border-radius: 4px;
                padding: 2px 8px;
                font-size: 11px;
                background: white;
                color: {TEXT_COLOR};
            }}
            QComboBox::drop-down {{ border: none; }}
        """)
        self._frame_combo.currentTextChanged.connect(self._on_frame_combo_changed)
        frame_row.addWidget(self._frame_combo, 1)
        layout.addLayout(frame_row)
        self.enable_frame_selector(False)
        return layout

    @staticmethod
    def _build_divider() -> QFrame:
        line = QFrame()
        line.setFrameShape(QFrame.Shape.HLine)
        line.setStyleSheet(f"color: {BORDER};")
        return line

    @staticmethod
    def _build_vertical_divider() -> QFrame:
        line = QFrame()
        line.setFrameShape(QFrame.Shape.VLine)
        line.setStyleSheet(f"color: {BORDER};")
        return line

    @staticmethod
    def _axis_label(text: str) -> QLabel:
        lbl = QLabel(text)
        lbl.setAlignment(Qt.AlignmentFlag.AlignCenter)
        lbl.setStyleSheet("font-size: 11px; color: #888; margin-bottom: 2px;")
        return lbl

    def _make_jog_btn(self, text: str, primary: bool = False) -> QPushButton:
        btn = QPushButton(text)
        btn.setFixedSize(54, 54)
        if primary:
            btn.setStyleSheet(f"""
                QPushButton {{
                    background-color: {PRIMARY};
                    color: white;
                    border: none;
                    border-radius: 6px;
                    font-size: 12px;
                    font-weight: 700;
                }}
                QPushButton:hover   {{ background-color: {PRIMARY_DARK}; }}
                QPushButton:pressed {{ background-color: {PRIMARY_DARK}; }}
            """)
        else:
            btn.setStyleSheet(f"""
                QPushButton {{
                    background-color: {SECONDARY_BG};
                    color: {TEXT_COLOR};
                    border: 1px solid {BORDER};
                    border-radius: 6px;
                    font-size: 12px;
                    font-weight: 700;
                }}
                QPushButton:hover   {{ background-color: {SECONDARY_HOVER}; }}
                QPushButton:pressed {{ background-color: {SECONDARY_HOVER}; border-color: {PRIMARY}; }}
            """)
        return btn

    # ── Timers & connections ──────────────────────────────────────────────────

    def _setup_timers(self) -> None:
        for key, axis, direction in _AXES:
            self._axis_map[key] = (axis, direction)
            timer = QTimer(self)
            timer.setInterval(_JOG_INTERVAL_MS)
            timer.timeout.connect(partial(self._perform_jog, key))
            self._timers[key] = timer

        btn_key_pairs = [
            (self.btn_x_plus,   "x_plus"),
            (self.btn_x_minus,  "x_minus"),
            (self.btn_y_plus,   "y_plus"),
            (self.btn_y_minus,  "y_minus"),
            (self.btn_z_plus,   "z_plus"),
            (self.btn_z_minus,  "z_minus"),
            (self.btn_rx_plus,  "rx_plus"),
            (self.btn_rx_minus, "rx_minus"),
            (self.btn_ry_plus,  "ry_plus"),
            (self.btn_ry_minus, "ry_minus"),
            (self.btn_rz_plus,  "rz_plus"),
            (self.btn_rz_minus, "rz_minus"),
        ]
        for btn, key in btn_key_pairs:
            btn.pressed.connect(partial(self._on_jog_press, key))
            btn.released.connect(partial(self._on_jog_release, key))

        for name in _JOINT_NAMES:
            for direction, suffix in (("Plus", "plus"), ("Minus", "minus")):
                key = f"{name.lower()}_{suffix}"
                self._joint_axis_map[key] = (name, direction)
                timer = QTimer(self)
                timer.setInterval(_JOG_INTERVAL_MS)
                timer.timeout.connect(partial(self._perform_joint_jog, key))
                self._joint_timers[key] = timer

        for key, btn in self._joint_btns.items():
            btn.pressed.connect(partial(self._on_joint_jog_press, key))
            btn.released.connect(partial(self._on_joint_jog_release, key))

    # ── Slots ─────────────────────────────────────────────────────────────────

    def _on_slider_changed(self, steps: list[float], unit: str, label: QLabel, idx: int) -> None:
        if self._current_jog_command() == "SERVO_JOG":
            if label is getattr(self, "_linear_label", None):
                unit = "mm/s"
            elif label is getattr(self, "_rotation_label", None):
                unit = "°/s"
        label.setText(f"{steps[idx]} {unit}")

    def _on_jog_press(self, key: str) -> None:
        self.jog_started.emit(key)
        self._perform_jog(key)
        if self._current_jog_command() != "SERVO_JOG":
            self._timers[key].start()

    def _on_jog_release(self, key: str) -> None:
        self._timers[key].stop()
        if self._current_jog_command() == "SERVO_JOG":
            self.jog_stopped.emit(key)

    def _perform_jog(self, key: str) -> None:
        axis, direction = self._axis_map[key]
        if axis in _LINEAR_AXES:
            step = _LINEAR_STEPS[self._linear_slider.value()]
        else:
            step = _ROTATION_STEPS[self._rotation_slider.value()]

        if (
            self._current_jog_command() != "SERVO_JOG"
            and axis == "Z"
            and self._invert_z_btn.isChecked()
        ):
            direction = "Minus" if direction == "Plus" else "Plus"

        self.jog_requested.emit(self._current_jog_command(), axis, direction, step)

    def _current_jog_command(self) -> str:
        if self._jog_mode_group is None:
            return "JOG_ROBOT"
        return "SERVO_JOG" if self._jog_mode_group.checkedId() == 1 else "JOG_ROBOT"

    def _on_jog_mode_selected(self, _button_id: int) -> None:
        self._on_jog_mode_changed()

    def _on_jog_mode_changed(self) -> None:
        servo_mode = self._current_jog_command() == "SERVO_JOG"
        if self._linear_title_label is not None:
            source = "Linear Speed" if servo_mode else "Linear Step"
            self._linear_title_label.setText(f"{self._t(source)}:")
        if self._rotation_title_label is not None:
            source = "Rotation Speed" if servo_mode else "Rotation Step"
            self._rotation_title_label.setText(f"{self._t(source)}:")
        self._on_slider_changed(_LINEAR_STEPS, "mm", self._linear_label, self._linear_slider.value())
        self._on_slider_changed(_ROTATION_STEPS, "°", self._rotation_label, self._rotation_slider.value())

    def _on_joint_jog_press(self, key: str) -> None:
        self.joint_jog_started.emit(key)
        self._perform_joint_jog(key)
        self._joint_timers[key].start()

    def _on_joint_jog_release(self, key: str) -> None:
        self._joint_timers[key].stop()
        self.joint_jog_stopped.emit(key)

    def _perform_joint_jog(self, key: str) -> None:
        joint, direction = self._joint_axis_map[key]
        step = _JOINT_STEPS[self._joint_slider.value()]
        self.joint_jog_requested.emit("JOG_JOINT", joint, direction, step)

    def retranslateUi(self) -> None:
        self._tabs.setTabText(0, self._t("Cartesian"))
        self._tabs.setTabText(1, self._t("Joint"))
        self._position_title_label.setText(self._t("Current Position"))
        self._joint_positions_title_label.setText(self._t("Joint Positions"))
        self._joint_step_title_label.setText(f"{self._t('Joint Step')}:")
        self._linear_section_label.setText(self._t("Linear"))
        self._rotational_section_label.setText(self._t("Rotational"))
        self._joints_section_label.setText(self._t("Joints"))
        self._invert_z_btn.setText(f"⇅  {self._t('Invert Z')}")
        self._mode_label.setText(f"{self._t('Mode')}:")
        self._frame_label.setText(f"{self._t('Frame')}:")
        self._step_mode_btn.setText(self._t("Step"))
        self._servo_mode_btn.setText(self._t("Servo"))
        self._on_jog_mode_changed()

    def changeEvent(self, event) -> None:
        if event.type() == QEvent.Type.LanguageChange:
            self.retranslateUi()
        super().changeEvent(event)

    @staticmethod
    def _t(text: str) -> str:
        translated = QCoreApplication.translate("RobotJogWidget", text)
        return translated or text


if __name__ == "__main__":
    import sys

    from PyQt6.QtWidgets import QApplication, QMainWindow

    app = QApplication(sys.argv)

    widget = RobotJogWidget()
    widget.jog_requested.connect(
        lambda cmd, axis, direction, step: print(f"JOG: {cmd} {axis} {direction} {step}")
    )
    widget.jog_started.connect(lambda key: print(f"started: {key}"))
    widget.jog_stopped.connect(lambda key: print(f"stopped: {key}"))
    widget.frame_changed.connect(lambda name: print(f"frame changed: {name}"))

    widget.joint_jog_requested.connect(
        lambda cmd, joint, direction, step: print(f"JOINT JOG: {cmd} {joint} {direction} {step}")
    )
    widget.joint_jog_started.connect(lambda key: print(f"joint started: {key}"))
    widget.joint_jog_stopped.connect(lambda key: print(f"joint stopped: {key}"))

    widget.set_position([10.0, -20.5, 3.25, 0.0, 0.0, 90.0])
    widget.set_joint_position([12.5, -45.0, 30.0, 0.0, 60.0, 0.0])
    widget.set_frame_options(["World", ("Base", "BASE"), "Tool"], default="BASE")

    window = QMainWindow()
    window.setCentralWidget(widget)
    window.setWindowTitle("RobotJogWidget — standalone test")
    window.resize(520, 920)
    window.show()

    sys.exit(app.exec())
