#!/usr/bin/env python3
from __future__ import annotations

import json
import math
import sys
from dataclasses import dataclass, field
from typing import Iterable

from PyQt6.QtCore import QPointF, QRectF, QSize, Qt
from PyQt6.QtGui import QColor, QBrush, QPainter, QPainterPath, QPen
from PyQt6.QtWidgets import (
    QApplication,
    QDoubleSpinBox,
    QGridLayout,
    QGroupBox,
    QHBoxLayout,
    QLabel,
    QPushButton,
    QPlainTextEdit,
    QToolTip,
    QVBoxLayout,
    QWizard,
    QWizardPage,
    QWidget,
)

from pl_gui.settings.settings_view.styles import (
    ACTION_BTN_STYLE,
    BG_COLOR,
    BORDER,
    GHOST_BTN_STYLE,
    GROUP_STYLE,
    LABEL_STYLE,
    PRIMARY,
    PRIMARY_LIGHT,
    SECONDARY_BG,
    TERTIARY_BG,
    TEXT_COLOR,
)
from src.applications.base.robot_jog_widget import RobotJogWidget
from src.applications.base.drawer_toggle import DrawerToggle
from src.applications.base.styled_message_box import ask_yes_no
from pl_gui.utils.utils_widgets.wizards import ConfigurableWizard


AXES = ("x", "y", "z")
ROT_AXES = ("rx", "ry", "rz")
LINEAR_JOG_BUTTONS = (
    "btn_x_plus",
    "btn_x_minus",
    "btn_y_plus",
    "btn_y_minus",
    "btn_z_plus",
    "btn_z_minus",
)
ROTATION_JOG_BUTTONS = (
    "btn_rx_plus",
    "btn_rx_minus",
    "btn_ry_plus",
    "btn_ry_minus",
    "btn_rz_plus",
    "btn_rz_minus",
)
ROTATION_PLANES = {
    "rx": (("y", "z"), "x"),
    "ry": (("x", "z"), "y"),
    "rz": (("x", "y"), "z"),
}


_SPIN_STYLE = f"""
QDoubleSpinBox {{
    background: white;
    color: {TEXT_COLOR};
    border: 1px solid {BORDER};
    border-radius: 6px;
    padding: 4px 8px;
    font-size: 10pt;
}}
QDoubleSpinBox:focus {{
    border: 2px solid {PRIMARY};
}}
"""

_SUMMARY_STYLE = f"""
QLabel {{
    background: {PRIMARY_LIGHT};
    color: {TEXT_COLOR};
    border: 1px solid {BORDER};
    border-radius: 8px;
    padding: 8px 12px;
    font-size: 11pt;
    font-weight: bold;
}}
"""

_OUTPUT_STYLE = f"""
QPlainTextEdit {{
    background: white;
    color: {TEXT_COLOR};
    border: 1px solid {BORDER};
    border-radius: 8px;
    padding: 10px;
    font-size: 10pt;
}}
"""

_RESULT_VALUE_STYLE = f"""
QLabel {{
    background: white;
    color: {TEXT_COLOR};
    border: 1px solid {BORDER};
    border-radius: 8px;
    padding: 10px 12px;
    font-size: 13pt;
    font-weight: bold;
}}
"""

_READOUT_VALUE_STYLE = f"""
QLabel {{
    background: {TERTIARY_BG};
    color: {TEXT_COLOR};
    border: 1px solid {BORDER};
    border-radius: 6px;
    padding: 4px 8px;
    font-size: 10pt;
    font-weight: bold;
}}
"""

_WARNING_STYLE = f"""
QLabel {{
    background: {SECONDARY_BG};
    color: {TEXT_COLOR};
    border: 1px solid {BORDER};
    border-radius: 8px;
    padding: 8px 12px;
    font-size: 10pt;
}}
"""

_STEP_TITLE_STYLE = f"""
QLabel {{
    color: {TEXT_COLOR};
    background: transparent;
    font-size: 16pt;
    font-weight: 700;
}}
"""

_INFO_BUTTON_STYLE = f"""
QPushButton {{
    background: {PRIMARY_LIGHT};
    color: {PRIMARY};
    border: 1px solid {BORDER};
    border-radius: 11px;
    font-size: 10pt;
    font-weight: 700;
    min-width: 22px;
    max-width: 22px;
    min-height: 22px;
    max-height: 22px;
}}
QPushButton:hover {{
    border-color: {PRIMARY};
}}
"""

_GUIDE_BODY = QColor(214, 214, 214)
_GUIDE_BODY_LINE = QColor(183, 183, 183)
_GUIDE_DETAIL = QColor(142, 142, 142)
_GUIDE_JOINT = QColor(69, 69, 69)
_GUIDE_GREEN = QColor(47, 128, 86)
_GUIDE_RED = QColor(200, 67, 67)
_GUIDE_BLUE = QColor(35, 102, 184)
_GUIDE_ORANGE = QColor(217, 136, 0)
_GUIDE_MARKER = QColor(85, 213, 106)
_GUIDE_CENTER = QColor(246, 164, 0)
_GUIDE_CENTER_GLOW = QColor(245, 163, 22, 190)


def _action_button(text: str) -> QPushButton:
    button = QPushButton(text)
    button.setStyleSheet(ACTION_BTN_STYLE)
    button.setCursor(Qt.CursorShape.PointingHandCursor)
    return button


def _ghost_button(text: str) -> QPushButton:
    button = QPushButton(text)
    button.setStyleSheet(GHOST_BTN_STYLE)
    button.setCursor(Qt.CursorShape.PointingHandCursor)
    return button


def _label(text: str) -> QLabel:
    label = QLabel(text)
    label.setStyleSheet(LABEL_STYLE)
    return label


