import logging
from PyQt6.QtCore import pyqtSignal, Qt
from PyQt6.QtWidgets import (
    QVBoxLayout, QHBoxLayout, QLabel, QPushButton,
    QTableWidget, QTableWidgetItem, QHeaderView,
    QGroupBox, QWidget, QTabWidget, QComboBox, QFrame,
)
from PyQt6.QtCore import QEvent
from pl_gui.utils.utils_widgets.table_helpers import make_table
from pl_gui.settings.settings_view.styles import (
    ACTION_BTN_STYLE, APP_PHASE_TAB_STYLE, BG_COLOR, BORDER,
    GHOST_BTN_STYLE, PRIMARY, SECONDARY_BG, STATUS_OK,
    TERTIARY_TEXT, TEXT_COLOR,
)
from src.applications.base.i_application_view import IApplicationView

_logger = logging.getLogger(__name__)
_ACCENT = PRIMARY
_BG = BG_COLOR
_TEXT = TEXT_COLOR
_MUTED = TERTIARY_TEXT
_BORDER = BORDER
_STEP_DONE_STYLE = """
    QPushButton {
        background: #2E7D32; color: white;
        border: none; border-radius: 8px;
        padding: 0 16px; font-size: 11pt; font-weight: bold;
        min-height: 44px;
    }
"""

_TABLE = f"""
    QTableWidget {{
        background: white; alternate-background-color: {SECONDARY_BG}; color: {_TEXT};
        gridline-color: {_BORDER}; border: 1px solid {_BORDER}; border-radius: 10px;
        font-size: 10pt;
    }}
    QTableWidget::item {{ padding: 8px; }}
    QTableWidget::item:selected {{ background: {SECONDARY_BG}; color: {_TEXT}; }}
    QHeaderView::section {{
        background: {_ACCENT}; color: white; border: none;
        padding: 8px; font-size: 9pt; font-weight: bold;
    }}
"""
_CARD = f"""
    QGroupBox {{ background: white; color: {_ACCENT}; border: 1px solid {_BORDER};
        border-radius: 16px; margin-top: 18px; padding-top: 12px;
        font-size: 10pt; font-weight: bold; }}
    QGroupBox::title {{ subcontrol-origin: margin; left: 16px; top: 0;
        background: {SECONDARY_BG}; padding: 8px 12px; }}
"""


