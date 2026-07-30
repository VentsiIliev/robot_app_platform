#!/usr/bin/env python3
from __future__ import annotations

import json
import sys
from dataclasses import dataclass, field
from typing import Iterable

from PyQt6.QtCore import Qt
from PyQt6.QtWidgets import (
    QApplication,
    QGridLayout,
    QGroupBox,
    QHBoxLayout,
    QLabel,
    QPlainTextEdit,
    QToolTip,
    QVBoxLayout,
    QWizard,
    QWizardPage,
    QWidget,
)

from pl_gui.settings.settings_view.styles import (
    BG_COLOR,
    BORDER,
    GROUP_STYLE,
    LABEL_STYLE,
    PRIMARY,
    PRIMARY_LIGHT,
    SECONDARY_BG,
    TEXT_COLOR,
    TERTIARY_BG,
)
from pl_gui.utils.utils_widgets.MaterialButton import MaterialButton
from pl_gui.utils.utils_widgets.wizards import ConfigurableWizard
from src.applications.base.app_styles import (
    APP_PRIMARY_BUTTON_STYLE,
    APP_SECONDARY_BUTTON_STYLE,
    muted_text_style,
)
from src.applications.base.drawer_toggle import DrawerToggle
from src.applications.base.robot_jog_widget import RobotJogWidget
from src.applications.base.styled_message_box import ask_yes_no, show_warning


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

_STATUS_DONE = "Done"
_STATUS_PENDING = "Pending"


@dataclass(frozen=True)
class Pose6D:
    x: float
    y: float
    z: float
    rx: float
    ry: float
    rz: float

    def as_list(self) -> list[float]:
        return [self.x, self.y, self.z, self.rx, self.ry, self.rz]


@dataclass
class CalibrationWorkflowState:
    current_pose: Pose6D = field(default_factory=lambda: Pose6D(100, -300, 300, 180, 0, 0))
    board_placed: bool = False
    camera_calibrated: bool = False
    robot_calibrated: bool = False
    camera_tcp_offset_calibrated: bool = False
    camera_center_pose: Pose6D | None = None
    tool_point_pose: Pose6D | None = None

    def as_summary(self) -> dict:
        return {
            "development_only": True,
            "board_placed": self.board_placed,
            "camera_calibrated": self.camera_calibrated,
            "robot_calibrated": self.robot_calibrated,
            "camera_tcp_offset_calibrated": self.camera_tcp_offset_calibrated,
            "physical_point_alignment": {
                "camera_center_pose": self.camera_center_pose.as_list()
                if self.camera_center_pose else None,
                "tool_or_gripper_pose": self.tool_point_pose.as_list()
                if self.tool_point_pose else None,
            },
            "notes": [
                "This probe is robot-system agnostic and does not call real robot or camera services.",
                "Future integration should replace simulated step completion with service calls.",
                "The final physical-point step captures the same real point twice: once with camera center aligned, then once with tool or gripper aligned.",
            ],
        }


def _action_button(text: str) -> MaterialButton:
    button = MaterialButton(text)
    button.setStyleSheet(APP_PRIMARY_BUTTON_STYLE)
    button.setAutoDefault(False)
    button.setDefault(False)
    return button


def _secondary_button(text: str) -> MaterialButton:
    button = MaterialButton(text)
    button.setStyleSheet(APP_SECONDARY_BUTTON_STYLE)
    button.setAutoDefault(False)
    button.setDefault(False)
    return button


def _label(text: str) -> QLabel:
    label = QLabel(text)
    label.setStyleSheet(LABEL_STYLE)
    return label


class PoseReadout(QWidget):
    def __init__(self, initial: Iterable[float] = (0, 0, 300, 180, 0, 0)) -> None:
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

    def set_pose(self, pose: Pose6D | None) -> None:
        if pose is None:
            for label in self._values.values():
                label.setProperty("raw_value", None)
                label.setText("-")
            return
        for name, value in zip(("x", "y", "z", "rx", "ry", "rz"), pose.as_list()):
            suffix = "mm" if name in AXES else "deg"
            self._values[name].setProperty("raw_value", float(value))
            self._values[name].setText(f"{float(value):.3f} {suffix}")


def _pose_group(title: str, widget: QWidget) -> QGroupBox:
    group = QGroupBox(title)
    group.setStyleSheet(GROUP_STYLE)
    layout = QVBoxLayout(group)
    layout.setContentsMargins(14, 18, 14, 14)
    layout.addWidget(widget)
    return group