@dataclass(frozen=True)
class Pose6D:
    x: float
    y: float
    z: float
    rx: float
    ry: float
    rz: float

    def position_delta(self, other: "Pose6D") -> dict[str, float]:
        return {
            "x": other.x - self.x,
            "y": other.y - self.y,
            "z": other.z - self.z,
        }

    def rotation_delta(self, other: "Pose6D") -> dict[str, float]:
        return {
            "rx": unwrap_degrees(getattr(self, "rx"), getattr(other, "rx")) - self.rx,
            "ry": unwrap_degrees(getattr(self, "ry"), getattr(other, "ry")) - self.ry,
            "rz": unwrap_degrees(getattr(self, "rz"), getattr(other, "rz")) - self.rz,
        }

    def as_list(self) -> list[float]:
        return [self.x, self.y, self.z, self.rx, self.ry, self.rz]


@dataclass(frozen=True)
class PlaneInference:
    translation_axis: str
    translation_direction: str
    rotation_axis: str
    planar_axes: tuple[str, str]
    fixed_axis: str
    suggested_plane_key: str
    axis_offsets_deg: dict[str, float]
    warnings: tuple[str, ...]

    def as_config(self) -> dict:
        return {
            "pivot_motion_plane": self.suggested_plane_key,
            "pivot_motion_plane_config": self.as_plane_object(),
            "pivot_translation_axis": self.translation_axis,
            "pivot_translation_direction": self.translation_direction,
            "axis_offsets_deg": self.axis_offsets_deg,
            "orientation_overrides_deg": {},
        }

    def as_plane_object(self) -> dict:
        return {
            "label": self.suggested_plane_key,
            "planar_axes": list(self.planar_axes),
            "fixed_axis": self.fixed_axis,
            "rotation_axis": self.rotation_axis,
            "translation_axis": self.translation_axis,
            "translation_direction": self.translation_direction,
            "axis_offsets_deg": self.axis_offsets_deg,
        }


def unwrap_degrees(reference: float, value: float) -> float:
    return math.degrees(math.radians(reference) + math.atan2(
        math.sin(math.radians(value - reference)),
        math.cos(math.radians(value - reference)),
    ))


def dominant_axis(deltas: dict[str, float], *, min_abs: float) -> tuple[str, float] | None:
    axis, value = max(deltas.items(), key=lambda item: abs(item[1]))
    if abs(value) < min_abs:
        return None
    return axis, value


def infer_plane(
    reference_pose: Pose6D,
    translation_pose: Pose6D,
    rotation_pose: Pose6D,
    *,
    fixed_axis_override: str | None = None,
    min_translation_mm: float = 1.0,
    min_rotation_deg: float = 1.0,
) -> PlaneInference:
    translation = dominant_axis(
        reference_pose.position_delta(translation_pose),
        min_abs=min_translation_mm,
    )
    if translation is None:
        raise ValueError(f"Translation move is too small; move at least {min_translation_mm:.1f} mm")

    rotation = dominant_axis(
        reference_pose.rotation_delta(rotation_pose),
        min_abs=min_rotation_deg,
    )
    if rotation is None:
        raise ValueError(f"Rotation move is too small; rotate at least {min_rotation_deg:.1f} deg")

    translation_axis, translation_delta = translation
    rotation_axis, _rotation_delta = rotation
    direction = "forward" if translation_delta >= 0.0 else "reverse"
    warnings: list[str] = []
    if fixed_axis_override:
        fixed_axis = str(fixed_axis_override).strip().lower()
        if fixed_axis not in AXES:
            raise ValueError(f"Unsupported fixed axis: {fixed_axis_override}")
        planar_axes = tuple(axis for axis in AXES if axis != fixed_axis)
        expected_rotation_axis = f"r{fixed_axis}"
        if rotation_axis != expected_rotation_axis:
            warnings.append(
                f"Measured rotation axis '{rotation_axis.upper()}' does not match the selected fixed axis "
                f"'{fixed_axis.upper()}'. A {fixed_axis.upper()}-fixed plane normally rotates around "
                f"{expected_rotation_axis.upper()}."
            )
    else:
        planar_axes, fixed_axis = ROTATION_PLANES[rotation_axis]

    if translation_axis not in planar_axes:
        warnings.append(
            f"Translation axis '{translation_axis}' is outside the natural plane for {rotation_axis.upper()}. "
            f"{rotation_axis.upper()} normally sweeps {planar_axes[0].upper()}/{planar_axes[1].upper()} "
            f"and keeps {fixed_axis.upper()} fixed."
        )

    axis_offsets = {planar_axes[0]: 0.0, planar_axes[1]: 90.0}
    suggested_key = f"{planar_axes[0]}{planar_axes[1]}_{fixed_axis}_{rotation_axis}"
    return PlaneInference(
        translation_axis=translation_axis,
        translation_direction=direction,
        rotation_axis=rotation_axis,
        planar_axes=planar_axes,
        fixed_axis=fixed_axis,
        suggested_plane_key=suggested_key,
        axis_offsets_deg=axis_offsets,
        warnings=tuple(warnings),
    )


class PoseEditor(QWidget):
    def __init__(self, title: str, initial: Iterable[float] = (0, 0, 300, 180, 0, 0)) -> None:
        super().__init__()
        self._fields: dict[str, QDoubleSpinBox] = {}
        layout = QGridLayout(self)
        layout.setContentsMargins(0, 0, 0, 0)
        layout.setHorizontalSpacing(10)
        layout.setVerticalSpacing(4)
        for col, (name, value) in enumerate(zip(("x", "y", "z", "rx", "ry", "rz"), initial)):
            spin = QDoubleSpinBox()
            spin.setRange(-2000.0, 2000.0)
            spin.setDecimals(3)
            spin.setSingleStep(1.0)
            spin.setValue(float(value))
            spin.setSuffix(" mm" if name in AXES else " deg")
            spin.setMinimumHeight(34)
            spin.setStyleSheet(_SPIN_STYLE)
            self._fields[name] = spin
            label = QLabel(name.upper())
            label.setStyleSheet(LABEL_STYLE)
            label.setAlignment(Qt.AlignmentFlag.AlignCenter)
            layout.addWidget(label, 0, col)
            layout.addWidget(spin, 1, col)

    def pose(self) -> Pose6D:
        return Pose6D(**{name: spin.value() for name, spin in self._fields.items()})

    def set_pose(self, pose: Pose6D) -> None:
        for name, value in zip(("x", "y", "z", "rx", "ry", "rz"), pose.as_list()):
            self._fields[name].setValue(float(value))


