from __future__ import annotations

import json
import math

from PyQt6.QtCore import QPointF, QRectF, QSize, Qt, pyqtSignal
from PyQt6.QtGui import QColor, QBrush, QPainter, QPainterPath, QPen
from PyQt6.QtWidgets import (
    QComboBox,
    QFrame,
    QHBoxLayout,
    QLabel,
    QPlainTextEdit,
    QPushButton,
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
    LABEL_STYLE,
    PRIMARY,
    PRIMARY_LIGHT,
    SECONDARY_BG,
    TERTIARY_BG,
    TEXT_COLOR,
)
from src.applications.base.i_application_view import IApplicationView
from src.applications.base.styled_message_box import ask_yes_no, show_critical, show_info
from src.robot_systems.paint.applications.paint_motion_plane_setup.domain.plane_inference import (
    AXES,
    Pose6D,
    dominant_axis,
)


_VALUE_STYLE = f"""
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

_INFO_STYLE = f"""
QLabel {{
    background: {SECONDARY_BG};
    color: {TEXT_COLOR};
    border: 1px solid {BORDER};
    border-radius: 8px;
    padding: 8px 12px;
    font-size: 10pt;
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

_CARD_STYLE = f"""
QFrame {{
    background: white;
    border: 1px solid {BORDER};
    border-radius: 8px;
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


def _pose_text(pose: Pose6D | None) -> str:
    if pose is None:
        return "not set"
    names = ("X", "Y", "Z", "RX", "RY", "RZ")
    suffixes = ("mm", "mm", "mm", "deg", "deg", "deg")
    return "   ".join(
        f"{name}={value:.3f} {suffix}"
        for name, value, suffix in zip(names, pose.as_list(), suffixes)
    )


def _button(text: str, *, primary: bool = True) -> QPushButton:
    button = QPushButton(text)
    button.setStyleSheet(ACTION_BTN_STYLE if primary else GHOST_BTN_STYLE)
    button.setCursor(Qt.CursorShape.PointingHandCursor)
    return button


class _PoseReadout(QFrame):
    def __init__(self, label: str) -> None:
        super().__init__()
        self.setStyleSheet(_CARD_STYLE)
        layout = QHBoxLayout(self)
        layout.setContentsMargins(10, 8, 10, 8)
        layout.setSpacing(10)

        title = QLabel(label)
        title.setStyleSheet(LABEL_STYLE)
        self._value = QLabel("not set")
        self._value.setStyleSheet(_VALUE_STYLE)
        self._value.setMinimumHeight(32)
        self._value.setTextInteractionFlags(Qt.TextInteractionFlag.TextSelectableByMouse)

        layout.addWidget(title)
        layout.addWidget(self._value, 1)

    def set_pose(self, pose: Pose6D | None) -> None:
        self._value.setText(_pose_text(pose))


class _GuideIllustration(QWidget):
    def __init__(self, mode: str) -> None:
        super().__init__()
        self._mode = mode
        self._selected_axis: str | None = None
        self._selected_delta = 0.0
        self.setMinimumHeight(220)

    def sizeHint(self) -> QSize:
        return QSize(520, 250)

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
        if self._mode == "translation":
            self._draw_translation_guide(painter, cx, cy)
        elif self._mode == "rotation":
            self._draw_rotation_guide(painter, cx, cy)
        else:
            self._draw_reference_guide(painter, cx, cy)
        if self._selected_axis:
            self._draw_selected_axis(painter, cx, cy, self._selected_axis, self._selected_delta)

    def _draw_robot(self, painter: QPainter, cx: float, cy: float) -> None:
        painter.setPen(QPen(_GUIDE_DETAIL, 2))
        painter.setBrush(QBrush(_GUIDE_BODY))
        painter.drawRoundedRect(QRectF(cx - 54, cy - 160, 108, 96), 14, 14)

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


class _WizardPage(QWizardPage):
    def __init__(self, title: str, help_text: str) -> None:
        super().__init__()
        self._complete = False
        self._help_text = help_text
        self._layout = QVBoxLayout(self)
        self._layout.setContentsMargins(18, 14, 18, 14)
        self._layout.setSpacing(12)
        self._build_heading(title)

    @property
    def content_layout(self) -> QVBoxLayout:
        return self._layout

    def set_complete(self, complete: bool) -> None:
        if self._complete == complete:
            return
        self._complete = complete
        self.completeChanged.emit()

    def isComplete(self) -> bool:
        return self._complete

    def _build_heading(self, title: str) -> None:
        row = QHBoxLayout()
        label = QLabel(title)
        label.setStyleSheet(f"color: {TEXT_COLOR}; font-size: 16pt; font-weight: 700;")
        info = QPushButton("i")
        info.setStyleSheet(_INFO_BUTTON_STYLE)
        info.setCursor(Qt.CursorShape.PointingHandCursor)
        info.clicked.connect(self._show_help)
        row.addWidget(label)
        row.addWidget(info)
        row.addStretch()
        self._layout.addLayout(row)

    def _show_help(self) -> None:
        show_info(self, "Step information", self._help_text)


class _ResultPage(_WizardPage):
    def __init__(self) -> None:
        super().__init__(
            "Result",
            "Review the generated motion-plane object. This development screen does not apply it to runtime paint execution.",
        )
        self.set_complete(True)


class PaintMotionPlaneSetupView(IApplicationView):
    SHOW_JOG_WIDGET = True
    JOG_FRAME_SELECTOR_ENABLED = True
    JOG_DRAWER_WIDTH = 330

    move_to_paint_pose_requested = pyqtSignal()
    paint_group_selected = pyqtSignal(str)
    capture_reference_requested = pyqtSignal()
    capture_translation_requested = pyqtSignal()
    capture_rotation_requested = pyqtSignal()

    def __init__(self) -> None:
        self._current_pose: Pose6D | None = None
        self._paint_pose: Pose6D | None = None
        self._reference_pose: Pose6D | None = None
        self._translation_pose: Pose6D | None = None
        self._rotation_pose: Pose6D | None = None
        self._busy = False
        self._pages: dict[str, _WizardPage] = {}
        super().__init__("Paint Motion Plane Setup")

    def setup_ui(self) -> None:
        self.setStyleSheet(f"background-color: {BG_COLOR};")
        layout = QVBoxLayout(self)
        layout.setContentsMargins(18, 18, 18, 18)
        layout.setSpacing(12)

        self._current = _PoseReadout("Current pose")
        layout.addWidget(self._current)

        self._wizard = QWizard()
        self._wizard.setWizardStyle(QWizard.WizardStyle.ModernStyle)
        self._wizard.setOption(QWizard.WizardOption.NoCancelButton, True)
        self._wizard.setButtonText(QWizard.WizardButton.FinishButton, "Finish")
        self._wizard.setMinimumHeight(520)
        self._build_pages()
        layout.addWidget(self._wizard, 1)

    def clean_up(self) -> None:
        return None

    def set_jog_position(self, pos: list) -> None:
        super().set_jog_position(pos)
        if pos and len(pos) >= 6:
            self.set_current_pose(Pose6D.from_sequence(pos))

    def set_current_pose(self, pose: Pose6D | None) -> None:
        self._current_pose = pose
        self._current.set_pose(pose)

    def set_paint_pose(self, pose: Pose6D | None) -> None:
        self._paint_pose = pose
        self._paint_pose_readout.set_pose(pose)
        self._move_paint_btn.setEnabled(pose is not None and not self._busy)

    def set_paint_groups(self, group_ids: list[str], selected_group_id: str = "") -> None:
        selected = str(selected_group_id or "").strip()
        self._paint_group_combo.blockSignals(True)
        self._paint_group_combo.clear()
        for group_id in group_ids:
            self._paint_group_combo.addItem(group_id, group_id)
        if selected:
            index = self._paint_group_combo.findData(selected)
            if index >= 0:
                self._paint_group_combo.setCurrentIndex(index)
        self._paint_group_combo.blockSignals(False)
        self._paint_group_combo.setEnabled(bool(group_ids) and not self._busy)

    def set_paint_move_complete(self, complete: bool) -> None:
        self._pages["paint"].set_complete(complete)

    def set_reference_pose(self, pose: Pose6D | None) -> None:
        self._reference_pose = pose
        self._reference_readout.set_pose(pose)
        self._pages["reference"].set_complete(pose is not None)
        self._sync_translation_guide()
        self._sync_rotation_guide()

    def set_translation_pose(self, pose: Pose6D | None) -> None:
        self._translation_pose = pose
        self._translation_readout.set_pose(pose)
        self._pages["translation"].set_complete(pose is not None)
        self._sync_translation_guide()

    def set_rotation_pose(self, pose: Pose6D | None) -> None:
        self._rotation_pose = pose
        self._rotation_readout.set_pose(pose)
        self._pages["rotation"].set_complete(pose is not None)
        self._sync_rotation_guide()

    def set_result(
        self,
        result: dict | None,
        warnings: tuple[str, ...] = (),
        paint_plane_config: dict | None = None,
    ) -> None:
        if result is None:
            self._result_output.setPlainText("Capture reference, translation, and rotation to generate a result.")
            return
        payload = {
            "paint_plane_config": paint_plane_config or {},
            "suggested_runtime_config": result,
            "warnings": list(warnings),
        }
        fixed_axis = str(
            result.get("pivot_motion_plane_config", {}).get("fixed_axis", "")
        ).upper()
        rotation_axis = str(
            result.get("pivot_motion_plane_config", {}).get("rotation_axis", "")
        ).upper()
        if fixed_axis and rotation_axis:
            self._result_summary.setText(
                f"Inferred fixed axis: {fixed_axis} from measured rotation {rotation_axis}."
            )
        else:
            self._result_summary.setText("Fixed axis will be inferred from the measured rotation.")
        self._result_output.setPlainText(json.dumps(payload, indent=2))

    def set_busy(self, busy: bool, message: str = "") -> None:
        self._busy = busy
        self._status.setText(message or "Ready")
        self._paint_group_combo.setEnabled(not busy and self._paint_group_combo.count() > 0)
        self._move_paint_btn.setEnabled(not busy and self._paint_pose is not None)
        self._capture_reference_btn.setEnabled(not busy)
        self._capture_translation_btn.setEnabled(not busy)
        self._capture_rotation_btn.setEnabled(not busy)

    def show_error(self, title: str, message: str) -> None:
        show_critical(self, title, message)

    def confirm_move_to_paint_pose(self) -> bool:
        if self._paint_pose is None:
            self.show_error("Paint pose unavailable", "The configured paint movement group has no valid 6D pose.")
            return False
        return ask_yes_no(
            self,
            "Move robot to paint pose",
            "The robot will move to:\n\n"
            f"{_pose_text(self._paint_pose)}\n\n"
            "Confirm only if the robot path is clear.",
            default_no=True,
        )

    def _build_pages(self) -> None:
        paint = _WizardPage(
            "Move to paint position",
            "Start from the same taught paint position that paint execution will use. The inferred axes are meaningful only for this pose orientation.",
        )
        selector_row = QHBoxLayout()
        selector_label = QLabel("Shaft")
        selector_label.setStyleSheet(LABEL_STYLE)
        self._paint_group_combo = QComboBox()
        self._paint_group_combo.setStyleSheet(
            f"background: white; color: {TEXT_COLOR}; border: 1px solid {BORDER}; "
            "border-radius: 6px; padding: 6px 8px; font-size: 11pt;"
        )
        self._paint_group_combo.currentIndexChanged.connect(self._on_paint_group_changed)
        selector_row.addWidget(selector_label)
        selector_row.addWidget(self._paint_group_combo, 1)
        self._paint_pose_readout = _PoseReadout("Paint pose")
        self._move_paint_btn = _button("Move to Paint Position")
        self._move_paint_btn.clicked.connect(self._on_move_paint_clicked)
        self._status = QLabel("Ready")
        self._status.setStyleSheet(_INFO_STYLE)
        paint.content_layout.addLayout(selector_row)
        paint.content_layout.addWidget(self._paint_pose_readout)
        paint.content_layout.addWidget(self._move_paint_btn)
        paint.content_layout.addWidget(self._status)
        self._add_page("paint", paint)

        reference = _WizardPage(
            "Capture reference pose",
            "Use the jog drawer if needed, then capture the current robot pose as the origin for the axis probe.",
        )
        self._reference_guide = _GuideIllustration("reference")
        self._reference_readout = _PoseReadout("Reference")
        self._capture_reference_btn = _button("Set Current as Reference")
        self._capture_reference_btn.clicked.connect(self._on_capture_reference_clicked)
        reference.content_layout.addWidget(self._reference_guide)
        reference.content_layout.addWidget(self._reference_readout)
        reference.content_layout.addWidget(self._capture_reference_btn)
        self._add_page("reference", reference)

        translation = _WizardPage(
            "Move and capture translation",
            "Jog along the desired paint translation direction, then capture the current pose.",
        )
        self._translation_guide = _GuideIllustration("translation")
        self._translation_readout = _PoseReadout("Translation")
        self._capture_translation_btn = _button("Capture Current Translation")
        self._capture_translation_btn.clicked.connect(self._on_capture_translation_clicked)
        translation.content_layout.addWidget(self._translation_guide)
        translation.content_layout.addWidget(self._translation_readout)
        translation.content_layout.addWidget(self._capture_translation_btn)
        self._add_page("translation", translation)

        rotation = _WizardPage(
            "Move and capture rotation",
            "Return near the reference position if needed, rotate around the desired paint rotation axis, then capture.",
        )
        self._rotation_guide = _GuideIllustration("rotation")
        self._rotation_readout = _PoseReadout("Rotation")
        self._capture_rotation_btn = _button("Capture Current Rotation")
        self._capture_rotation_btn.clicked.connect(self._on_capture_rotation_clicked)
        rotation.content_layout.addWidget(self._rotation_guide)
        rotation.content_layout.addWidget(self._rotation_readout)
        rotation.content_layout.addWidget(self._capture_rotation_btn)
        self._add_page("rotation", rotation)

        result = _ResultPage()
        self._result_summary = QLabel("Fixed axis will be inferred from the measured rotation.")
        self._result_summary.setStyleSheet(_INFO_STYLE)
        self._result_output = QPlainTextEdit()
        self._result_output.setReadOnly(True)
        self._result_output.setStyleSheet(_OUTPUT_STYLE)
        result.content_layout.addWidget(self._result_summary)
        result.content_layout.addWidget(self._result_output, 1)
        self._add_page("result", result)

    def _add_page(self, key: str, page: _WizardPage) -> None:
        self._pages[key] = page
        self._wizard.addPage(page)

    def _on_move_paint_clicked(self) -> None:
        self.move_to_paint_pose_requested.emit()

    def _on_paint_group_changed(self, _index: int) -> None:
        group_id = str(self._paint_group_combo.currentData() or self._paint_group_combo.currentText()).strip()
        if group_id:
            self.paint_group_selected.emit(group_id)

    def _on_capture_reference_clicked(self) -> None:
        self.capture_reference_requested.emit()

    def _on_capture_translation_clicked(self) -> None:
        self.capture_translation_requested.emit()

    def _on_capture_rotation_clicked(self) -> None:
        self.capture_rotation_requested.emit()

    def _sync_translation_guide(self) -> None:
        if self._reference_pose is None or self._translation_pose is None:
            self._translation_guide.set_selected_axis(None)
            return
        result = dominant_axis(
            self._reference_pose.position_delta(self._translation_pose),
            min_abs=1.0,
        )
        if result is None:
            self._translation_guide.set_selected_axis(None)
            return
        axis, delta = result
        self._translation_guide.set_selected_axis(axis, delta)

    def _sync_rotation_guide(self) -> None:
        if self._reference_pose is None or self._rotation_pose is None:
            self._rotation_guide.set_selected_axis(None)
            return
        result = dominant_axis(
            self._reference_pose.rotation_delta(self._rotation_pose),
            min_abs=1.0,
        )
        if result is None:
            self._rotation_guide.set_selected_axis(None)
            return
        axis, delta = result
        self._rotation_guide.set_selected_axis(axis, delta)