class StatusRow(QWidget):
    def __init__(self, title: str) -> None:
        super().__init__()
        self._status = QLabel(_STATUS_PENDING)
        self._status.setAlignment(Qt.AlignmentFlag.AlignCenter)
        self._status.setMinimumWidth(120)
        self._status.setStyleSheet(_READOUT_VALUE_STYLE)

        layout = QHBoxLayout(self)
        layout.setContentsMargins(0, 0, 0, 0)
        layout.addWidget(_label(title))
        layout.addStretch()
        layout.addWidget(self._status)

    def set_done(self, done: bool) -> None:
        self._status.setText(_STATUS_DONE if done else _STATUS_PENDING)


class CalibrationWizardPage(QWizardPage):
    def __init__(self, state: CalibrationWorkflowState, title: str, info_text: str) -> None:
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

    def nextId(self) -> int:
        wizard = self.wizard()
        if wizard is None:
            return super().nextId()
        page_ids = wizard.pageIds()
        try:
            index = page_ids.index(wizard.currentId())
        except ValueError:
            return super().nextId()
        if index + 1 >= len(page_ids):
            return -1
        return page_ids[index + 1]

    def _add_step_header(self, layout: QVBoxLayout) -> None:
        row = QHBoxLayout()
        row.setContentsMargins(0, 0, 0, 0)
        row.setSpacing(8)

        title = QLabel(self._title)
        title.setStyleSheet(_STEP_TITLE_STYLE)
        info = MaterialButton("i")
        info.setStyleSheet(_INFO_BUTTON_STYLE)
        info.clicked.connect(lambda: self._show_info_bubble(info))

        row.addWidget(title)
        row.addWidget(info)
        row.addStretch()
        layout.addLayout(row)

    def _show_info_bubble(self, button: MaterialButton) -> None:
        pos = button.mapToGlobal(button.rect().bottomLeft())
        QToolTip.showText(pos, self._info_text, button)

    def _add_development_notice(self, layout: QVBoxLayout) -> None:
        notice = QLabel("Development probe only: no real calibration service or robot command is executed.")
        notice.setWordWrap(True)
        notice.setStyleSheet(_notice_style())
        layout.addWidget(notice)

    @staticmethod
    def _pose_data(pose: Pose6D) -> dict[str, float]:
        return dict(zip(("x", "y", "z", "rx", "ry", "rz"), pose.as_list()))

    @staticmethod
    def set_jog_buttons_enabled(jog: RobotJogWidget, names: tuple[str, ...], enabled: bool) -> None:
        for name in names:
            button = getattr(jog, name, None)
            if button is not None:
                button.setEnabled(enabled)


def _notice_style() -> str:
    return (
        f"background: {SECONDARY_BG}; color: {TEXT_COLOR}; border: 1px solid {BORDER}; "
        "border-radius: 8px; padding: 8px 12px; font-size: 10pt;"
    )


class PlaceBoardPage(CalibrationWizardPage):
    def __init__(self, state: CalibrationWorkflowState) -> None:
        super().__init__(
            state,
            "Step 1: Place Calibration Board",
            "Place the calibration board in the camera view and make sure it is stable before starting camera calibration.",
        )
        layout = QVBoxLayout(self)
        layout.setSpacing(12)
        self._add_step_header(layout)
        self._add_development_notice(layout)

        instruction = QLabel(
            "Place the board in the work area, keep it flat/stable, and verify it is visible to the camera."
        )
        instruction.setWordWrap(True)
        instruction.setStyleSheet(_notice_style())
        layout.addWidget(instruction)

        self._status = StatusRow("Board placement")
        layout.addWidget(_pose_group("Step Status", self._status))

        action = _action_button("Board Is Placed")
        action.clicked.connect(self._mark_board_placed)
        row = QHBoxLayout()
        row.addWidget(action)
        row.addStretch()
        layout.addLayout(row)
        layout.addStretch()

    def initializePage(self) -> None:
        self._status.set_done(self._state.board_placed)

    def isComplete(self) -> bool:
        return self._state.board_placed

    def _mark_board_placed(self) -> None:
        self._state.board_placed = True
        self.initializePage()
        self.completeChanged.emit()


class SimulatedCalibrationPage(CalibrationWizardPage):
    def __init__(
        self,
        state: CalibrationWorkflowState,
        *,
        title: str,
        info_text: str,
        status_title: str,
        button_text: str,
        confirm_title: str | None = None,
        confirm_text: str | None = None,
    ) -> None:
        super().__init__(state, title, info_text)
        self._status_title = status_title
        self._confirm_title = confirm_title
        self._confirm_text = confirm_text
        layout = QVBoxLayout(self)
        layout.setSpacing(12)
        self._add_step_header(layout)
        self._add_development_notice(layout)

        self._status = StatusRow(status_title)
        layout.addWidget(_pose_group("Step Status", self._status))

        action = _action_button(button_text)
        action.clicked.connect(self._run_step)
        row = QHBoxLayout()
        row.addWidget(action)
        row.addStretch()
        layout.addLayout(row)
        layout.addStretch()

    def initializePage(self) -> None:
        self._status.set_done(self._is_done())

    def isComplete(self) -> bool:
        return self._is_done()

    def _run_step(self) -> None:
        if self._confirm_title and self._confirm_text:
            if not ask_yes_no(self, self._confirm_title, self._confirm_text, default_no=True):
                return
        self._set_done()
        self.initializePage()
        self.completeChanged.emit()

    def _is_done(self) -> bool:
        raise NotImplementedError

    def _set_done(self) -> None:
        raise NotImplementedError