class PoseReadout(QWidget):
    def __init__(self, title: str, initial: Iterable[float] = (0, 0, 300, 180, 0, 0)) -> None:
        super().__init__()
        self._values: dict[str, QLabel] = {}
        layout = QGridLayout(self)
        layout.setContentsMargins(0, 0, 0, 0)
        layout.setHorizontalSpacing(10)
        layout.setVerticalSpacing(4)
        for col, (name, value) in enumerate(zip(("x", "y", "z", "rx", "ry", "rz"), initial)):
            label = QLabel(name.upper())
            label.setStyleSheet(LABEL_STYLE)
            label.setAlignment(Qt.AlignmentFlag.AlignCenter)
            value_label = QLabel()
            value_label.setAlignment(Qt.AlignmentFlag.AlignCenter)
            value_label.setMinimumHeight(34)
            value_label.setStyleSheet(_READOUT_VALUE_STYLE)
            self._values[name] = value_label
            layout.addWidget(label, 0, col)
            layout.addWidget(value_label, 1, col)
        self.set_pose(Pose6D(*[float(value) for value in initial]))

    def pose(self) -> Pose6D:
        values = []
        for name in ("x", "y", "z", "rx", "ry", "rz"):
            values.append(float(self._values[name].property("raw_value")))
        return Pose6D(*values)

    def set_pose(self, pose: Pose6D) -> None:
        for name, value in zip(("x", "y", "z", "rx", "ry", "rz"), pose.as_list()):
            suffix = "mm" if name in AXES else "deg"
            self._values[name].setProperty("raw_value", float(value))
            self._values[name].setText(f"{float(value):.3f} {suffix}")


class GuideIllustration(QWidget):
    def __init__(self, mode: str, parent=None) -> None:
        super().__init__(parent)
        self._mode = mode
        self._selected_axis: str | None = None
        self._selected_delta: float = 0.0
        self.setMinimumHeight(230)
        self.setSizePolicy(self.sizePolicy().horizontalPolicy(), self.sizePolicy().verticalPolicy())

    def sizeHint(self) -> QSize:
        return QSize(520, 260)

    def set_selected_axis(self, axis: str | None, delta: float = 0.0) -> None:
        self._selected_axis = axis
        self._selected_delta = float(delta)
        self.update()

    def paintEvent(self, _event) -> None:
        painter = QPainter(self)
        painter.setRenderHint(QPainter.RenderHint.Antialiasing)
        painter.fillRect(self.rect(), QColor(BG_COLOR))

        cx = self.width() * 0.42
        cy = self.height() * 0.66
        self._draw_robot(painter, cx, cy)
        self._draw_axes(painter, cx, cy)
        if self._mode == "rotation":
            self._draw_rotation_guide(painter, cx, cy)
        elif self._mode == "translation":
            self._draw_translation_guide(painter, cx, cy)
        else:
            self._draw_reference_guide(painter, cx, cy)
        if self._selected_axis:
            self._draw_selected_axis(painter, cx, cy, self._selected_axis, self._selected_delta)

    def _draw_robot(self, painter: QPainter, cx: float, cy: float) -> None:
        painter.setPen(QPen(_GUIDE_DETAIL, 2))
        painter.setBrush(QBrush(_GUIDE_BODY))
        body = QRectF(cx - 54, cy - 160, 108, 96)
        painter.drawRoundedRect(body, 14, 14)

        painter.setPen(QPen(_GUIDE_BODY_LINE, 1))
        painter.drawLine(QPointF(cx - 42, cy - 136), QPointF(cx + 42, cy - 136))
        painter.drawLine(QPointF(cx - 42, cy - 88), QPointF(cx + 42, cy - 88))

        painter.setPen(QPen(QColor(BORDER), 1))
        painter.setBrush(QBrush(_GUIDE_DETAIL))
        painter.drawEllipse(QPointF(cx - 34, cy - 148), 4, 4)
        painter.drawEllipse(QPointF(cx + 34, cy - 148), 4, 4)
        painter.setBrush(QBrush(_GUIDE_MARKER))
        painter.drawEllipse(QPointF(cx, cy - 148), 5, 5)

        painter.setBrush(QBrush(QColor(BORDER)))
        painter.drawRoundedRect(QRectF(cx - 15, cy - 64, 30, 58), 4, 4)
        painter.drawRoundedRect(QRectF(cx - 18, cy - 72, 36, 10), 4, 4)
        painter.drawRoundedRect(QRectF(cx - 18, cy - 8, 36, 10), 4, 4)

        painter.setBrush(QBrush(_GUIDE_JOINT))
        painter.setPen(QPen(QColor(TEXT_COLOR), 1.5))
        painter.drawEllipse(QRectF(cx - 56, cy - 18, 112, 36))
        painter.setBrush(QBrush(_GUIDE_CENTER_GLOW))
        painter.setPen(Qt.PenStyle.NoPen)
        painter.drawEllipse(QPointF(cx, cy), 18, 18)
        painter.setBrush(QBrush(_GUIDE_CENTER))
        painter.drawEllipse(QPointF(cx, cy), 7, 7)

    def _draw_axes(self, painter: QPainter, cx: float, cy: float) -> None:
        self._draw_arrow(painter, QPointF(cx, cy), QPointF(cx + 160, cy), _GUIDE_RED, 4)
        self._draw_arrow(painter, QPointF(cx, cy), QPointF(cx - 115, cy + 88), _GUIDE_GREEN, 4)
        self._draw_arrow(painter, QPointF(cx, cy), QPointF(cx, cy - 140), _GUIDE_BLUE, 4)

    def _draw_reference_guide(self, painter: QPainter, cx: float, cy: float) -> None:
        painter.setPen(QPen(QColor(PRIMARY), 3))
        painter.setBrush(QBrush(QColor(PRIMARY_LIGHT)))
        painter.drawEllipse(QPointF(cx, cy), 24, 24)

    def _draw_translation_guide(self, painter: QPainter, cx: float, cy: float) -> None:
        painter.setPen(QPen(_GUIDE_RED, 2))
        for offset in (58, 112):
            painter.drawLine(QPointF(cx + offset, cy - 7), QPointF(cx + offset, cy + 7))

    def _draw_rotation_guide(self, painter: QPainter, cx: float, cy: float) -> None:
        painter.setPen(QPen(_GUIDE_ORANGE, 4))
        painter.setBrush(Qt.BrushStyle.NoBrush)
        painter.drawArc(QRectF(cx - 80, cy - 30, 160, 60), 200 * 16, 270 * 16)
        self._draw_arrow(painter, QPointF(cx + 62, cy - 20), QPointF(cx + 86, cy - 36), _GUIDE_ORANGE, 4)

    def _draw_selected_axis(self, painter: QPainter, cx: float, cy: float, axis: str, delta: float) -> None:
        axis_name = axis.lower().removeprefix("r")
        sign = 1.0 if delta >= 0.0 else -1.0
        end = self._axis_endpoint(cx, cy, axis_name, sign)
        self._draw_arrow(painter, QPointF(cx, cy), end, _GUIDE_ORANGE, 6)
        painter.setPen(QPen(_GUIDE_ORANGE, 2))
        painter.setBrush(QBrush(QColor(BG_COLOR)))
        label_rect = QRectF(end.x() - 24, end.y() - 26, 48, 24)
        painter.drawRoundedRect(label_rect, 6, 6)
        painter.drawText(label_rect, Qt.AlignmentFlag.AlignCenter, axis.upper())

    @staticmethod
    def _axis_endpoint(cx: float, cy: float, axis: str, sign: float) -> QPointF:
        if axis == "x":
            return QPointF(cx + (160 * sign), cy)
        if axis == "y":
            return QPointF(cx - (115 * sign), cy + (88 * sign))
        return QPointF(cx, cy - (140 * sign))

    @staticmethod
    def _draw_arrow(
        painter: QPainter,
        start: QPointF,
        end: QPointF,
        color: QColor,
        width: int,
    ) -> None:
        painter.setPen(QPen(color, width, Qt.PenStyle.SolidLine, Qt.PenCapStyle.RoundCap))
        painter.drawLine(start, end)
        angle = math.atan2(end.y() - start.y(), end.x() - start.x())
        arrow_size = 18
        left = QPointF(
            end.x() - arrow_size * math.cos(angle - math.pi / 6),
            end.y() - arrow_size * math.sin(angle - math.pi / 6),
        )
        right = QPointF(
            end.x() - arrow_size * math.cos(angle + math.pi / 6),
            end.y() - arrow_size * math.sin(angle + math.pi / 6),
        )
        head = QPainterPath()
        head.moveTo(end)
        head.lineTo(left)
        head.moveTo(end)
        head.lineTo(right)
        painter.drawPath(head)


