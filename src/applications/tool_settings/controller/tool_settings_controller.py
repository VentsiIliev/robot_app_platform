import logging

from PyQt6.QtCore import QObject, QThread, Qt, pyqtSignal
from PyQt6.QtWidgets import (
    QComboBox, QDialog, QHBoxLayout, QLabel, QLineEdit, QPushButton, QSpinBox,
    QTabWidget, QTableWidget, QTableWidgetItem, QVBoxLayout, QWidget,
)

from src.applications.base.app_dialog import (
    AppDialog, DIALOG_COMBO_STYLE, DIALOG_INPUT_STYLE,
)
from src.applications.base.i_application_controller import IApplicationController
from src.applications.base.styled_message_box import show_warning, ask_yes_no
from pl_gui.settings.settings_view.styles import LABEL_STYLE
from src.applications.base.widgets.custom_virtual_keyboard import (
    KeyboardDoubleSpinBox, KeyboardLineEdit, KeyboardSpinBox,
)
from ..model.tool_settings_model import ToolSettingsModel
from ..view.tool_settings_view import ToolSettingsView

_logger = logging.getLogger(__name__)


class _Worker(QObject):
    finished = pyqtSignal(object)

    def __init__(self, fn):
        super().__init__()
        self._fn = fn

    def run(self):
        try:
            self.finished.emit(self._fn())
        except Exception as exc:
            self.finished.emit((False, str(exc)))


def _lbl(text: str) -> QLabel:
    lbl = QLabel(text)
    lbl.setStyleSheet(LABEL_STYLE)
    return lbl