class ToolSettingsView(IApplicationView):

    SHOW_JOG_WIDGET = True



    add_tool_requested    = pyqtSignal()
    edit_tool_requested   = pyqtSignal(int, str)   # tool_id, name
    remove_tool_requested = pyqtSignal(int)         # tool_id
    update_slot_requested = pyqtSignal(int, int)    # slot_id, tool_id
    add_slot_requested    = pyqtSignal()
    edit_slot_requested   = pyqtSignal(int, object)  # slot_id, current_tool_id (int or None)
    remove_slot_requested = pyqtSignal(int)         # slot_id
    save_slots_requested  = pyqtSignal(list)        # list of (slot_id, tool_id) tuples
    edit_geometry_requested = pyqtSignal(int)
    activate_tool_requested = pyqtSignal(int)
    capture_reference_requested = pyqtSignal()
    capture_candidate_requested = pyqtSignal()
    reset_calibration_requested = pyqtSignal()
    solve_calibration_requested = pyqtSignal(int)
    edit_sequences_requested = pyqtSignal(int)


    def __init__(self, parent=None):
        super().__init__("ToolSettings", parent)

    def setup_ui(self) -> None:
        self.setStyleSheet(f"background: {_BG};")
        root = QVBoxLayout(self)
        root.setContentsMargins(30, 16, 30, 16)
        root.setSpacing(14)

        self._title = QLabel()
        self._title.setObjectName("toolsTitle")
        self._title.setStyleSheet(
            f"background: {PRIMARY}; color: white; border-radius: 14px;"
            " padding: 14px 16px; font-size: 11pt; font-weight: bold;"
        )
        root.addWidget(self._title)

        self._tabs = QTabWidget()
        self._tabs.setStyleSheet(
            APP_PHASE_TAB_STYLE + "QTabWidget::pane { border: none; background: transparent; }"
        )
        self._tabs.addTab(self._build_tools_panel(), "")
        self._tabs.addTab(self._build_slots_panel(), "")
        self._tabs.addTab(self._build_calibration_panel(), "")
        root.addWidget(self._tabs, 1)

        footer = QFrame()
        footer.setObjectName("toolFooter")
        footer.setStyleSheet(
            f"QFrame#toolFooter {{ background: white; border: 1px solid {_BORDER};"
            " border-radius: 16px; }"
        )
        footer_row = QHBoxLayout(footer)
        footer_row.setContentsMargins(14, 10, 14, 10)
        footer_row.setSpacing(10)
        self._save_state = QLabel()
        self._save_state.setStyleSheet(f"color: {STATUS_OK}; font-weight: bold;")
        footer_row.addWidget(self._save_state)
        footer_row.addStretch(1)
        self._status = QLabel("")
        self._status.setStyleSheet(f"color: {_MUTED};")
        footer_row.addWidget(self._status)
        self._btn_discard_slots = QPushButton()
        self._btn_discard_slots.setStyleSheet(GHOST_BTN_STYLE)
        self._btn_discard_slots.setCursor(Qt.CursorShape.PointingHandCursor)
        self._btn_discard_slots.clicked.connect(self._on_discard_slots)
        footer_row.addWidget(self._btn_discard_slots)
        self._btn_save_slots = QPushButton()
        self._btn_save_slots.setStyleSheet(ACTION_BTN_STYLE)
        self._btn_save_slots.setCursor(Qt.CursorShape.PointingHandCursor)
        self._btn_save_slots.clicked.connect(self._on_save_slots)
        footer_row.addWidget(self._btn_save_slots)
        root.addWidget(footer)
        self._loaded_slot_assignments: dict[int, int | None] = {}
        self._reference_captured = False
        self._candidate_samples = 0
        self.retranslateUi()
        self.set_calibration_progress(reference_captured=False, candidate_samples=0)

    @staticmethod
    def _page() -> tuple[QWidget, QVBoxLayout]:
        page = QWidget()
        layout = QVBoxLayout(page)
        layout.setContentsMargins(0, 8, 0, 0)
        layout.setSpacing(12)
        return page, layout

    @staticmethod
    def _button(text: str, *, primary: bool = False) -> QPushButton:
        button = QPushButton(text)
        button.setStyleSheet(ACTION_BTN_STYLE if primary else GHOST_BTN_STYLE)
        button.setCursor(Qt.CursorShape.PointingHandCursor)
        return button

    def _build_tools_panel(self) -> QWidget:
        page, page_layout = self._page()
        self._tools_box = QGroupBox()
        self._tools_box.setStyleSheet(_CARD)
        layout = QVBoxLayout(self._tools_box)
        layout.setContentsMargins(16, 18, 16, 16)
        layout.setSpacing(12)
        self._tools_table = make_table(["ID", "Name", "X (mm)", "Y (mm)", "Z (mm)", "Collision"])
        self._tools_table.setStyleSheet(_TABLE)
        self._tools_table.verticalHeader().setDefaultSectionSize(50)
        self._tools_table.setMinimumHeight(140)
        self._tools_table.setMaximumHeight(370)
        self._tools_table.horizontalHeader().setSectionResizeMode(1, QHeaderView.ResizeMode.Stretch)
        layout.addWidget(self._tools_table)
        row = QHBoxLayout()
        row.setSpacing(10)
        self._btn_add_tool = self._button("", primary=True)
        self._btn_edit_tool = self._button("")
        self._btn_geometry = self._button("")
        self._btn_remove_tool = self._button("")
        for button in (self._btn_add_tool, self._btn_edit_tool, self._btn_geometry, self._btn_remove_tool):
            row.addWidget(button)
        row.addStretch(1)
        layout.addLayout(row)
        page_layout.addWidget(self._tools_box)
        page_layout.addStretch(1)
        self._btn_add_tool.clicked.connect(self.add_tool_requested.emit)
        self._btn_edit_tool.clicked.connect(self._on_edit_tool)
        self._btn_remove_tool.clicked.connect(self._on_remove_tool)
        self._btn_geometry.clicked.connect(self._on_edit_geometry)
        self._tools_table.itemSelectionChanged.connect(self._on_tool_selection)
        for button in (self._btn_edit_tool, self._btn_remove_tool, self._btn_geometry):
            button.setEnabled(False)
        return page

    def _build_slots_panel(self) -> QWidget:
        page, page_layout = self._page()
        self._slots_box = QGroupBox()
        self._slots_box.setStyleSheet(_CARD)
        layout = QVBoxLayout(self._slots_box)
        layout.setContentsMargins(16, 18, 16, 16)
        layout.setSpacing(12)
        self._slots_table = make_table(["Slot ID", "Assigned Tool"])
        self._slots_table.setStyleSheet(_TABLE)
        self._slots_table.verticalHeader().setDefaultSectionSize(50)
        self._slots_table.setMinimumHeight(140)
        self._slots_table.setMaximumHeight(370)
        self._slots_table.horizontalHeader().setSectionResizeMode(QHeaderView.ResizeMode.Stretch)
        self._slots_table.itemSelectionChanged.connect(self._on_slot_selection)
        layout.addWidget(self._slots_table)
        self._slots_empty = QLabel()
        self._slots_empty.setAlignment(Qt.AlignmentFlag.AlignCenter)
        self._slots_empty.setMinimumHeight(94)
        self._slots_empty.setStyleSheet(
            f"color: {_MUTED}; background: white; border: 1px solid {_BORDER};"
            " border-radius: 12px;"
        )
        layout.addWidget(self._slots_empty)
        row = QHBoxLayout()
        row.setSpacing(10)
        self._btn_add_slot = self._button("", primary=True)
        self._btn_edit_slot = self._button("")
        self._btn_sequences = self._button("")
        self._btn_remove_slot = self._button("")
        for button in (self._btn_add_slot, self._btn_edit_slot, self._btn_sequences, self._btn_remove_slot):
            row.addWidget(button)
        row.addStretch(1)
        layout.addLayout(row)
        page_layout.addWidget(self._slots_box)
        page_layout.addStretch(1)
        self._btn_add_slot.clicked.connect(self.add_slot_requested.emit)
        self._btn_edit_slot.clicked.connect(self._on_edit_slot)
        self._btn_remove_slot.clicked.connect(self._on_remove_slot)
        self._btn_sequences.clicked.connect(self._on_edit_sequences)
        for button in (self._btn_edit_slot, self._btn_remove_slot, self._btn_sequences):
            button.setEnabled(False)
        return page

    def _build_calibration_panel(self) -> QWidget:
        page, page_layout = self._page()
        self._calibration_box = QGroupBox()
        self._calibration_box.setStyleSheet(_CARD)
        layout = QVBoxLayout(self._calibration_box)
        layout.setContentsMargins(16, 18, 16, 16)
        layout.setSpacing(10)
        self._tool_to_calibrate_label = QLabel()
        self._tool_to_calibrate_label.setStyleSheet(f"color: {_MUTED};")
        layout.addWidget(self._tool_to_calibrate_label)
        selector_row = QHBoxLayout()
        self._calibration_tool_combo = QComboBox()
        self._calibration_tool_combo.setMinimumHeight(48)
        self._calibration_tool_combo.setStyleSheet(
            f"QComboBox {{ background: white; color: {_TEXT}; border: 1px solid {_BORDER};"
            " border-radius: 10px; padding: 8px 12px; font-size: 11pt; }"
        )
        self._calibration_tool_combo.currentIndexChanged.connect(self._on_calibration_tool_changed)
        selector_row.addWidget(self._calibration_tool_combo, 1)
        self._btn_reset_calibration = self._button("")
        self._btn_reset_calibration.clicked.connect(self.reset_calibration_requested.emit)
        selector_row.addWidget(self._btn_reset_calibration)
        layout.addLayout(selector_row)
        self._calibration_guide = QLabel()
        self._calibration_guide.setWordWrap(True)
        self._calibration_guide.setStyleSheet(
            f"color: {_ACCENT}; background: {SECONDARY_BG};"
            " border-radius: 10px; padding: 12px;"
        )
        layout.addWidget(self._calibration_guide)
        self._reference_state = QLabel()
        self._candidate_state = QLabel()
        self._solve_state = QLabel()
        self._activate_state = QLabel()
        self._btn_capture_reference = self._button("")
        self._btn_capture_candidate = self._button("")
        self._btn_solve = self._button("")
        self._btn_activate = self._button("")
        self._step_titles: list[QLabel] = []
        for number, detail, button in (
            (1, self._reference_state, self._btn_capture_reference),
            (2, self._candidate_state, self._btn_capture_candidate),
            (3, self._solve_state, self._btn_solve),
            (4, self._activate_state, self._btn_activate),
        ):
            self._add_calibration_step(layout, number, detail, button)
        self._btn_capture_reference.clicked.connect(self.capture_reference_requested.emit)
        self._btn_capture_candidate.clicked.connect(self.capture_candidate_requested.emit)
        self._btn_solve.clicked.connect(self._on_solve)
        self._btn_activate.clicked.connect(self._on_activate)
        page_layout.addWidget(self._calibration_box)
        page_layout.addStretch(1)
        return page

    def _add_calibration_step(
        self, layout: QVBoxLayout, number: int, detail: QLabel, button: QPushButton
    ) -> None:
        row = QHBoxLayout()
        row.setSpacing(12)
        badge = QLabel(str(number))
        badge.setAlignment(Qt.AlignmentFlag.AlignCenter)
        badge.setFixedSize(32, 32)
        badge.setStyleSheet(
            f"color: {_ACCENT}; background: {SECONDARY_BG};"
            " border-radius: 16px; font-weight: bold;"
        )
        row.addWidget(badge)
        text = QVBoxLayout()
        title = QLabel()
        title.setStyleSheet(f"color: {_TEXT}; font-weight: bold;")
        detail.setStyleSheet(f"color: {_MUTED};")
        text.addWidget(title)
        text.addWidget(detail)
        row.addLayout(text, 1)
        button.setMinimumWidth(230)
        row.addWidget(button)
        layout.addLayout(row)
        self._step_titles.append(title)
        if number < 4:
            divider = QFrame()
            divider.setFrameShape(QFrame.Shape.HLine)
            divider.setStyleSheet(f"color: {_BORDER};")
            layout.addWidget(divider)

    # ── Setters ──────────────────────────────────────────────────────

    def set_tools(self, tools) -> None:
        previous_id = self._calibration_tool_combo.currentData()
        self._tools_table.setRowCount(0)
        self._calibration_tool_combo.blockSignals(True)
        self._calibration_tool_combo.clear()
        for t in tools:
            row = self._tools_table.rowCount()
            self._tools_table.insertRow(row)
            self._tools_table.setItem(row, 0, QTableWidgetItem(str(t.id)))
            self._tools_table.setItem(row, 1, QTableWidgetItem(t.name))
            transform = list(getattr(t, "relative_transform", [0, 0, 0, 0, 0, 0]))
            for column, value in enumerate(transform[:3], start=2):
                self._tools_table.setItem(row, column, QTableWidgetItem(f"{float(value):.3f}"))
            self._tools_table.setItem(row, 5, QTableWidgetItem(str(getattr(t, "collision_profile", ""))))
            self._calibration_tool_combo.addItem(f"{t.name} (ID {t.id})", t.id)
        index = self._calibration_tool_combo.findData(previous_id)
        if index >= 0:
            self._calibration_tool_combo.setCurrentIndex(index)
        self._calibration_tool_combo.blockSignals(False)
        self._tools_table.setFixedHeight(min(370, max(140, 40 + 50 * len(tools))))
        self.set_calibration_progress(
            reference_captured=self._reference_captured,
            candidate_samples=self._candidate_samples,
        )

    def set_slots(self, slots, tools) -> None:
        self._slots_table.setRowCount(0)
        self._loaded_slot_assignments = {s.id: s.tool_id for s in slots}
        for s in slots:
            row = self._slots_table.rowCount()
            self._slots_table.insertRow(row)
            self._slots_table.setItem(row, 0, QTableWidgetItem(str(s.id)))
            combo = QComboBox()
            combo.setMinimumHeight(44)
            combo.setStyleSheet(
                f"background: white; border: 1px solid {_BORDER};"
                " border-radius: 8px; padding: 6px 10px;"
            )
            combo.addItem(self.tr("— Unassigned —"), None)
            for t in tools:
                combo.addItem(f"{t.name} ({t.id})", t.id)
            idx = combo.findData(s.tool_id)
            combo.setCurrentIndex(idx if idx >= 0 else 0)
            combo.currentIndexChanged.connect(self._on_slot_assignment_changed)
            self._slots_table.setCellWidget(row, 1, combo)
        self._slots_table.setFixedHeight(min(370, max(140, 40 + 50 * len(slots))))
        self._slots_table.setVisible(bool(slots))
        self._slots_empty.setVisible(not slots)
        self._btn_save_slots.setEnabled(bool(slots))
        self._update_save_state()

    def set_status(self, msg: str) -> None:
        self._status.setText(msg)

    def set_calibration_progress(
        self, *, reference_captured: bool, candidate_samples: int
    ) -> None:
        """Show calibration progress and make the next valid action obvious."""
        self._reference_captured = bool(reference_captured)
        self._candidate_samples = max(0, int(candidate_samples))
        selected_tool_id, selected_tool_name = self._calibration_selection()

        if not self._reference_captured:
            guide = self.tr(
                "Jog the reference tool to the calibration point, then capture the reference contact."
            )
        elif self._candidate_samples < 3:
            guide = self.tr(
                "Reference captured. Fit the tool being calibrated to the same point from different wrist orientations, capturing at least 3 contacts."
            )
        elif selected_tool_id is None:
            guide = self.tr(
                "Contact samples are ready. Select the tool to update, then solve the calibration."
            )
        else:
            guide = self.tr(
                "Ready to solve calibration for {tool_name} (ID {tool_id})."
            ).format(tool_name=selected_tool_name, tool_id=selected_tool_id)

        self._calibration_guide.setText(guide)
        self._reference_state.setText(
            self.tr("Reference: captured ✓")
            if self._reference_captured
            else self.tr("Reference: not captured")
        )
        self._candidate_state.setText(
            self.tr("Tool contacts: {count} / 3 minimum").format(
                count=self._candidate_samples
            )
        )
        self._solve_state.setText(
            self.tr("Ready to solve") if self._candidate_samples >= 3
            else self.tr("Needs 3 tool contacts")
        )
        self._activate_state.setText(
            self.tr("Selected tool: {tool_name}").format(tool_name=selected_tool_name)
            if selected_tool_id is not None else self.tr("No tool selected")
        )
        self._btn_capture_candidate.setEnabled(self._reference_captured)
        self._btn_solve.setEnabled(
            self._candidate_samples >= 3 and selected_tool_id is not None
        )
        self._btn_activate.setEnabled(selected_tool_id is not None)
        self._btn_capture_reference.setStyleSheet(
            _STEP_DONE_STYLE if self._reference_captured else ACTION_BTN_STYLE
        )
        self._btn_capture_candidate.setStyleSheet(
            ACTION_BTN_STYLE
            if self._reference_captured and self._candidate_samples < 3
            else GHOST_BTN_STYLE
        )
        self._btn_solve.setStyleSheet(
            ACTION_BTN_STYLE
            if self._candidate_samples >= 3 and selected_tool_id is not None
            else GHOST_BTN_STYLE
        )

    def _calibration_selection(self):
        tool_id = self._calibration_tool_combo.currentData()
        if tool_id is None:
            return None, None
        return int(tool_id), self._calibration_tool_combo.currentText().rsplit(" (ID ", 1)[0]

    def selected_tool(self):
        rows = self._tools_table.selectedItems()
        if not rows:
            return None, None
        row = self._tools_table.currentRow()
        return (
            int(self._tools_table.item(row, 0).text()),
            self._tools_table.item(row, 1).text(),
        )

    # ── Slots ────────────────────────────────────────────────────────

    def _on_tool_selection(self) -> None:
        has = bool(self._tools_table.selectedItems())
        self._btn_edit_tool.setEnabled(has)
        self._btn_remove_tool.setEnabled(has)
        self._btn_geometry.setEnabled(has)
        if has:
            tool_id, _ = self.selected_tool()
            index = self._calibration_tool_combo.findData(tool_id)
            if index >= 0:
                self._calibration_tool_combo.setCurrentIndex(index)
        self.set_calibration_progress(
            reference_captured=self._reference_captured,
            candidate_samples=self._candidate_samples,
        )

    def _on_edit_tool(self) -> None:
        tid, name = self.selected_tool()
        if tid is not None:
            self.edit_tool_requested.emit(tid, name)

    def _on_remove_tool(self) -> None:
        tid, _ = self.selected_tool()
        if tid is not None:
            self.remove_tool_requested.emit(tid)

    def _on_edit_geometry(self) -> None:
        tool_id, _ = self.selected_tool()
        if tool_id is not None:
            self.edit_geometry_requested.emit(tool_id)

    def _on_activate(self) -> None:
        tool_id, _ = self._calibration_selection()
        if tool_id is not None:
            self.activate_tool_requested.emit(tool_id)

    def _on_solve(self) -> None:
        tool_id, _ = self._calibration_selection()
        if tool_id is not None:
            self.solve_calibration_requested.emit(tool_id)

    def _on_save_slot(self) -> None:
        from PyQt6.QtWidgets import QComboBox
        for row in range(self._slots_table.rowCount()):
            slot_id = int(self._slots_table.item(row, 0).text())
            combo   = self._slots_table.cellWidget(row, 1)
            if isinstance(combo, QComboBox):
                tool_id = combo.currentData()
                self.update_slot_requested.emit(slot_id, tool_id)

    def selected_slot_id(self):
        rows = self._slots_table.selectedItems()
        if not rows:
            return None
        row = self._slots_table.currentRow()
        return int(self._slots_table.item(row, 0).text())

    def selected_slot(self):
        if not self._slots_table.selectedItems():
            return None, None
        from PyQt6.QtWidgets import QComboBox
        row = self._slots_table.currentRow()
        sid = int(self._slots_table.item(row, 0).text())
        combo = self._slots_table.cellWidget(row, 1)
        tid = combo.currentData() if isinstance(combo, QComboBox) else None
        return sid, tid

    def selected_slot_id(self):
        sid, _ = self.selected_slot()
        return sid

    def _on_slot_selection(self) -> None:
        has = bool(self._slots_table.selectedItems())
        self._btn_edit_slot.setEnabled(has)
        self._btn_remove_slot.setEnabled(has)
        self._btn_sequences.setEnabled(has)

    def _on_edit_slot(self) -> None:
        sid, tid = self.selected_slot()
        if sid is not None:
            self.edit_slot_requested.emit(sid, tid)

    def _on_remove_slot(self) -> None:
        sid = self.selected_slot_id()
        if sid is not None:
            self.remove_slot_requested.emit(sid)

    def _on_edit_sequences(self) -> None:
        slot_id = self.selected_slot_id()
        if slot_id is not None:
            self.edit_sequences_requested.emit(slot_id)

    def _on_save_slots(self) -> None:
        from PyQt6.QtWidgets import QComboBox
        result = []
        for row in range(self._slots_table.rowCount()):
            slot_id = int(self._slots_table.item(row, 0).text())
            combo   = self._slots_table.cellWidget(row, 1)
            if isinstance(combo, QComboBox):
                tool_id = combo.currentData()   # None for Unassigned
                result.append((slot_id, tool_id))
        self.save_slots_requested.emit(result)

    def _on_calibration_tool_changed(self, _index: int) -> None:
        self.set_calibration_progress(
            reference_captured=self._reference_captured,
            candidate_samples=self._candidate_samples,
        )

    def _on_slot_assignment_changed(self, _index: int) -> None:
        self._update_save_state()

    def _update_save_state(self) -> None:
        pending = any(
            self._slots_table.cellWidget(row, 1).currentData()
            != self._loaded_slot_assignments.get(int(self._slots_table.item(row, 0).text()))
            for row in range(self._slots_table.rowCount())
        )
        self._save_state.setText(
            self.tr("●  Unsaved slot changes") if pending
            else self.tr("●  All changes saved")
        )
        self._btn_discard_slots.setEnabled(pending)

    def _on_discard_slots(self) -> None:
        for row in range(self._slots_table.rowCount()):
            slot_id = int(self._slots_table.item(row, 0).text())
            combo = self._slots_table.cellWidget(row, 1)
            index = combo.findData(self._loaded_slot_assignments.get(slot_id))
            combo.setCurrentIndex(max(0, index))
        self._update_save_state()

    def clean_up(self) -> None:
        pass

    def retranslateUi(self) -> None:
        self._title.setText(self.tr("Tools & Magazine").upper())
        for index, title in enumerate(("Tools", "Slots", "TCP calibration")):
            self._tabs.setTabText(index, self.tr(title))
        self._tools_box.setTitle(self.tr("Tools / Grippers").upper())
        self._slots_box.setTitle(self.tr("Slot ↔ Tool Assignments").upper())
        self._calibration_box.setTitle(self.tr("Guided TCP Calibration").upper())
        for table, headers in (
            (self._tools_table, ("ID", "Name", "X (mm)", "Y (mm)", "Z (mm)", "Collision")),
            (self._slots_table, ("Slot ID", "Assigned Tool")),
        ):
            for column, source in enumerate(headers):
                table.horizontalHeaderItem(column).setText(self.tr(source).upper())
        self._slots_empty.setText(self.tr("No slots yet. Add a slot to assign a tool to it."))
        for button, source in (
            (self._btn_add_tool, "Add tool"),
            (self._btn_edit_tool, "Edit"),
            (self._btn_geometry, "Offsets"),
            (self._btn_remove_tool, "Remove"),
            (self._btn_add_slot, "Add slot"),
            (self._btn_edit_slot, "Edit slot"),
            (self._btn_sequences, "Teach sequences"),
            (self._btn_remove_slot, "Remove slot"),
            (self._btn_capture_reference, "Capture reference contact"),
            (self._btn_capture_candidate, "Capture tool contact"),
            (self._btn_solve, "Solve selected tool"),
            (self._btn_activate, "Activate selected tool"),
            (self._btn_reset_calibration, "Start over"),
            (self._btn_discard_slots, "Discard"),
            (self._btn_save_slots, "Save all changes"),
        ):
            button.setText(self.tr(source))
        for label, source in zip(
            self._step_titles,
            ("Reference contact", "Tool contacts", "Solve", "Activate"),
        ):
            label.setText(self.tr(source))
        self._tool_to_calibrate_label.setText(self.tr("Tool to calibrate").upper())
        self._update_save_state()
        self.set_calibration_progress(
            reference_captured=self._reference_captured,
            candidate_samples=self._candidate_samples,
        )

    def changeEvent(self, event) -> None:
        if event.type() == QEvent.Type.LanguageChange:
            self.setWindowTitle(self.tr("Tools & Magazine"))
            self.retranslateUi()
        super().changeEvent(event)