@dataclass
class ProbeState:
    current_pose: Pose6D = field(default_factory=lambda: Pose6D(100, -300, 300, 180, 0, 0))
    paint_pose: Pose6D = field(default_factory=lambda: Pose6D(100, -300, 300, 180, 0, 0))
    reference_pose: Pose6D = field(default_factory=lambda: Pose6D(100, -300, 300, 180, 0, 0))
    translation_pose: Pose6D = field(default_factory=lambda: Pose6D(140, -300, 300, 180, 0, 0))
    rotation_pose: Pose6D = field(default_factory=lambda: Pose6D(100, -300, 300, 180, 10, 0))
    paint_position_reached: bool = False
    reference_captured: bool = False
    translation_captured: bool = False
    rotation_captured: bool = False
    fixed_axis: str | None = None
    inference: PlaneInference | None = None


def _pose_group(title: str, widget: QWidget) -> QGroupBox:
    group = QGroupBox(title)
    group.setStyleSheet(GROUP_STYLE)
    layout = QVBoxLayout(group)
    layout.setContentsMargins(14, 18, 14, 14)
    layout.addWidget(widget)
    return group


class ProbeWizardPage(QWizardPage):
    def __init__(self, state: ProbeState, title: str, info_text: str) -> None:
        super().__init__()
        self._state = state
        self._title = title
        self._info_text = info_text
        self._pose_changed_callback = None
        self.setTitle("")
        self.setSubTitle("")
        self.setStyleSheet(f"background-color: {BG_COLOR};")

    def set_pose_changed_callback(self, callback) -> None:
        self._pose_changed_callback = callback

    def _notify_pose_changed(self) -> None:
        if callable(self._pose_changed_callback):
            self._pose_changed_callback()

    def _add_step_header(self, layout: QVBoxLayout) -> None:
        row = QHBoxLayout()
        row.setContentsMargins(0, 0, 0, 0)
        row.setSpacing(8)

        title = QLabel(self._title)
        title.setStyleSheet(_STEP_TITLE_STYLE)
        info = QPushButton("i")
        info.setStyleSheet(_INFO_BUTTON_STYLE)
        info.setCursor(Qt.CursorShape.PointingHandCursor)
        info.clicked.connect(lambda: self._show_info_bubble(info))

        row.addWidget(title)
        row.addWidget(info)
        row.addStretch()
        layout.addLayout(row)

    def _show_info_bubble(self, button: QPushButton) -> None:
        pos = button.mapToGlobal(button.rect().bottomLeft())
        QToolTip.showText(pos, self._info_text, button)

    @staticmethod
    def _pose_data(pose: Pose6D) -> dict[str, float]:
        return dict(zip(("x", "y", "z", "rx", "ry", "rz"), pose.as_list()))

    @staticmethod
    def _set_jog_buttons_enabled(jog: RobotJogWidget, names: tuple[str, ...], enabled: bool) -> None:
        for name in names:
            button = getattr(jog, name, None)
            if button is not None:
                button.setEnabled(enabled)

    def _translation_move_done(self) -> bool:
        return dominant_axis(
            self._state.reference_pose.position_delta(self._state.current_pose),
            min_abs=1.0,
        ) is not None

    def _rotation_move_done(self) -> bool:
        return dominant_axis(
            self._state.reference_pose.rotation_delta(self._state.current_pose),
            min_abs=1.0,
        ) is not None


