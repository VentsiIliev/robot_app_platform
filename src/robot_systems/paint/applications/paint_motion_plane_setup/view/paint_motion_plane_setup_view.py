from __future__ import annotations

import json

from PyQt6.QtCore import Qt, pyqtSignal
from PyQt6.QtWidgets import (
    QButtonGroup,
    QFrame,
    QHBoxLayout,
    QLabel,
    QPlainTextEdit,
    QPushButton,
    QRadioButton,
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
    capture_reference_requested = pyqtSignal()
    capture_translation_requested = pyqtSignal()
    capture_rotation_requested = pyqtSignal()
    fixed_axis_selected = pyqtSignal(str)

    def __init__(self) -> None:
        self._current_pose: Pose6D | None = None
        self._paint_pose: Pose6D | None = None
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

    def set_paint_move_complete(self, complete: bool) -> None:
        self._pages["paint"].set_complete(complete)

    def set_reference_pose(self, pose: Pose6D | None) -> None:
        self._reference_readout.set_pose(pose)
        self._pages["reference"].set_complete(pose is not None)

    def set_translation_pose(self, pose: Pose6D | None) -> None:
        self._translation_readout.set_pose(pose)
        self._pages["translation"].set_complete(pose is not None)

    def set_rotation_pose(self, pose: Pose6D | None) -> None:
        self._rotation_readout.set_pose(pose)
        self._pages["rotation"].set_complete(pose is not None)

    def set_result(self, result: dict | None, warnings: tuple[str, ...] = ()) -> None:
        if result is None:
            self._result_output.setPlainText("Capture reference, translation, rotation, and fixed axis to generate a result.")
            return
        payload = {
            "suggested_runtime_config": result,
            "warnings": list(warnings),
        }
        self._result_output.setPlainText(json.dumps(payload, indent=2))

    def set_busy(self, busy: bool, message: str = "") -> None:
        self._busy = busy
        self._status.setText(message or "Ready")
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
        self._paint_pose_readout = _PoseReadout("Paint pose")
        self._move_paint_btn = _button("Move to Paint Position")
        self._move_paint_btn.clicked.connect(self._on_move_paint_clicked)
        self._status = QLabel("Ready")
        self._status.setStyleSheet(_INFO_STYLE)
        paint.content_layout.addWidget(self._paint_pose_readout)
        paint.content_layout.addWidget(self._move_paint_btn)
        paint.content_layout.addWidget(self._status)
        self._add_page("paint", paint)

        reference = _WizardPage(
            "Capture reference pose",
            "Use the jog drawer if needed, then capture the current robot pose as the origin for the axis probe.",
        )
        self._reference_readout = _PoseReadout("Reference")
        self._capture_reference_btn = _button("Set Current as Reference")
        self._capture_reference_btn.clicked.connect(self._on_capture_reference_clicked)
        reference.content_layout.addWidget(self._reference_readout)
        reference.content_layout.addWidget(self._capture_reference_btn)
        self._add_page("reference", reference)

        translation = _WizardPage(
            "Move and capture translation",
            "Jog along the desired paint translation direction, then capture the current pose.",
        )
        self._translation_readout = _PoseReadout("Translation")
        self._capture_translation_btn = _button("Capture Current Translation")
        self._capture_translation_btn.clicked.connect(self._on_capture_translation_clicked)
        translation.content_layout.addWidget(self._translation_readout)
        translation.content_layout.addWidget(self._capture_translation_btn)
        self._add_page("translation", translation)

        rotation = _WizardPage(
            "Move and capture rotation",
            "Return near the reference position if needed, rotate around the desired paint rotation axis, then capture.",
        )
        self._rotation_readout = _PoseReadout("Rotation")
        self._capture_rotation_btn = _button("Capture Current Rotation")
        self._capture_rotation_btn.clicked.connect(self._on_capture_rotation_clicked)
        rotation.content_layout.addWidget(self._rotation_readout)
        rotation.content_layout.addWidget(self._capture_rotation_btn)
        self._add_page("rotation", rotation)

        fixed = _WizardPage(
            "Select fixed axis",
            "Choose the robot position axis that should remain constant while the path is projected in the paint plane.",
        )
        axis_row = QHBoxLayout()
        self._axis_group = QButtonGroup(self)
        for index, axis in enumerate(AXES):
            radio = QRadioButton(axis.upper())
            radio.setStyleSheet(f"color: {TEXT_COLOR}; font-size: 12pt;")
            radio.setCursor(Qt.CursorShape.PointingHandCursor)
            self._axis_group.addButton(radio, index)
            axis_row.addWidget(radio)
        self._axis_group.buttonClicked.connect(self._on_axis_clicked)
        fixed.content_layout.addLayout(axis_row)
        self._add_page("fixed", fixed)

        result = _ResultPage()
        self._result_output = QPlainTextEdit()
        self._result_output.setReadOnly(True)
        self._result_output.setStyleSheet(_OUTPUT_STYLE)
        result.content_layout.addWidget(self._result_output, 1)
        self._add_page("result", result)

    def _add_page(self, key: str, page: _WizardPage) -> None:
        self._pages[key] = page
        self._wizard.addPage(page)

    def _on_move_paint_clicked(self) -> None:
        self.move_to_paint_pose_requested.emit()

    def _on_capture_reference_clicked(self) -> None:
        self.capture_reference_requested.emit()

    def _on_capture_translation_clicked(self) -> None:
        self.capture_translation_requested.emit()

    def _on_capture_rotation_clicked(self) -> None:
        self.capture_rotation_requested.emit()

    def _on_axis_clicked(self, button: QRadioButton) -> None:
        axis = button.text().strip().lower()
        self._pages["fixed"].set_complete(axis in AXES)
        self.fixed_axis_selected.emit(axis)
