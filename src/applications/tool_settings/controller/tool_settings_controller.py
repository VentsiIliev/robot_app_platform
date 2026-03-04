import logging

from PyQt6.QtCore import Qt
from PyQt6.QtWidgets import QComboBox, QDialog, QLabel, QLineEdit, QSpinBox, QVBoxLayout

from src.applications.base.app_dialog import (
    AppDialog, DIALOG_COMBO_STYLE, DIALOG_INPUT_STYLE,
)
from src.applications.base.i_application_controller import IApplicationController
from src.applications.base.styled_message_box import show_warning, ask_yes_no
from pl_gui.settings.settings_view.styles import LABEL_STYLE
from ..model.tool_settings_model import ToolSettingsModel
from ..view.tool_settings_view import ToolSettingsView

_logger = logging.getLogger(__name__)


def _lbl(text: str) -> QLabel:
    lbl = QLabel(text)
    lbl.setStyleSheet(LABEL_STYLE)
    return lbl


class ToolSettingsController(IApplicationController):

    def __init__(self, model: ToolSettingsModel, view: ToolSettingsView):
        self._model = model
        self._view  = view

    def load(self) -> None:
        self._connect_signals()
        self._refresh()

    def stop(self) -> None:
        pass

    def _connect_signals(self) -> None:
        self._view.add_tool_requested.connect(self._on_add)
        self._view.edit_tool_requested.connect(self._on_edit)
        self._view.remove_tool_requested.connect(self._on_remove)
        self._view.add_slot_requested.connect(self._on_add_slot)
        self._view.remove_slot_requested.connect(self._on_remove_slot)
        self._view.save_slots_requested.connect(self._on_save_slots)
        self._view.edit_slot_requested.connect(self._on_edit_slot)

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
        self._id_spin = QSpinBox()
        self._id_spin.setRange(0, 9999)
        self._id_spin.setStyleSheet(DIALOG_INPUT_STYLE)
        self._id_spin.setCursor(Qt.CursorShape.PointingHandCursor)
        if tool_id is not None:
            self._id_spin.setValue(tool_id)
            self._id_spin.setEnabled(False)
        root.addWidget(self._id_spin)

        root.addWidget(_lbl("Name"))
        self._name_edit = QLineEdit(name)
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
        self._slot_spin = QSpinBox()
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