class MoveToPaintPositionPage(ProbeWizardPage):
    def __init__(self, state: ProbeState) -> None:
        super().__init__(
            state,
            "Step 1: Move to Paint Position",
            "Start from the real paint movement-group pose. The reference, translation, and rotation captures must be made from this paint orientation so the inferred axes match the actual painting setup.",
        )
        layout = QVBoxLayout(self)
        layout.setSpacing(12)
        self._add_step_header(layout)
        layout.addWidget(_pose_group("Guide", GuideIllustration("reference")))

        self._current = PoseReadout("", state.current_pose.as_list())
        self._paint = PoseReadout("", state.paint_pose.as_list())
        layout.addWidget(_pose_group("Current Pose", self._current))
        layout.addWidget(_pose_group("Paint Position", self._paint))

        actions = QHBoxLayout()
        move = _action_button("Move Current to Paint Position")
        move.clicked.connect(self._move_to_paint_position)
        actions.addWidget(move)
        actions.addStretch()
        layout.addLayout(actions)
        layout.addStretch()

    def initializePage(self) -> None:
        self._current.set_pose(self._state.current_pose)
        self._paint.set_pose(self._state.paint_pose)

    def isComplete(self) -> bool:
        return self._state.paint_position_reached

    def validatePage(self) -> bool:
        return self.isComplete()

    def _move_to_paint_position(self) -> None:
        if not self._confirm_move_to_paint_position():
            return
        self._state.current_pose = self._state.paint_pose
        self._state.reference_pose = self._state.paint_pose
        self._state.paint_position_reached = True
        self._state.reference_captured = False
        self._state.translation_captured = False
        self._state.rotation_captured = False
        self._state.fixed_axis = None
        self._state.inference = None
        self.initializePage()
        self._notify_pose_changed()
        self.completeChanged.emit()

    def _confirm_move_to_paint_position(self) -> bool:
        pose = self._state.paint_pose
        message = (
            "The robot will move to:\n\n"
            f"X: {pose.x:.3f} mm\n"
            f"Y: {pose.y:.3f} mm\n"
            f"Z: {pose.z:.3f} mm\n"
            f"RX: {pose.rx:.3f} deg\n"
            f"RY: {pose.ry:.3f} deg\n"
            f"RZ: {pose.rz:.3f} deg"
        )
        return ask_yes_no(self, "Confirm Paint Position Move", message, default_no=True)

    def _mark_current_pose_changed(self) -> None:
        self._state.paint_position_reached = False
        self._state.reference_captured = False
        self._state.translation_captured = False
        self._state.rotation_captured = False
        self._state.fixed_axis = None
        self._state.inference = None
        self.initializePage()
        self.completeChanged.emit()


class ReferencePage(ProbeWizardPage):
    def __init__(self, state: ProbeState) -> None:
        super().__init__(
            state,
            "Step 2: Capture Reference Pose",
            "Use the jog drawer to move the robot into the paint reference pose, then capture the current pose as reference.",
        )
        layout = QVBoxLayout(self)
        layout.setSpacing(12)
        self._add_step_header(layout)
        layout.addWidget(_pose_group("Guide", GuideIllustration("reference")))

        self._current = PoseReadout("", state.current_pose.as_list())
        self._reference = PoseReadout("", state.reference_pose.as_list())
        layout.addWidget(_pose_group("Current Pose", self._current))
        layout.addWidget(_pose_group("Reference Pose", self._reference))

        actions = QHBoxLayout()
        capture = _action_button("Capture Current as Reference")
        capture.clicked.connect(self._capture_reference)
        example_xz = _ghost_button("Example XZ/RY")
        example_xz.clicked.connect(self._load_xz_ry_example)
        example_yz = _ghost_button("Example YZ/RX")
        example_yz.clicked.connect(self._load_yz_rx_example)
        actions.addWidget(capture)
        actions.addWidget(example_xz)
        actions.addWidget(example_yz)
        actions.addStretch()
        layout.addLayout(actions)
        layout.addStretch()

    def initializePage(self) -> None:
        self._current.set_pose(self._state.current_pose)
        self._reference.set_pose(self._state.reference_pose)

    def isComplete(self) -> bool:
        return self._state.reference_captured

    def validatePage(self) -> bool:
        return True

    def _capture_reference(self) -> None:
        self._state.reference_pose = self._state.current_pose
        self._state.reference_captured = True
        self._state.translation_captured = False
        self._state.rotation_captured = False
        self._state.fixed_axis = None
        self._state.inference = None
        self._reference.set_pose(self._state.reference_pose)
        self._notify_pose_changed()
        self.completeChanged.emit()

    def _load_xz_ry_example(self) -> None:
        self._state.current_pose = Pose6D(100, -300, 300, 0, 0, 0)
        self._state.paint_pose = Pose6D(100, -300, 300, 0, 0, 0)
        self._state.reference_pose = Pose6D(100, -300, 300, 0, 0, 0)
        self._state.translation_pose = Pose6D(140, -300, 300, 0, 0, 0)
        self._state.rotation_pose = Pose6D(100, -300, 300, 0, 10, 0)
        self._state.paint_position_reached = True
        self._state.reference_captured = True
        self._state.translation_captured = True
        self._state.rotation_captured = True
        self._state.fixed_axis = "y"
        self.initializePage()
        self._notify_pose_changed()
        self.completeChanged.emit()

    def _load_yz_rx_example(self) -> None:
        self._state.current_pose = Pose6D(100, -300, 300, 0, 0, 0)
        self._state.paint_pose = Pose6D(100, -300, 300, 0, 0, 0)
        self._state.reference_pose = Pose6D(100, -300, 300, 0, 0, 0)
        self._state.translation_pose = Pose6D(100, -260, 300, 0, 0, 0)
        self._state.rotation_pose = Pose6D(100, -300, 300, 10, 0, 0)
        self._state.paint_position_reached = True
        self._state.reference_captured = True
        self._state.translation_captured = True
        self._state.rotation_captured = True
        self._state.fixed_axis = "x"
        self.initializePage()
        self._notify_pose_changed()
        self.completeChanged.emit()