class CameraCalibrationPage(SimulatedCalibrationPage):
    def __init__(self, state: CalibrationWorkflowState) -> None:
        super().__init__(
            state,
            title="Step 2: Camera Calibration",
            info_text="Run intrinsic camera calibration after the board is placed and visible.",
            status_title="Camera calibration",
            button_text="Run Camera Calibration",
            confirm_title="Confirm Camera Calibration",
            confirm_text=(
                "Camera calibration may move the robot in the real workflow. "
                "Make sure the board is placed correctly and the robot path is clear. "
                "Continue with the simulated development step?"
            ),
        )

    def _is_done(self) -> bool:
        return self._state.camera_calibrated

    def _set_done(self) -> None:
        self._state.camera_calibrated = True


class RobotCalibrationPage(SimulatedCalibrationPage):
    def __init__(self, state: CalibrationWorkflowState) -> None:
        super().__init__(
            state,
            title="Step 3: Robot Calibration",
            info_text="Run robot calibration after camera calibration is complete.",
            status_title="Robot calibration",
            button_text="Run Robot Calibration",
            confirm_title="Confirm Robot Calibration",
            confirm_text="Robot calibration may move the robot in the real workflow. Continue with the simulated development step?",
        )

    def _is_done(self) -> bool:
        return self._state.robot_calibrated

    def _set_done(self) -> None:
        self._state.robot_calibrated = True


class CameraTcpOffsetPage(SimulatedCalibrationPage):
    def __init__(self, state: CalibrationWorkflowState) -> None:
        super().__init__(
            state,
            title="Step 4: Camera to TCP Offset Calibration",
            info_text="Run camera-to-TCP offset calibration after robot calibration.",
            status_title="Camera to TCP offset calibration",
            button_text="Run Camera to TCP Offset Calibration",
            confirm_title="Confirm Camera TCP Offset Calibration",
            confirm_text="Camera-to-TCP offset calibration may rotate and recenter the robot in the real workflow. Continue with the simulated development step?",
        )

    def _is_done(self) -> bool:
        return self._state.camera_tcp_offset_calibrated

    def _set_done(self) -> None:
        self._state.camera_tcp_offset_calibrated = True


class PhysicalPointAlignmentPage(CalibrationWizardPage):
    def __init__(self, state: CalibrationWorkflowState) -> None:
        super().__init__(
            state,
            "Step 5: Align Shared Physical Point",
            "Align the camera center to a real physical point and capture the pose. Then align the tool or gripper to the same physical point and capture the pose.",
        )
        layout = QVBoxLayout(self)
        layout.setSpacing(12)
        self._add_step_header(layout)
        self._add_development_notice(layout)

        self._current = PoseReadout(state.current_pose.as_list())
        self._camera = PoseReadout()
        self._tool = PoseReadout()
        layout.addWidget(_pose_group("Current Pose", self._current))
        layout.addWidget(_pose_group("Camera Center Aligned Pose", self._camera))
        layout.addWidget(_pose_group("Tool / Gripper Aligned Pose", self._tool))

        actions = QHBoxLayout()
        capture_camera = _action_button("Capture Camera Center Pose")
        capture_camera.clicked.connect(self._capture_camera_center)
        capture_tool = _action_button("Capture Tool / Gripper Pose")
        capture_tool.clicked.connect(self._capture_tool_point)
        reset = _secondary_button("Clear Captures")
        reset.clicked.connect(self._clear_captures)
        actions.addWidget(capture_camera)
        actions.addWidget(capture_tool)
        actions.addWidget(reset)
        actions.addStretch()
        layout.addLayout(actions)
        layout.addStretch()

    def initializePage(self) -> None:
        self._current.set_pose(self._state.current_pose)
        self._camera.set_pose(self._state.camera_center_pose)
        self._tool.set_pose(self._state.tool_point_pose)

    def isComplete(self) -> bool:
        return self._state.camera_center_pose is not None and self._state.tool_point_pose is not None

    def _capture_camera_center(self) -> None:
        self._state.camera_center_pose = self._state.current_pose
        self.initializePage()
        self.completeChanged.emit()

    def _capture_tool_point(self) -> None:
        if self._state.camera_center_pose is None:
            show_warning(self, "Camera Center Pose Required", "Capture the camera center pose first.")
            return
        self._state.tool_point_pose = self._state.current_pose
        self.initializePage()
        self.completeChanged.emit()

    def _clear_captures(self) -> None:
        self._state.camera_center_pose = None
        self._state.tool_point_pose = None
        self.initializePage()
        self.completeChanged.emit()

    def update_current_pose(self) -> None:
        self.initializePage()
        self.completeChanged.emit()