class ToolSettingsController(IApplicationController):

    def __init__(self, model: ToolSettingsModel, view: ToolSettingsView):
        self._model = model
        self._view  = view
        self._active = []

    def load(self) -> None:
        self._connect_signals()
        self._refresh()

    def stop(self) -> None:
        for thread, _worker in list(self._active):
            thread.quit()
            thread.wait(1000)
        self._active.clear()

    def _connect_signals(self) -> None:
        self._view.add_tool_requested.connect(self._on_add)
        self._view.edit_tool_requested.connect(self._on_edit)
        self._view.remove_tool_requested.connect(self._on_remove)
        self._view.add_slot_requested.connect(self._on_add_slot)
        self._view.remove_slot_requested.connect(self._on_remove_slot)
        self._view.save_slots_requested.connect(self._on_save_slots)
        self._view.edit_slot_requested.connect(self._on_edit_slot)
        self._view.edit_geometry_requested.connect(self._on_edit_geometry)
        self._view.activate_tool_requested.connect(self._on_activate_tool)
        self._view.capture_reference_requested.connect(self._on_capture_reference)
        self._view.capture_candidate_requested.connect(self._on_capture_candidate)
        self._view.solve_calibration_requested.connect(self._on_solve_calibration)
        self._view.edit_sequences_requested.connect(self._on_edit_sequences)

    def _refresh(self) -> None:
        tools = self._model.get_tools()
        slots = self._model.get_slots()
        self._view.set_tools(tools)
        self._view.set_slots(slots, tools)
        self._view.set_status(f"{len(tools)} tool(s), {len(slots)} slot(s)")

    def _on_add(self) -> None:
        dialog = _ToolDialog(parent=self._view)
        if dialog.exec() != QDialog.DialogCode.Accepted:
            return
        tool_id, name = dialog.get_values()
        ok, msg = self._model.add_tool(tool_id, name)
        self._view.set_status(msg)
        if ok:
            self._refresh()
        else:
            show_warning(self._view, "Add Tool", msg)

    def _on_edit(self, tool_id: int, current_name: str) -> None:
        dialog = _ToolDialog(tool_id=tool_id, name=current_name, parent=self._view)
        if dialog.exec() != QDialog.DialogCode.Accepted:
            return
        _, name = dialog.get_values()
        ok, msg = self._model.update_tool(tool_id, name)
        self._view.set_status(msg)
        if ok:
            self._refresh()
        else:
            show_warning(self._view, "Edit Tool", msg)

    def _on_remove(self, tool_id: int) -> None:
        if not ask_yes_no(self._view, "Remove Tool", f"Remove tool ID {tool_id}?"):
            return
        ok, msg = self._model.remove_tool(tool_id)
        self._view.set_status(msg)
        if ok:
            self._refresh()
        else:
            show_warning(self._view, "Remove Tool", msg)

    def _on_add_slot(self) -> None:
        tools = self._model.get_tools()
        if not tools:
            show_warning(self._view, "Add Slot", "Add at least one tool first.")
            return
        dialog = _SlotDialog(tools=tools, parent=self._view)
        if dialog.exec() != QDialog.DialogCode.Accepted:
            return
        slot_id, tool_id = dialog.get_values()
        ok, msg = self._model.add_slot(slot_id, tool_id)
        self._view.set_status(msg)
        if ok:
            self._refresh()
        else:
            show_warning(self._view, "Add Slot", msg)

    def _on_remove_slot(self, slot_id: int) -> None:
        if not ask_yes_no(self._view, "Remove Slot", f"Remove slot {slot_id}?"):
            return
        ok, msg = self._model.remove_slot(slot_id)
        self._view.set_status(msg)
        if ok:
            self._refresh()
        else:
            show_warning(self._view, "Remove Slot", msg)

    def _on_save_slots(self, assignments: list) -> None:
        errors = []
        for slot_id, tool_id in assignments:
            ok, msg = self._model.update_slot(slot_id, tool_id)
            if not ok:
                errors.append(msg)
        if errors:
            show_warning(self._view, "Save Slots", "\n".join(errors))
        else:
            self._view.set_status("Slots saved")
            self._refresh()

    def _on_edit_slot(self, slot_id: int, current_tool_id) -> None:
        tools = self._model.get_tools()
        if not tools:
            show_warning(self._view, "Edit Slot", "No tools defined.")
            return
        dialog = _SlotDialog(tools=tools, slot_id=slot_id, current_tool_id=current_tool_id, parent=self._view)
        if dialog.exec() != QDialog.DialogCode.Accepted:
            return
        _, tool_id = dialog.get_values()
        ok, msg = self._model.update_slot(slot_id, tool_id)
        self._view.set_status(msg)
        if ok:
            self._refresh()
        else:
            show_warning(self._view, "Edit Slot", msg)

    def _on_edit_geometry(self, tool_id: int) -> None:
        tool = next((item for item in self._model.get_tools() if item.id == tool_id), None)
        if tool is None:
            return
        dialog = _ToolGeometryDialog(tool, parent=self._view)
        if dialog.exec() != QDialog.DialogCode.Accepted:
            return
        transform, collision_profile = dialog.get_values()
        ok, msg = self._model.update_tool_geometry(tool_id, transform, collision_profile)
        self._view.set_status(msg)
        if ok:
            self._refresh()
        else:
            show_warning(self._view, "Tool Offsets", msg)

    def _on_capture_reference(self) -> None:
        self._run_blocking(self._model.capture_reference_contact, self._show_simple_result)

    def _on_capture_candidate(self) -> None:
        self._run_blocking(self._model.capture_tool_contact, self._show_calibration_result)

    def _on_solve_calibration(self, tool_id: int) -> None:
        self._run_blocking(
            lambda: self._model.solve_tool_calibration(tool_id),
            self._show_calibration_result,
        )

    def _on_activate_tool(self, tool_id: int) -> None:
        self._run_blocking(lambda: self._model.activate_tool(tool_id), self._show_simple_result)

    def _on_edit_sequences(self, slot_id: int) -> None:
        slot = next((item for item in self._model.get_slots() if item.id == slot_id), None)
        if slot is None:
            return
        dialog = _SequenceDialog(slot, self._model.get_current_motion_pose, parent=self._view)
        if dialog.exec() != QDialog.DialogCode.Accepted:
            return
        pickup, dropoff = dialog.get_values()
        ok, msg = self._model.update_slot_sequences(slot_id, pickup, dropoff)
        self._view.set_status(msg)
        if not ok:
            show_warning(self._view, "Teach Sequences", msg)
        else:
            self._refresh()

    def _show_simple_result(self, result) -> None:
        ok, msg = result[:2]
        self._view.set_status(msg)
        if not ok:
            show_warning(self._view, "Tools & Magazine", msg)
        else:
            self._refresh()

    def _show_calibration_result(self, result) -> None:
        ok, msg = result[:2]
        payload = result[2] if len(result) > 2 else {}
        if ok and payload.get("sample_count"):
            msg = (
                f"{msg}; samples={payload['sample_count']}, "
                f"spread={float(payload.get('max_spread_mm', 0.0)):.3f} mm"
            )
        self._view.set_status(msg)
        if not ok:
            show_warning(self._view, "Tool Calibration", msg)
        else:
            self._refresh()

    def _run_blocking(self, fn, on_done) -> None:
        thread = QThread(self._view)
        worker = _Worker(fn)
        worker.moveToThread(thread)
        thread.started.connect(worker.run)
        worker.finished.connect(on_done)
        worker.finished.connect(thread.quit)
        worker.finished.connect(lambda _result, t=thread, w=worker: self._release_worker(t, w))
        self._active.append((thread, worker))
        thread.start()

    def _release_worker(self, thread, worker) -> None:
        try:
            self._active.remove((thread, worker))
        except ValueError:
            pass
        worker.deleteLater()
        thread.deleteLater()