class JogTranslationPage(ProbeWizardPage):
    def __init__(self, state: ProbeState) -> None:
        super().__init__(
            state,
            "Step 3: Move and Capture Translation",
            "Use the jog drawer to move along the preferred paint translation axis. If the move was wrong, return to reference and jog again. Capture the current pose when the translation is correct.",
        )
        layout = QVBoxLayout(self)
        layout.setSpacing(12)
        self._add_step_header(layout)
        self._guide = GuideIllustration("translation")
        layout.addWidget(_pose_group("Guide", self._guide))

        self._reference = PoseReadout("", state.reference_pose.as_list())
        self._translation = PoseReadout("", state.translation_pose.as_list())
        layout.addWidget(_pose_group("Reference Pose", self._reference))
        layout.addWidget(_pose_group("Captured Translation Pose", self._translation))

        actions = QHBoxLayout()
        capture = _action_button("Capture Current Translation")
        capture.clicked.connect(self._capture_translation)
        reset = _ghost_button("Back to Reference")
        reset.clicked.connect(self._back_to_reference)
        actions.addWidget(capture)
        actions.addWidget(reset)
        actions.addStretch()
        layout.addLayout(actions)
        layout.addStretch()

    def initializePage(self) -> None:
        self._reference.set_pose(self._state.reference_pose)
        self._translation.set_pose(self._state.translation_pose)
        self._sync_guide()

    def isComplete(self) -> bool:
        return self._state.translation_captured

    def validatePage(self) -> bool:
        if not self.isComplete():
            return False
        self._state.current_pose = self._state.reference_pose
        return True

    def _nudge_position(self, axis: str, delta: float) -> None:
        data = self._pose_data(self._state.current_pose)
        data[axis] += delta
        self._state.current_pose = Pose6D(**data)
        self._state.translation_captured = False
        self._state.rotation_captured = False
        self._state.inference = None
        self._notify_pose_changed()
        self.completeChanged.emit()

    def _capture_translation(self) -> None:
        if not self._translation_move_done():
            return
        self._state.translation_pose = self._state.current_pose
        self._state.translation_captured = True
        self._state.rotation_captured = False
        self._state.fixed_axis = None
        self._state.inference = None
        self._translation.set_pose(self._state.translation_pose)
        self._sync_guide()
        self.completeChanged.emit()

    def _back_to_reference(self) -> None:
        self._state.current_pose = self._state.reference_pose
        self._state.translation_captured = False
        self._state.rotation_captured = False
        self._state.fixed_axis = None
        self._state.inference = None
        self.initializePage()
        self._notify_pose_changed()
        self.completeChanged.emit()

    def _sync_guide(self) -> None:
        if not self._state.translation_captured:
            self._guide.set_selected_axis(None)
            return
        result = dominant_axis(
            self._state.reference_pose.position_delta(self._state.translation_pose),
            min_abs=1.0,
        )
        if result is None:
            self._guide.set_selected_axis(None)
            return
        axis, delta = result
        self._guide.set_selected_axis(axis, delta)


class JogRotationPage(ProbeWizardPage):
    def __init__(self, state: ProbeState) -> None:
        super().__init__(
            state,
            "Step 4: Move and Capture Rotation",
            "Use the jog drawer to rotate around the intended pivot axis. If the rotation was wrong, return to reference and rotate again. Capture the current pose when the rotation is correct.",
        )
        layout = QVBoxLayout(self)
        layout.setSpacing(12)
        self._add_step_header(layout)
        self._guide = GuideIllustration("rotation")
        layout.addWidget(_pose_group("Guide", self._guide))

        self._reference = PoseReadout("", state.reference_pose.as_list())
        self._rotation = PoseReadout("", state.rotation_pose.as_list())
        layout.addWidget(_pose_group("Reference Pose", self._reference))
        layout.addWidget(_pose_group("Captured Rotation Pose", self._rotation))

        actions = QHBoxLayout()
        capture = _action_button("Capture Current Rotation")
        capture.clicked.connect(self._capture_rotation)
        reset = _ghost_button("Back to Reference")
        reset.clicked.connect(self._back_to_reference)
        actions.addWidget(capture)
        actions.addWidget(reset)
        actions.addStretch()
        layout.addLayout(actions)
        layout.addStretch()

    def initializePage(self) -> None:
        self._reference.set_pose(self._state.reference_pose)
        self._rotation.set_pose(self._state.rotation_pose)
        self._sync_guide()

    def isComplete(self) -> bool:
        return self._state.rotation_captured

    def validatePage(self) -> bool:
        if not self.isComplete():
            return False
        return True

    def _nudge_rotation(self, axis: str, delta: float) -> None:
        data = self._pose_data(self._state.current_pose)
        data[axis] += delta
        self._state.current_pose = Pose6D(**data)
        self._state.rotation_captured = False
        self._state.inference = None
        self._notify_pose_changed()
        self.completeChanged.emit()

    def _capture_rotation(self) -> None:
        if not self._rotation_move_done():
            return
        self._state.rotation_pose = self._state.current_pose
        self._state.rotation_captured = True
        self._state.fixed_axis = None
        self._state.inference = None
        self._rotation.set_pose(self._state.rotation_pose)
        self._sync_guide()
        self.completeChanged.emit()

    def _back_to_reference(self) -> None:
        self._state.current_pose = self._state.reference_pose
        self._state.rotation_captured = False
        self._state.fixed_axis = None
        self._state.inference = None
        self.initializePage()
        self._notify_pose_changed()
        self.completeChanged.emit()

    def _sync_guide(self) -> None:
        if not self._state.rotation_captured:
            self._guide.set_selected_axis(None)
            return
        result = dominant_axis(
            self._state.reference_pose.rotation_delta(self._state.rotation_pose),
            min_abs=1.0,
        )
        if result is None:
            self._guide.set_selected_axis(None)
            return
        axis, delta = result
        self._guide.set_selected_axis(axis, delta)


