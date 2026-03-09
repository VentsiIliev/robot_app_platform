from functools import partial

from PyQt6.QtCore import Qt, QTimer, pyqtSignal
from PyQt6.QtWidgets import (
    QFrame, QVBoxLayout, QHBoxLayout, QGridLayout,
    QPushButton, QLabel, QSlider, QSizePolicy, QSpacerItem,
)

from pl_gui.settings.settings_view.styles import (
    PRIMARY, PRIMARY_DARK, BG_COLOR, BORDER,
    TEXT_COLOR, SECONDARY_BG, SECONDARY_HOVER,
)

_LINEAR_STEPS:   list[float] = [0.1, 0.5, 1.0, 5.0, 10.0, 50.0]
_ROTATION_STEPS: list[float] = [0.1, 0.5, 1.0, 5.0, 10.0, 45.0, 90.0]
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

    def __init__(self, parent=None):
        super().__init__(parent)
        self._timers:   dict[str, QTimer]       = {}
        self._axis_map: dict[str, tuple[str, str]] = {}
        self._setup_ui()
        self._setup_timers()

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


        root.addWidget(self._build_slider_row("Linear Step", _LINEAR_STEPS, "mm", "_linear_slider", "_linear_label", 2))
        root.addWidget(self._build_divider())
        root.addLayout(self._build_linear_section())

        root.addSpacing(12)  # ← gap between the two blocks
        root.addWidget(self._build_divider())
        root.addSpacing(4)

        root.addWidget(
            self._build_slider_row("Rotation Step", _ROTATION_STEPS, "°", "_rotation_slider", "_rotation_label", 2))
        root.addWidget(self._build_divider())
        root.addLayout(self._build_rotational_section())
        root.addWidget(self._build_divider())
        root.addLayout(self._build_bottom_row())

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

        title = QLabel("Current Position")
        title.setStyleSheet(f"font-size: 11px; font-weight: 700; color: {TEXT_COLOR};")
        outer.addWidget(title)

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

    def set_position(self, pos: list) -> None:
        if not pos or len(pos) < 6:
            for lbl in self._pos_labels.values():
                lbl.setText("—")
            return
        for name, idx in _POS_AXES:
            self._pos_labels[name].setText(f"{pos[idx]:.3f}")


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
        lbl.setFixedWidth(100)

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

        self._invert_z_btn = QPushButton("⇅  Invert Z")
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

        header = QLabel(title)
        header.setAlignment(Qt.AlignmentFlag.AlignCenter)
        header.setStyleSheet(
            f"font-size: 11px; font-weight: 700; color: {TEXT_COLOR}; letter-spacing: 0.5px;"
        )
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

    def _build_bottom_row(self) -> QHBoxLayout:
        layout = QHBoxLayout()
        layout.setAlignment(Qt.AlignmentFlag.AlignCenter)

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

    # ── Slots ─────────────────────────────────────────────────────────────────

    @staticmethod
    def _on_slider_changed(steps: list[float], unit: str, label: QLabel, idx: int) -> None:
        label.setText(f"{steps[idx]} {unit}")

    def _on_jog_press(self, key: str) -> None:
        self.jog_started.emit(key)
        self._perform_jog(key)
        self._timers[key].start()

    def _on_jog_release(self, key: str) -> None:
        self._timers[key].stop()
        self.jog_stopped.emit(key)

    def _perform_jog(self, key: str) -> None:
        axis, direction = self._axis_map[key]
        if axis in _LINEAR_AXES:
            step = _LINEAR_STEPS[self._linear_slider.value()]
        else:
            step = _ROTATION_STEPS[self._rotation_slider.value()]

        if axis == "Z" and self._invert_z_btn.isChecked():
            direction = "Minus" if direction == "Plus" else "Plus"

        self.jog_requested.emit("JOG_ROBOT", axis, direction, step)