# ── Dialogs ───────────────────────────────────────────────────────────────────

class _ToolDialog(AppDialog):

    def __init__(self, tool_id=None, name: str = "", parent=None):
        title = "Edit Tool" if tool_id is not None else "Add Tool"
        super().__init__(title, min_width=360, parent=parent)
        self._fixed_id = tool_id

        root = QVBoxLayout(self)
        root.setContentsMargins(24, 24, 24, 24)
        root.setSpacing(12)

        root.addWidget(_lbl("Tool ID"))
        self._id_spin = KeyboardSpinBox()
        self._id_spin.setRange(0, 9999)
        self._id_spin.setStyleSheet(DIALOG_INPUT_STYLE)
        self._id_spin.setCursor(Qt.CursorShape.PointingHandCursor)
        if tool_id is not None:
            self._id_spin.setValue(tool_id)
            self._id_spin.setEnabled(False)
        root.addWidget(self._id_spin)

        root.addWidget(_lbl("Name"))
        self._name_edit = KeyboardLineEdit(name)
        self._name_edit.setPlaceholderText("e.g. Single Gripper")
        self._name_edit.setStyleSheet(DIALOG_INPUT_STYLE)
        root.addWidget(self._name_edit)

        root.addStretch()
        ok_label = "Save" if tool_id is not None else "Add"
        root.addWidget(self._build_button_row(ok_label=ok_label))

    def get_values(self):
        return self._id_spin.value(), self._name_edit.text().strip()


class _SlotDialog(AppDialog):

    def __init__(self, tools, slot_id=None, current_tool_id=None, parent=None):
        title = "Edit Slot" if slot_id is not None else "Add Slot"
        super().__init__(title, min_width=360, parent=parent)

        root = QVBoxLayout(self)
        root.setContentsMargins(24, 24, 24, 24)
        root.setSpacing(12)

        root.addWidget(_lbl("Slot ID"))
        self._slot_spin = KeyboardSpinBox()
        self._slot_spin.setRange(0, 9999)
        self._slot_spin.setStyleSheet(DIALOG_INPUT_STYLE)
        self._slot_spin.setCursor(Qt.CursorShape.PointingHandCursor)
        if slot_id is not None:
            self._slot_spin.setValue(slot_id)
            self._slot_spin.setEnabled(False)
        root.addWidget(self._slot_spin)

        root.addWidget(_lbl("Tool"))
        self._tool_combo = QComboBox()
        self._tool_combo.setStyleSheet(DIALOG_COMBO_STYLE)
        self._tool_combo.addItem("— Unassigned —", None)
        for t in tools:
            self._tool_combo.addItem(f"{t.name}  (ID {t.id})", t.id)
        idx = self._tool_combo.findData(current_tool_id)
        self._tool_combo.setCurrentIndex(idx if idx >= 0 else 0)
        root.addWidget(self._tool_combo)

        root.addStretch()
        ok_label = "Save" if slot_id is not None else "Add"
        root.addWidget(self._build_button_row(ok_label=ok_label))

    def get_values(self):
        return self._slot_spin.value(), self._tool_combo.currentData()


class _ToolGeometryDialog(AppDialog):
    def __init__(self, tool, parent=None):
        super().__init__("Tool TCP Offsets", min_width=420, parent=parent)
        root = QVBoxLayout(self)
        root.setContentsMargins(24, 24, 24, 24)
        root.setSpacing(10)
        root.addWidget(_lbl(f"{tool.name} (Tool {tool.id}) — relative to calibration tool"))
        transform = list(getattr(tool, "relative_transform", [0, 0, 0, 0, 0, 0]))
        self._offsets = []
        for index, axis in enumerate(("X offset (mm)", "Y offset (mm)", "Z offset (mm)")):
            root.addWidget(_lbl(axis))
            field = KeyboardDoubleSpinBox()
            field.setRange(-2000.0, 2000.0)
            field.setDecimals(3)
            field.setValue(float(transform[index]))
            field.setStyleSheet(DIALOG_INPUT_STYLE)
            self._offsets.append(field)
            root.addWidget(field)
        root.addWidget(_lbl("Collision profile"))
        self._collision = KeyboardLineEdit(str(getattr(tool, "collision_profile", "")))
        self._collision.setPlaceholderText("e.g. vacuum_gripper")
        self._collision.setStyleSheet(DIALOG_INPUT_STYLE)
        root.addWidget(self._collision)
        root.addWidget(self._build_button_row(ok_label="Save Offsets"))

    def get_values(self):
        xyz = [field.value() for field in self._offsets]
        return xyz + [0.0, 0.0, 0.0], self._collision.text().strip()