class FixedAxisPage(ProbeWizardPage):
    def __init__(self, state: ProbeState) -> None:
        super().__init__(
            state,
            "Step 5: Constant Axis",
            "Choose the robot position axis that should remain constant during the generated paint motion. This defines the plane normal and prevents relying only on the detected rotation axis.",
        )
        layout = QVBoxLayout(self)
        layout.setSpacing(12)
        self._add_step_header(layout)

        self._summary = QLabel("")
        self._summary.setStyleSheet(_SUMMARY_STYLE)
        self._summary.setMinimumHeight(44)
        layout.addWidget(self._summary)

        actions = QHBoxLayout()
        self._axis_buttons: dict[str, QPushButton] = {}
        for axis in AXES:
            button = _ghost_button(f"Keep {axis.upper()} Constant")
            button.setCheckable(True)
            button.clicked.connect(lambda _checked=False, a=axis: self._select_axis(a))
            self._axis_buttons[axis] = button
            actions.addWidget(button)
        actions.addStretch()
        layout.addLayout(actions)
        layout.addStretch()

    def initializePage(self) -> None:
        self._sync_buttons()

    def isComplete(self) -> bool:
        return self._state.fixed_axis in AXES

    def validatePage(self) -> bool:
        return self.isComplete()

    def _select_axis(self, axis: str) -> None:
        self._state.fixed_axis = axis
        self._state.inference = None
        self._sync_buttons()
        self.completeChanged.emit()

    def _sync_buttons(self) -> None:
        selected = self._state.fixed_axis
        for axis, button in self._axis_buttons.items():
            button.setChecked(axis == selected)
        if selected:
            planar_axes = ", ".join(axis.upper() for axis in AXES if axis != selected)
            self._summary.setText(
                f"Selected fixed axis: {selected.upper()} | Generated plane: {planar_axes}"
            )
        else:
            self._summary.setText("Select which position axis should stay constant.")


class InferencePage(ProbeWizardPage):
    def __init__(self, state: ProbeState) -> None:
        super().__init__(
            state,
            "Step 6: Inference",
            "Review the inferred motion plane and the suggested runtime configuration fragment.",
        )
        layout = QVBoxLayout(self)
        layout.setSpacing(12)
        self._add_step_header(layout)

        result_group = QGroupBox("Result")
        result_group.setStyleSheet(GROUP_STYLE)
        result_layout = QGridLayout(result_group)
        result_layout.setContentsMargins(14, 18, 14, 14)
        result_layout.setHorizontalSpacing(10)
        result_layout.setVerticalSpacing(8)
        self._result_values: dict[str, QLabel] = {}
        for col, (key, title) in enumerate((
            ("plane", "Plane"),
            ("axis", "Paint Axis"),
            ("direction", "Direction"),
            ("rotation", "Rotation"),
            ("fixed", "Fixed Axis"),
        )):
            result_layout.addWidget(_label(title), 0, col)
            value = QLabel("-")
            value.setAlignment(Qt.AlignmentFlag.AlignCenter)
            value.setStyleSheet(_RESULT_VALUE_STYLE)
            value.setMinimumHeight(48)
            self._result_values[key] = value
            result_layout.addWidget(value, 1, col)
        layout.addWidget(result_group)

        self._summary = QLabel("")
        self._summary.setAlignment(Qt.AlignmentFlag.AlignLeft)
        self._summary.setStyleSheet(_SUMMARY_STYLE)
        self._summary.setMinimumHeight(44)
        layout.addWidget(self._summary)

        self._warnings = QLabel("")
        self._warnings.setWordWrap(True)
        self._warnings.setStyleSheet(_WARNING_STYLE)
        self._warnings.hide()
        layout.addWidget(self._warnings)

        self._output = QPlainTextEdit()
        self._output.setReadOnly(True)
        self._output.setStyleSheet(_OUTPUT_STYLE)
        layout.addWidget(self._output, stretch=1)

    def initializePage(self) -> None:
        self._infer()

    def _infer(self) -> None:
        try:
            result = infer_plane(
                self._state.reference_pose,
                self._state.translation_pose,
                self._state.rotation_pose,
                fixed_axis_override=self._state.fixed_axis,
            )
        except ValueError as exc:
            self._state.inference = None
            self._summary.setText(str(exc))
            for value in self._result_values.values():
                value.setText("-")
            self._warnings.hide()
            self._output.setPlainText("")
            return

        self._state.inference = result
        warning_text = "\n".join(f"WARNING: {warning}" for warning in result.warnings)
        payload = {
            "inference": {
                "translation_axis": result.translation_axis,
                "translation_direction": result.translation_direction,
                "rotation_axis": result.rotation_axis,
                "planar_axes": list(result.planar_axes),
                "fixed_axis": result.fixed_axis,
                "suggested_plane_key": result.suggested_plane_key,
                "plane_object": result.as_plane_object(),
                "warnings": list(result.warnings),
            },
            "suggested_runtime_config": result.as_config(),
            "notes": [
                "A missing orientation override means the generated path uses the taught paint base pose orientation.",
                "An override of 0.0 still forces exactly 0.0; it is not the same as no override.",
                "If translation_axis is outside planar_axes, the requested setup is physically unusual for that rotation axis.",
            ],
        }
        self._summary.setText(
            f"Suggested plane: {result.suggested_plane_key} | "
            f"axis={result.translation_axis} direction={result.translation_direction} | "
            f"rotation={result.rotation_axis.upper()}"
        )
        self._result_values["plane"].setText(result.suggested_plane_key)
        self._result_values["axis"].setText(result.translation_axis.upper())
        self._result_values["direction"].setText(result.translation_direction.title())
        self._result_values["rotation"].setText(result.rotation_axis.upper())
        self._result_values["fixed"].setText(result.fixed_axis.upper())
        if result.warnings:
            self._warnings.setText("\n".join(result.warnings))
            self._warnings.show()
        else:
            self._warnings.hide()
        text = json.dumps(payload, indent=2)
        if warning_text:
            text = f"{warning_text}\n\n{text}"
        self._output.setPlainText(text)