class FinishPage(CalibrationWizardPage):
    def __init__(self, state: CalibrationWorkflowState) -> None:
        super().__init__(
            state,
            "Step 6: Finish",
            "Review the development-only calibration workflow summary.",
        )
        layout = QVBoxLayout(self)
        layout.setSpacing(12)
        self._add_step_header(layout)
        self._output = QPlainTextEdit()
        self._output.setReadOnly(True)
        self._output.setStyleSheet(_OUTPUT_STYLE)
        layout.addWidget(self._output, stretch=1)

    def initializePage(self) -> None:
        self._output.setPlainText(json.dumps(self._state.as_summary(), indent=2))

    def isComplete(self) -> bool:
        return True


def create_calibration_workflow_wizard(
    state: CalibrationWorkflowState | None = None,
) -> ConfigurableWizard:
    workflow_state = state or CalibrationWorkflowState()
    pages = [
        PlaceBoardPage(workflow_state),
        CameraCalibrationPage(workflow_state),
        RobotCalibrationPage(workflow_state),
        CameraTcpOffsetPage(workflow_state),
        PhysicalPointAlignmentPage(workflow_state),
        FinishPage(workflow_state),
    ]
    wizard = ConfigurableWizard(
        title="Calibration Workflow Probe",
        pages=pages,
        min_width=1180,
        min_height=760,
        use_material_buttons=False,
    )
    wizard.setStyleSheet(f"background-color: {BG_COLOR};")
    _install_wizard_buttons(wizard)
    _install_jog_drawer(wizard, workflow_state, pages)
    _wire_step_button_gating(wizard, pages)
    return wizard


def _install_wizard_buttons(wizard: ConfigurableWizard) -> None:
    for button_type in (
        QWizard.WizardButton.BackButton,
        QWizard.WizardButton.NextButton,
        QWizard.WizardButton.FinishButton,
        QWizard.WizardButton.CancelButton,
    ):
        current = wizard.button(button_type)
        if current is None:
            continue
        button = MaterialButton(current.text())
        button.setAutoDefault(False)
        button.setDefault(False)
        wizard.setButton(button_type, button)


def _install_jog_drawer(
    wizard: ConfigurableWizard,
    state: CalibrationWorkflowState,
    pages: list[QWizardPage],
) -> None:
    drawer = DrawerToggle(wizard, side="right", width=340)
    jog = RobotJogWidget()
    jog.enable_frame_selector(False)
    drawer.add_widget(jog)
    drawer.set_visible(True)
    allowed_jog_keys: set[str] = set()

    wizard._calibration_probe_jog_drawer = drawer
    wizard._calibration_probe_jog_widget = jog

    def sync_drawer() -> None:
        jog.set_position(state.current_pose.as_list())
        CalibrationWizardPage.set_jog_buttons_enabled(jog, LINEAR_JOG_BUTTONS, True)
        CalibrationWizardPage.set_jog_buttons_enabled(jog, ROTATION_JOG_BUTTONS, True)

    def on_jog_started(key: str) -> None:
        allowed_jog_keys.add(key)

    def on_jog_stopped(key: str) -> None:
        allowed_jog_keys.discard(key)
        timer = getattr(jog, "_timers", {}).get(key)
        if timer is not None:
            timer.stop()

    def on_jog_requested(_command: str, axis: str, direction: str, step: float) -> None:
        axis_name = axis.lower()
        key = f"{axis_name}_{direction.lower()}"
        if key not in allowed_jog_keys:
            return
        allowed_jog_keys.discard(key)
        timer = getattr(jog, "_timers", {}).get(key)
        if timer is not None:
            timer.stop()
        if axis_name not in (*AXES, *ROT_AXES):
            return
        delta = float(step) if direction == "Plus" else -float(step)
        data = CalibrationWizardPage._pose_data(state.current_pose)
        data[axis_name] += delta
        state.current_pose = Pose6D(**data)
        page = wizard.currentPage()
        if isinstance(page, PhysicalPointAlignmentPage):
            page.update_current_pose()
        sync_drawer()

    for page in pages:
        if isinstance(page, CalibrationWizardPage):
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
    wizard = create_calibration_workflow_wizard()
    wizard.show()
    return app.exec()


if __name__ == "__main__":
    raise SystemExit(main())