class _SequencePage(QWidget):
    def __init__(self, steps, pose_provider, parent=None):
        super().__init__(parent)
        self._pose_provider = pose_provider
        root = QVBoxLayout(self)
        self._table = QTableWidget(0, 3)
        self._table.setHorizontalHeaderLabels(["Step", "Type", "Pose / Details"])
        self._table.horizontalHeader().setStretchLastSection(True)
        root.addWidget(self._table)
        buttons = QHBoxLayout()
        for label, callback in (
            ("Capture Motion", self._capture_motion),
            ("Attach", self._add_attach),
            ("Detach", self._add_detach),
            ("Confirm", self._add_confirm),
            ("Remove", self._remove),
        ):
            button = QPushButton(label)
            button.setCursor(Qt.CursorShape.PointingHandCursor)
            button.clicked.connect(callback)
            buttons.addWidget(button)
        root.addLayout(buttons)
        for step in steps:
            self._append(step.to_dict() if hasattr(step, "to_dict") else dict(step))

    def _capture_motion(self):
        ok, message, pose = self._pose_provider()
        if not ok:
            show_warning(self, "Capture Motion", message)
            return
        self._append({
            "kind": "motion", "label": f"Motion {self._table.rowCount() + 1}",
            "pose": pose, "motion_type": "linear", "velocity": 10.0,
            "acceleration": 10.0, "blend_radius": 0.0,
        })

    def _add_attach(self): self._append({"kind": "attach", "label": "Attach tool"})
    def _add_detach(self): self._append({"kind": "detach", "label": "Detach tool"})
    def _add_confirm(self): self._append({"kind": "operator_confirm", "label": "Confirm tool state"})

    def _remove(self):
        row = self._table.currentRow()
        if row >= 0:
            self._table.removeRow(row)
            self._renumber()

    def _append(self, step):
        row = self._table.rowCount()
        self._table.insertRow(row)
        self._table.setItem(row, 0, QTableWidgetItem(str(row + 1)))
        self._table.setItem(row, 1, QTableWidgetItem(str(step.get("kind", "motion"))))
        label = str(step.get("label", ""))
        if step.get("kind") == "motion":
            pose = ", ".join(f"{float(value):.3f}" for value in step.get("pose", []))
            details = f"{label} | {pose}"
        else:
            details = label
        item = QTableWidgetItem(details)
        item.setData(Qt.ItemDataRole.UserRole, step)
        self._table.setItem(row, 2, item)

    def _renumber(self):
        for row in range(self._table.rowCount()):
            self._table.setItem(row, 0, QTableWidgetItem(str(row + 1)))

    def values(self):
        return [
            dict(self._table.item(row, 2).data(Qt.ItemDataRole.UserRole))
            for row in range(self._table.rowCount())
        ]

    def set_values(self, steps):
        self._table.setRowCount(0)
        for step in steps:
            self._append(step)


class _SequenceDialog(AppDialog):
    def __init__(self, slot, pose_provider, parent=None):
        super().__init__(f"Teach Slot {slot.id} Sequences", min_width=850, parent=parent)
        root = QVBoxLayout(self)
        root.setContentsMargins(20, 20, 20, 20)
        root.addWidget(QLabel(
            "Capture poses in execution order. Insert Attach/Detach exactly where the physical tool state changes."
        ))
        tabs = QTabWidget()
        self._pickup = _SequencePage(slot.pickup_sequence, pose_provider)
        self._dropoff = _SequencePage(slot.dropoff_sequence, pose_provider)
        tabs.addTab(self._pickup, "Pickup")
        tabs.addTab(self._dropoff, "Drop-off")
        root.addWidget(tabs)
        reverse = QPushButton("Generate Drop-off by Reversing Pickup")
        reverse.clicked.connect(self._reverse_pickup)
        root.addWidget(reverse)
        root.addWidget(self._build_button_row(ok_label="Save Sequences"))

    def _reverse_pickup(self):
        reversed_steps = []
        for step in reversed(self._pickup.values()):
            copied = dict(step)
            if copied.get("kind") == "attach":
                copied.update(kind="detach", label="Detach tool")
            elif copied.get("kind") == "detach":
                copied.update(kind="attach", label="Attach tool")
            reversed_steps.append(copied)
        self._dropoff.set_values(reversed_steps)

    def get_values(self):
        return self._pickup.values(), self._dropoff.values()
