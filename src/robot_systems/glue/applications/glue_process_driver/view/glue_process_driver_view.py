from __future__ import annotations

import json

from PyQt6.QtCore import QEvent, Qt, pyqtSignal
from PyQt6.QtWidgets import (
    QCheckBox,
    QGroupBox,
    QHBoxLayout,
    QLabel,
    QListWidget,
    QListWidgetItem,
    QPushButton,
    QTextEdit,
    QVBoxLayout,
)
from pl_gui.settings.settings_view.styles import BG_COLOR, GROUP_STYLE

from src.applications.base.i_application_view import IApplicationView


class GlueProcessDriverView(IApplicationView):
    capture_match_requested = pyqtSignal()
    build_job_requested = pyqtSignal()
    load_job_requested = pyqtSignal(bool)
    manual_mode_toggled = pyqtSignal(bool)
    step_requested = pyqtSignal()
    start_requested = pyqtSignal()
    pause_requested = pyqtSignal()
    resume_requested = pyqtSignal()
    stop_requested = pyqtSignal()
    reset_errors_requested = pyqtSignal()
    refresh_requested = pyqtSignal()

    def __init__(self, parent=None):
        super().__init__("Glue Process Driver", parent)

    def setup_ui(self) -> None:
        self.setStyleSheet(f"background-color: {BG_COLOR};")
        root = QVBoxLayout(self)
        root.setContentsMargins(16, 16, 16, 16)
        root.setSpacing(12)

        controls = QGroupBox("Controls")
        controls.setStyleSheet(GROUP_STYLE)
        controls_layout = QHBoxLayout(controls)
        controls_layout.setSpacing(8)

        self._spray_on = QCheckBox("Spray On")
        self._spray_on.setChecked(True)
        self._manual_mode = QCheckBox("Manual Mode")

        self._btn_capture = QPushButton("Capture + Match")
        self._btn_build = QPushButton("Build Job")
        self._btn_load = QPushButton("Load Job")
        self._btn_step = QPushButton("Step")
        self._btn_start = QPushButton("Start")
        self._btn_pause = QPushButton("Pause")
        self._btn_resume = QPushButton("Resume")
        self._btn_stop = QPushButton("Stop")
        self._btn_reset = QPushButton("Reset Errors")
        self._btn_refresh = QPushButton("Refresh")

        for button in (
            self._btn_capture,
            self._btn_build,
            self._btn_load,
            self._btn_step,
            self._btn_start,
            self._btn_pause,
            self._btn_resume,
            self._btn_stop,
            self._btn_reset,
            self._btn_refresh,
        ):
            button.setCursor(Qt.CursorShape.PointingHandCursor)
            controls_layout.addWidget(button)

        controls_layout.addWidget(self._spray_on)
        controls_layout.addWidget(self._manual_mode)
        root.addWidget(controls)

        self._process_group = QGroupBox("Process Snapshot")
        self._process_group.setStyleSheet(GROUP_STYLE)
        process_layout = QVBoxLayout(self._process_group)
        self._process_summary = QLabel("No process snapshot")
        self._machine_state_summary = QLabel("Previous: - | Current: - | Next: -")
        self._process_dump = QTextEdit()
        self._process_dump.setReadOnly(True)
        process_layout.addWidget(self._process_summary)
        process_layout.addWidget(self._machine_state_summary)
        process_layout.addWidget(self._process_dump)
        root.addWidget(self._process_group)

        self._match_group = QGroupBox("Match Summary")
        self._match_group.setStyleSheet(GROUP_STYLE)
        match_layout = QVBoxLayout(self._match_group)
        self._match_list = QListWidget()
        self._match_list.setSelectionMode(QListWidget.SelectionMode.MultiSelection)
        self._match_dump = QTextEdit()
        self._match_dump.setReadOnly(True)
        match_layout.addWidget(self._match_list)
        match_layout.addWidget(self._match_dump)
        root.addWidget(self._match_group)

        self._job_group = QGroupBox("Job Summary")
        self._job_group.setStyleSheet(GROUP_STYLE)
        job_layout = QVBoxLayout(self._job_group)
        self._job_dump = QTextEdit()
        self._job_dump.setReadOnly(True)
        job_layout.addWidget(self._job_dump)
        root.addWidget(self._job_group)

        self._btn_capture.clicked.connect(self._on_capture_match)
        self._btn_build.clicked.connect(self._on_build_job)
        self._btn_load.clicked.connect(self._on_load_job)
        self._btn_step.clicked.connect(self._on_step)
        self._btn_start.clicked.connect(self._on_start)
        self._btn_pause.clicked.connect(self._on_pause)
        self._btn_resume.clicked.connect(self._on_resume)
        self._btn_stop.clicked.connect(self._on_stop)
        self._btn_reset.clicked.connect(self._on_reset_errors)
        self._btn_refresh.clicked.connect(self._on_refresh)
        self._manual_mode.toggled.connect(self._on_manual_mode_toggled)

    def _on_capture_match(self) -> None:
        self.capture_match_requested.emit()

    def _on_build_job(self) -> None:
        self.build_job_requested.emit()

    def _on_load_job(self) -> None:
        self.load_job_requested.emit(self._spray_on.isChecked())

    def _on_manual_mode_toggled(self, enabled: bool) -> None:
        self.manual_mode_toggled.emit(enabled)

    def _on_step(self) -> None:
        self.step_requested.emit()

    def _on_start(self) -> None:
        self.start_requested.emit()

    def _on_pause(self) -> None:
        self.pause_requested.emit()

    def _on_resume(self) -> None:
        self.resume_requested.emit()

    def _on_stop(self) -> None:
        self.stop_requested.emit()

    def _on_reset_errors(self) -> None:
        self.reset_errors_requested.emit()

    def _on_refresh(self) -> None:
        self.refresh_requested.emit()

    def set_process_snapshot(self, snapshot: dict) -> None:
        process_state = snapshot.get("process_state", "unknown") if isinstance(snapshot, dict) else "unknown"
        self._process_summary.setText(f"Process State: {process_state}")
        machine = snapshot.get("machine") if isinstance(snapshot, dict) else None
        previous_state = self._format_machine_state(machine, "last_state")
        current_state = self._format_machine_state(machine, "current_state")
        next_state = self._format_machine_state(machine, "last_next_state")
        self._machine_state_summary.setText(
            f"Previous: {previous_state} | Current: {current_state} | Next: {next_state}"
        )
        self._process_dump.setPlainText(json.dumps(snapshot, indent=2, sort_keys=True))

    def set_match_summary(self, summary: dict) -> None:
        self._match_dump.setPlainText(json.dumps(summary, indent=2, sort_keys=True))

    def set_matched_workpieces(self, workpieces: list) -> None:
        self._match_list.clear()
        for index, workpiece in enumerate(workpieces):
            item = QListWidgetItem(self._format_workpiece_label(index, workpiece))
            item.setData(Qt.ItemDataRole.UserRole, index)
            self._match_list.addItem(item)
            item.setSelected(True)

    def get_selected_match_indexes(self) -> list[int]:
        items = self._match_list.selectedItems()
        if not items:
            return list(range(self._match_list.count()))
        return [int(item.data(Qt.ItemDataRole.UserRole)) for item in items]

    def set_job_summary(self, job_summary) -> None:
        if job_summary is None:
            self._job_dump.setPlainText("No job built")
            return
        self._job_dump.setPlainText(json.dumps(job_summary, indent=2, sort_keys=True))

    def set_manual_mode_enabled(self, enabled: bool) -> None:
        self._manual_mode.blockSignals(True)
        self._manual_mode.setChecked(enabled)
        self._manual_mode.blockSignals(False)

    def changeEvent(self, event) -> None:
        if event.type() == QEvent.Type.LanguageChange:
            self.on_language_changed()
        super().changeEvent(event)

    def clean_up(self) -> None:
        controller = getattr(self, "_controller", None)
        if controller is None:
            return
        try:
            controller.stop()
        except Exception:
            pass

    def _format_workpiece_label(self, index: int, workpiece) -> str:
        if isinstance(workpiece, dict):
            workpiece_id = workpiece.get("workpieceId") or workpiece.get("name") or f"match-{index}"
        else:
            workpiece_id = getattr(workpiece, "workpieceId", None) or getattr(workpiece, "name", None) or f"match-{index}"
        return f"[{index}] {workpiece_id}"

    def _format_machine_state(self, machine: dict | None, key: str) -> str:
        if not isinstance(machine, dict):
            return "-"
        value = machine.get(key)
        return str(value) if value is not None else "-"