def create_probe_wizard(state: ProbeState | None = None) -> ConfigurableWizard:
    probe_state = state or ProbeState()
    pages = [
        MoveToPaintPositionPage(probe_state),
        ReferencePage(probe_state),
        JogTranslationPage(probe_state),
        JogRotationPage(probe_state),
        FixedAxisPage(probe_state),
        InferencePage(probe_state),
    ]
    wizard = ConfigurableWizard(
        title="Paint Motion Plane Probe",
        pages=pages,
        min_width=1180,
        min_height=760,
        use_material_buttons=True,
    )
    wizard.setStyleSheet(f"background-color: {BG_COLOR};")
    _install_probe_jog_drawer(wizard, probe_state, pages)
    _wire_step_button_gating(wizard, pages)
    return wizard


def _install_probe_jog_drawer(
    wizard: ConfigurableWizard,
    state: ProbeState,
    pages: list[QWizardPage],
) -> None:
    drawer = DrawerToggle(wizard, side="right", width=340)
    jog = RobotJogWidget()
    jog.enable_frame_selector(False)
    drawer.add_widget(jog)
    drawer.set_visible(True)
    allowed_jog_keys: set[str] = set()

    wizard._probe_jog_drawer = drawer
    wizard._probe_jog_widget = jog

    def sync_drawer() -> None:
        page = wizard.currentPage()
        jog.set_position(state.current_pose.as_list())
        if isinstance(page, JogTranslationPage):
            ProbeWizardPage._set_jog_buttons_enabled(jog, LINEAR_JOG_BUTTONS, True)
            ProbeWizardPage._set_jog_buttons_enabled(jog, ROTATION_JOG_BUTTONS, False)
            return
        if isinstance(page, JogRotationPage):
            ProbeWizardPage._set_jog_buttons_enabled(jog, LINEAR_JOG_BUTTONS, False)
            ProbeWizardPage._set_jog_buttons_enabled(jog, ROTATION_JOG_BUTTONS, True)
            return
        ProbeWizardPage._set_jog_buttons_enabled(jog, LINEAR_JOG_BUTTONS, True)
        ProbeWizardPage._set_jog_buttons_enabled(jog, ROTATION_JOG_BUTTONS, True)

    def on_jog_started(key: str) -> None:
        allowed_jog_keys.add(key)

    def on_jog_stopped(key: str) -> None:
        allowed_jog_keys.discard(key)
        timer = getattr(jog, "_timers", {}).get(key)
        if timer is not None:
            timer.stop()

    def on_jog_requested(_command: str, axis: str, direction: str, step: float) -> None:
        page = wizard.currentPage()
        axis_name = axis.lower()
        key = f"{axis_name}_{direction.lower()}"
        if key not in allowed_jog_keys:
            return
        allowed_jog_keys.discard(key)
        timer = getattr(jog, "_timers", {}).get(key)
        if timer is not None:
            timer.stop()
        delta = float(step) if direction == "Plus" else -float(step)
        if isinstance(page, MoveToPaintPositionPage) and axis_name in (*AXES, *ROT_AXES):
            data = ProbeWizardPage._pose_data(state.current_pose)
            data[axis_name] += delta
            state.current_pose = Pose6D(**data)
            page._mark_current_pose_changed()
        elif isinstance(page, ReferencePage) and axis_name in (*AXES, *ROT_AXES):
            data = ProbeWizardPage._pose_data(state.current_pose)
            data[axis_name] += delta
            state.current_pose = Pose6D(**data)
            state.reference_captured = False
            state.translation_captured = False
            state.rotation_captured = False
            state.inference = None
            page.initializePage()
            page.completeChanged.emit()
        elif isinstance(page, JogTranslationPage) and axis_name in AXES:
            page._nudge_position(axis_name, delta)
        elif isinstance(page, JogRotationPage) and axis_name in ROT_AXES:
            page._nudge_rotation(axis_name, delta)
        elif isinstance(page, InferencePage) and axis_name in (*AXES, *ROT_AXES):
            data = ProbeWizardPage._pose_data(state.current_pose)
            data[axis_name] += delta
            state.current_pose = Pose6D(**data)
        sync_drawer()

    for page in pages:
        if isinstance(page, ProbeWizardPage):
            page.set_pose_changed_callback(sync_drawer)
    jog.jog_started.connect(on_jog_started)
    jog.jog_stopped.connect(on_jog_stopped)
    jog.jog_requested.connect(on_jog_requested)
    wizard.currentIdChanged.connect(lambda _page_id: sync_drawer())
    sync_drawer()


def _wire_step_button_gating(wizard: ConfigurableWizard, pages: list[QWizardPage]) -> None:
    def sync_buttons() -> None:
        page = wizard.currentPage()
        if page is None:
            return
        next_button = wizard.button(QWizard.WizardButton.NextButton)
        if next_button is not None:
            next_button.setEnabled(page.isComplete())
        finish_button = wizard.button(QWizard.WizardButton.FinishButton)
        if finish_button is not None:
            finish_button.setEnabled(page.isComplete())

    wizard.currentIdChanged.connect(lambda _page_id: sync_buttons())
    for page in pages:
        page.completeChanged.connect(sync_buttons)
    sync_buttons()


def main() -> int:
    app = QApplication(sys.argv)
    wizard = create_probe_wizard()
    wizard.show()
    return app.exec()


if __name__ == "__main__":
    raise SystemExit(main())
