"""
Right panel — mirrors HTML .right structure:
  One QStackedWidget pane per tab (system / camera / robot / laser / height).
  Each pane is a QScrollArea containing a single card.
  Driven by CalibrationLeftPanel.tab_changed signal.
"""
from __future__ import annotations

from PyQt6.QtCore import Qt, pyqtSignal
from PyQt6.QtWidgets import (
    QComboBox,
    QHBoxLayout,
    QLabel,
    QScrollArea,
    QSpinBox,
    QStackedWidget,
    QVBoxLayout,
    QWidget,
)

from pl_gui.utils.utils_widgets.MaterialButton import MaterialButton
from src.applications.base.collapsible_settings_view import CollapsibleGroup
from src.applications.base.app_styles import (
    divider,
    section_hint,
    section_label,
)
from src.applications.calibration_settings.view.calibration_settings_schema import (
    CALIBRATION_ADAPTIVE_GROUP,
    CALIBRATION_AXIS_MAPPING_GROUP,
    CALIBRATION_CAMERA_TCP_GROUP,
    CALIBRATION_MARKER_GROUP,
    HEIGHT_MAPPING_GROUP,
    LASER_CALIBRATION_GROUP,
    LASER_DETECTION_GROUP,
    VISION_CALIBRATION_GROUP,
)
from src.shared_contracts.declarations import WorkAreaDefinition

# ── palette ───────────────────────────────────────────────────────────────────
_BG      = "#F0EFF5"
_PANEL   = "#FFFFFF"
_BD      = "#D0CCDE"
_PR      = "#905BA9"
_PRD     = "#7A4D90"
_PRL     = "#EDE7F6"
_PRL2    = "#D8CCF0"
_MU      = "#4A4868"
_NG      = "#B71C1C"
_SQ_BG   = "#DDD8F8"
_SQ_BD   = "#5B3ED6"
_SQ_FG   = "#2E1F8A"

_CARD_STYLE = f"""
QWidget#card {{
    background: {_PANEL};
    border: 1.5px solid {_BD};
    border-radius: 12px;
}}
"""

# Button styles matching HTML exactly
_BTN_PR = f"""
MaterialButton {{
    background: {_PR}; color: #fff; border: none; border-radius: 9px;
    font-size: 11pt; font-weight: 500; min-height: 54px;
}}
MaterialButton:hover:!disabled {{ background: {_PRD}; }}
MaterialButton:disabled {{ opacity: 0.32; }}
"""
_BTN_GH = f"""
MaterialButton {{
    background: {_PRL}; color: #5B2D80;
    border: 1.5px solid #B088CC; border-radius: 9px;
    font-size: 11pt; font-weight: 500; min-height: 54px;
}}
MaterialButton:hover:!disabled {{ background: {_PRL2}; }}
MaterialButton:disabled {{ opacity: 0.32; }}
"""
_BTN_SQ = f"""
MaterialButton {{
    background: {_SQ_BG}; color: {_SQ_FG};
    border: 1.5px solid {_SQ_BD}; border-radius: 9px;
    font-size: 11pt; font-weight: 500; min-height: 54px;
}}
MaterialButton:hover:!disabled {{ background: #CCC6F4; }}
MaterialButton:disabled {{ opacity: 0.32; }}
"""
_BTN_DG = f"""
MaterialButton {{
    background: {_NG}; color: #fff; border: none; border-radius: 9px;
    font-size: 11pt; font-weight: 500; min-height: 54px;
}}
MaterialButton:hover:!disabled {{ background: #8B0000; }}
MaterialButton:disabled {{ opacity: 0.32; }}
"""
_BTN_TON = f"""
MaterialButton {{
    background: {_PR}; color: #fff;
    border: 1.5px solid {_PRD}; border-radius: 9px;
    font-size: 11pt; font-weight: 500; min-height: 54px;
}}
MaterialButton:hover {{ background: {_PRD}; }}
"""
_BTN_TOF = f"""
MaterialButton {{
    background: #ECEAF4; color: #6A6590;
    border: 1.5px solid #B0AACB; border-radius: 9px;
    font-size: 11pt; font-weight: 500; min-height: 54px;
}}
MaterialButton:hover {{ background: #E2DFEF; }}
"""

_AREA_CARD_STYLE = f"""
QWidget#areaCard {{
    background: #F5F3FC;
    border: 1.5px solid {_BD};
    border-radius: 9px;
}}
"""

_COMBO_SPIN_STYLE = f"""
QComboBox, QSpinBox {{
    background: #fff; color: #1A1A2E;
    border: 1.5px solid #B0AACB; border-radius: 9px;
    padding: 0 14px; font-size: 11pt; min-height: 48px;
}}
QComboBox:focus, QSpinBox:focus {{ border-color: {_PR}; }}
"""

_PANE_IDS = ["system", "camera", "robot", "laser", "height"]


class _Card(QWidget):
    """White rounded card matching HTML .card"""
    def __init__(self, parent=None):
        super().__init__(parent)
        self.setObjectName("card")
        self.setStyleSheet(_CARD_STYLE)
        self._layout = QVBoxLayout(self)
        self._layout.setContentsMargins(18, 18, 18, 18)
        self._layout.setSpacing(12)

    def add(self, w: QWidget) -> QWidget:
        self._layout.addWidget(w)
        return w

    def add_layout(self, lo) -> None:
        self._layout.addLayout(lo)

    def add_divider(self) -> None:
        self._layout.addWidget(divider())

    def add_stretch(self) -> None:
        self._layout.addStretch()


def _pane(card: QWidget) -> QWidget:
    """Wrap a card in a QScrollArea that matches HTML .pane."""
    scroll = QScrollArea()
    scroll.setWidgetResizable(True)
    scroll.setFrameShape(QScrollArea.Shape.NoFrame)
    scroll.setHorizontalScrollBarPolicy(Qt.ScrollBarPolicy.ScrollBarAlwaysOff)
    scroll.setStyleSheet(f"background: {_BG};")
    scroll.setWidget(card)
    return scroll


def _btn(label: str, style: str, enabled: bool = True) -> MaterialButton:
    b = MaterialButton(label)
    b.setStyleSheet(style)
    b.setEnabled(enabled)
    b.setCursor(Qt.CursorShape.PointingHandCursor)
    return b


def _label(text: str) -> QLabel:
    lbl = QLabel(text)
    lbl.setStyleSheet(f"color: {_MU}; font-size: 10pt; font-weight: 500;")
    return lbl


# ─────────────────────────────────────────────────────────────────────────────
# Pane widgets
# ─────────────────────────────────────────────────────────────────────────────

class SystemPane(QWidget):
    calibrate_sequence_requested = pyqtSignal()
    stop_calibration_requested   = pyqtSignal()

    def __init__(self, parent=None):
        super().__init__(parent)
        card = _Card()
        card.add(section_label("System calibration"))
        card.add(section_hint("Use the guided sequence for a normal workflow, or stop the active task from here."))
        self.sequence_btn = _btn("Calibrate camera → robot", _BTN_SQ)
        card.add(self.sequence_btn)
        card.add_divider()
        self.stop_btn = _btn("⏹  Stop active task", _BTN_DG, enabled=False)
        card.add(self.stop_btn)
        card.add_stretch()

        outer = QVBoxLayout(self)
        outer.setContentsMargins(0, 0, 0, 0)
        outer.addWidget(_pane(card))

        self.sequence_btn.clicked.connect(self.calibrate_sequence_requested)
        self.stop_btn.clicked.connect(self.stop_calibration_requested)


class CameraPane(QWidget):
    capture_requested         = pyqtSignal()
    calibrate_camera_requested = pyqtSignal()
    crosshair_toggled         = pyqtSignal(bool)
    magnifier_toggled         = pyqtSignal(bool)
    save_requested            = pyqtSignal()

    def __init__(self, parent=None):
        super().__init__(parent)
        self._crosshair_on = False
        self._magnifier_on = False

        card = _Card()
        self._card = card
        card.add(section_label("Camera calibration"))
        card.add(section_hint("Capture a fresh image, use overlays while framing the board, then run camera calibration."))
        self.capture_btn = _btn("Capture calibration image", _BTN_GH)
        card.add(self.capture_btn)

        overlay_row = QHBoxLayout()
        overlay_row.setSpacing(10)
        self.crosshair_btn = _btn("＋  Crosshair", _BTN_TON)
        self.magnifier_btn = _btn("🔍  Magnifier", _BTN_TON)
        overlay_row.addWidget(self.crosshair_btn, stretch=1)
        overlay_row.addWidget(self.magnifier_btn, stretch=1)
        card.add_layout(overlay_row)
        card.add_divider()

        self.calibrate_camera_btn = _btn("Calibrate camera", _BTN_PR)
        card.add(self.calibrate_camera_btn)

        self._settings_groups: list[CollapsibleGroup] = []
        for schema in [VISION_CALIBRATION_GROUP]:
            g = CollapsibleGroup(schema)
            self._settings_groups.append(g)
            card.add(g)

        self.save_btn = _btn("Save phase settings", _BTN_GH)
        card.add(self.save_btn)
        card.add_stretch()

        outer = QVBoxLayout(self)
        outer.setContentsMargins(0, 0, 0, 0)
        outer.addWidget(_pane(card))

        self.capture_btn.clicked.connect(self.capture_requested)
        self.calibrate_camera_btn.clicked.connect(self.calibrate_camera_requested)
        self.crosshair_btn.clicked.connect(self._toggle_crosshair)
        self.magnifier_btn.clicked.connect(self._toggle_magnifier)

    def _toggle_crosshair(self) -> None:
        self._crosshair_on = not self._crosshair_on
        self.crosshair_btn.setStyleSheet(_BTN_TON if self._crosshair_on else _BTN_TOF)
        self.crosshair_toggled.emit(self._crosshair_on)

    def _toggle_magnifier(self) -> None:
        self._magnifier_on = not self._magnifier_on
        self.magnifier_btn.setStyleSheet(_BTN_TON if self._magnifier_on else _BTN_TOF)
        self.magnifier_toggled.emit(self._magnifier_on)

    def set_settings_values(self, flat: dict) -> None:
        for g in self._settings_groups:
            g.set_values(flat)

    def get_settings_values(self) -> dict:
        out = {}
        for g in self._settings_groups:
            out.update(g.get_values())
        return out


class RobotPane(QWidget):
    calibrate_robot_requested            = pyqtSignal()
    calibrate_camera_tcp_offset_requested = pyqtSignal()
    test_calibration_requested           = pyqtSignal()
    measure_marker_heights_requested     = pyqtSignal()

    def __init__(self, parent=None):
        super().__init__(parent)
        card = _Card()
        card.add(section_label("Robot calibration"))
        card.add(section_hint("Run robot calibration, then use TCP offset and test validation once calibration data exists."))
        self.calibrate_robot_btn = _btn("Calibrate robot", _BTN_PR)
        self.calibrate_tcp_btn   = _btn("Calibrate camera TCP offset", _BTN_PR, enabled=False)
        card.add(self.calibrate_robot_btn)
        card.add(self.calibrate_tcp_btn)
        card.add_divider()
        self.test_btn = _btn("▶  Test calibration", _BTN_PR, enabled=False)
        card.add(self.test_btn)

        self._settings_groups: list[CollapsibleGroup] = []
        for schema in [CALIBRATION_ADAPTIVE_GROUP, CALIBRATION_MARKER_GROUP,
                       CALIBRATION_AXIS_MAPPING_GROUP, CALIBRATION_CAMERA_TCP_GROUP]:
            g = CollapsibleGroup(schema)
            self._settings_groups.append(g)
            card.add(g)

        self.save_btn = _btn("Save phase settings", _BTN_GH)
        card.add(self.save_btn)
        card.add_stretch()

        outer = QVBoxLayout(self)
        outer.setContentsMargins(0, 0, 0, 0)
        outer.addWidget(_pane(card))

        self.calibrate_robot_btn.clicked.connect(self.calibrate_robot_requested)
        self.calibrate_tcp_btn.clicked.connect(self.calibrate_camera_tcp_offset_requested)
        self.test_btn.clicked.connect(self.test_calibration_requested)

    def set_settings_values(self, flat: dict) -> None:
        for g in self._settings_groups:
            g.set_values(flat)

    def get_settings_values(self) -> dict:
        out = {}
        for g in self._settings_groups:
            out.update(g.get_values())
        return out


class LaserPane(QWidget):
    calibrate_laser_requested = pyqtSignal()
    detect_laser_requested    = pyqtSignal()

    def __init__(self, parent=None):
        super().__init__(parent)
        card = _Card()
        card.add(section_label("Laser calibration"))
        card.add(section_hint("Calibrate the laser model or run a single detection pass for validation and debugging."))
        self.calibrate_laser_btn = _btn("📡  Calibrate laser", _BTN_PR)
        self.detect_laser_btn    = _btn("🔎  Detect laser once", _BTN_PR)
        card.add(self.calibrate_laser_btn)
        card.add(self.detect_laser_btn)

        self._settings_groups: list[CollapsibleGroup] = []
        for schema in [LASER_DETECTION_GROUP, LASER_CALIBRATION_GROUP]:
            g = CollapsibleGroup(schema)
            self._settings_groups.append(g)
            card.add(g)

        self.save_btn = _btn("Save phase settings", _BTN_GH)
        card.add(self.save_btn)
        card.add_stretch()

        outer = QVBoxLayout(self)
        outer.setContentsMargins(0, 0, 0, 0)
        outer.addWidget(_pane(card))

        self.calibrate_laser_btn.clicked.connect(self.calibrate_laser_requested)
        self.detect_laser_btn.clicked.connect(self.detect_laser_requested)

    def set_settings_values(self, flat: dict) -> None:
        for g in self._settings_groups:
            g.set_values(flat)

    def get_settings_values(self) -> dict:
        out = {}
        for g in self._settings_groups:
            out.update(g.get_values())
        return out


class _AreaGridPanel(QWidget):
    """Matches HTML .area-card inside the height pane."""
    work_area_changed          = pyqtSignal(str)
    measurement_area_changed   = pyqtSignal()
    generate_area_grid_requested = pyqtSignal()
    verify_area_grid_requested   = pyqtSignal()
    measure_area_grid_requested  = pyqtSignal()
    view_depth_map_requested     = pyqtSignal()

    def __init__(self, preview_label, work_area_definitions, parent=None):
        super().__init__(parent)
        self.preview_label = preview_label
        self._work_area_defs = [d for d in (work_area_definitions or []) if d.supports_height_mapping]
        self._build_ui()

    def _build_ui(self) -> None:
        area_card = QWidget()
        area_card.setObjectName("areaCard")
        area_card.setStyleSheet(_AREA_CARD_STYLE)
        ac = QVBoxLayout(area_card)
        ac.setContentsMargins(14, 14, 14, 14)
        ac.setSpacing(10)

        ac.addWidget(section_label("Step 3: Define area and grid"))
        ac.addWidget(section_hint(
            "Choose a work area, mark its four corners on the preview, then generate and verify the grid."
        ))

        # Work area selector
        ac.addWidget(_label("Work area"))
        self.work_area_combo = QComboBox()
        self.work_area_combo.setStyleSheet(_COMBO_SPIN_STYLE)
        for d in self._work_area_defs:
            self.work_area_combo.addItem(d.label, d.id)
        ac.addWidget(self.work_area_combo)

        # Rows / Cols
        spin_row = QHBoxLayout()
        spin_row.setSpacing(10)
        for label_text, attr_name, default in [("Rows", "grid_rows_spin", 5), ("Cols", "grid_cols_spin", 4)]:
            col = QVBoxLayout()
            col.setSpacing(4)
            col.addWidget(_label(label_text))
            spin = QSpinBox()
            spin.setRange(2, 50)
            spin.setValue(default)
            spin.setStyleSheet(_COMBO_SPIN_STYLE)
            setattr(self, attr_name, spin)
            col.addWidget(spin)
            spin_row.addLayout(col, stretch=1)
        ac.addLayout(spin_row)
        ac.addWidget(divider())

        # Action buttons — full width stacked
        self.generate_area_grid_btn = _btn("▦  Generate grid", _get_btn_pr())
        self.measure_area_grid_btn  = _btn("📐  Measure area grid", _get_btn_pr(), enabled=False)
        self.verify_area_grid_btn   = _btn("🧭  Verify grid", _get_btn_pr(), enabled=False)
        for b in [self.generate_area_grid_btn, self.measure_area_grid_btn, self.verify_area_grid_btn]:
            ac.addWidget(b)

        # Secondary row
        sec_row = QHBoxLayout()
        sec_row.setSpacing(10)
        self.clear_area_grid_btn = _btn("✎  Clear area", _get_btn_gh())
        self.view_depth_map_btn  = _btn("📈  Depth map", _get_btn_pr(), enabled=False)
        sec_row.addWidget(self.clear_area_grid_btn, stretch=1)
        sec_row.addWidget(self.view_depth_map_btn, stretch=1)
        ac.addLayout(sec_row)

        outer = QVBoxLayout(self)
        outer.setContentsMargins(0, 0, 0, 0)
        outer.addWidget(area_card)

        # signals
        self.work_area_combo.currentIndexChanged.connect(self._on_work_area_changed)
        self.generate_area_grid_btn.clicked.connect(self.generate_area_grid_requested)
        self.measure_area_grid_btn.clicked.connect(self.measure_area_grid_requested)
        self.verify_area_grid_btn.clicked.connect(self.verify_area_grid_requested)
        self.clear_area_grid_btn.clicked.connect(self.clear_measurement_area)
        self.view_depth_map_btn.clicked.connect(self.view_depth_map_requested)

    # ── public API (identical to original CalibrationAreaGridPanel) ───────────

    def _on_work_area_changed(self) -> None:
        key = self.current_height_mapping_area_key()
        self.preview_label.set_active_area(key)
        self.preview_label.set_grid_points([])
        self.work_area_changed.emit(self.current_work_area_id())

    def _on_measurement_area_changed(self, _area, _idx, _xn, _yn) -> None:
        self.preview_label.set_grid_points([])
        self.measurement_area_changed.emit()

    def _on_measurement_area_empty_clicked(self, _area, _xn, _yn) -> None:
        self.preview_label.set_grid_points([])
        self.measurement_area_changed.emit()

    def current_work_area_id(self) -> str:
        return str(self.work_area_combo.currentData() or "")

    def set_current_work_area_id(self, area_id: str) -> None:
        idx = self.work_area_combo.findData(str(area_id or ""))
        if idx >= 0:
            self.work_area_combo.setCurrentIndex(idx)

    def current_height_mapping_area_key(self) -> str | None:
        area_id = self.current_work_area_id()
        for d in self._work_area_defs:
            if d.id == area_id:
                return d.id
        return None

    def set_work_area_options(self, definitions: list[WorkAreaDefinition]) -> None:
        self._work_area_defs = [d for d in definitions if d.supports_height_mapping]
        self.work_area_combo.blockSignals(True)
        self.work_area_combo.clear()
        for d in self._work_area_defs:
            self.work_area_combo.addItem(d.label, d.id)
            self.preview_label.add_area(d.id, d.color)
        self.work_area_combo.blockSignals(False)
        self._on_work_area_changed()

    def get_measurement_area_corners(self) -> list[tuple[float, float]]:
        key = self.current_height_mapping_area_key()
        return self.preview_label.get_area_corners(key) if key else []

    def clear_measurement_area(self) -> None:
        key = self.current_height_mapping_area_key()
        if key:
            self.preview_label.clear_area(key)
        self.preview_label.set_grid_points([])

    def set_measurement_area_corners(self, area_id: str, corners) -> None:
        for d in self._work_area_defs:
            if d.id == area_id:
                self.preview_label.set_area_corners(d.id, corners)
                return

    def set_generated_grid_points(self, points, *, point_labels=None, point_statuses=None) -> None:
        self.preview_label.set_grid_points(points, point_labels=point_labels, point_statuses=point_statuses)

    def set_substitute_regions(self, polygons) -> None:
        self.preview_label.set_substitute_regions(polygons)

    def get_area_grid_shape(self) -> tuple[int, int]:
        return int(self.grid_rows_spin.value()), int(self.grid_cols_spin.value())

    def set_measure_area_grid_enabled(self, enabled: bool) -> None:
        self.measure_area_grid_btn.setEnabled(enabled)
        self.verify_area_grid_btn.setEnabled(enabled)

    def set_verify_area_grid_busy(self, busy: bool, current: int = 0, total: int = 0) -> None:
        if busy:
            txt = f"⏳  Verifying… {current}/{total}" if total else "⏳  Verifying…"
            self.verify_area_grid_btn.setText(txt)
        else:
            self.verify_area_grid_btn.setText("🧭  Verify grid")

    def set_depth_map_enabled(self, enabled: bool) -> None:
        self.view_depth_map_btn.setEnabled(enabled)

    def set_enabled(self, enabled: bool) -> None:
        self.generate_area_grid_btn.setEnabled(enabled)
        self.clear_area_grid_btn.setEnabled(enabled)
        self.grid_rows_spin.setEnabled(enabled)
        self.grid_cols_spin.setEnabled(enabled)
        self.work_area_combo.setEnabled(enabled)


def _get_btn_pr() -> str:
    return _BTN_PR


def _get_btn_gh() -> str:
    return _BTN_GH


class HeightPane(QWidget):
    verify_saved_model_requested = pyqtSignal()
    generate_area_grid_requested = pyqtSignal()
    verify_area_grid_requested   = pyqtSignal()
    measure_area_grid_requested  = pyqtSignal()
    view_depth_map_requested     = pyqtSignal()
    work_area_changed            = pyqtSignal(str)
    measurement_area_changed     = pyqtSignal()

    def __init__(self, preview_label, work_area_definitions, parent=None):
        super().__init__(parent)
        card = _Card()
        card.add(section_label("Height mapping"))
        card.add(section_hint(
            "Define the mapping area on the preview, generate the area grid, and verify the saved model here."
        ))

        self.area_grid_panel = _AreaGridPanel(preview_label, work_area_definitions)
        card.add(self.area_grid_panel)
        card.add_divider()

        self.verify_saved_model_btn = _btn("🧪  Verify saved model", _BTN_PR, enabled=False)
        card.add(self.verify_saved_model_btn)

        self._settings_groups: list[CollapsibleGroup] = []
        for schema in [HEIGHT_MAPPING_GROUP]:
            g = CollapsibleGroup(schema)
            self._settings_groups.append(g)
            card.add(g)

        self.save_btn = _btn("Save phase settings", _BTN_GH)
        card.add(self.save_btn)
        card.add_stretch()

        outer = QVBoxLayout(self)
        outer.setContentsMargins(0, 0, 0, 0)
        outer.addWidget(_pane(card))

        # forward signals from area_grid_panel
        self.area_grid_panel.generate_area_grid_requested.connect(self.generate_area_grid_requested)
        self.area_grid_panel.verify_area_grid_requested.connect(self.verify_area_grid_requested)
        self.area_grid_panel.measure_area_grid_requested.connect(self.measure_area_grid_requested)
        self.area_grid_panel.view_depth_map_requested.connect(self.view_depth_map_requested)
        self.area_grid_panel.work_area_changed.connect(self.work_area_changed)
        self.area_grid_panel.measurement_area_changed.connect(self.measurement_area_changed)
        self.verify_saved_model_btn.clicked.connect(self.verify_saved_model_requested)

    def set_settings_values(self, flat: dict) -> None:
        for g in self._settings_groups:
            g.set_values(flat)

    def get_settings_values(self) -> dict:
        out = {}
        for g in self._settings_groups:
            out.update(g.get_values())
        return out


# ─────────────────────────────────────────────────────────────────────────────
# CalibrationRightPanel
# ─────────────────────────────────────────────────────────────────────────────

class CalibrationRightPanel(QWidget):
    """Aggregates all pane signals and exposes a flat API to CalibrationView."""

    capture_requested                     = pyqtSignal()
    calibrate_camera_requested            = pyqtSignal()
    calibrate_robot_requested             = pyqtSignal()
    calibrate_sequence_requested          = pyqtSignal()
    calibrate_camera_tcp_offset_requested = pyqtSignal()
    calibrate_laser_requested             = pyqtSignal()
    detect_laser_requested                = pyqtSignal()
    stop_calibration_requested            = pyqtSignal()
    test_calibration_requested            = pyqtSignal()
    measure_marker_heights_requested      = pyqtSignal()
    generate_area_grid_requested          = pyqtSignal()
    verify_area_grid_requested            = pyqtSignal()
    measure_area_grid_requested           = pyqtSignal()
    view_depth_map_requested              = pyqtSignal()
    verify_saved_model_requested          = pyqtSignal()
    save_calibration_settings_requested   = pyqtSignal(dict)
    work_area_changed                     = pyqtSignal(str)
    measurement_area_changed              = pyqtSignal()

    def __init__(self, work_area_definitions: list[WorkAreaDefinition] | None = None, parent=None):
        super().__init__(parent)
        self.setStyleSheet(f"background: {_BG}; border-left: 1.5px solid {_BD};")

        # Will be set after left panel preview_label is created
        self._work_area_definitions = work_area_definitions or []
        self._stack = QStackedWidget()
        self._pane_map: dict[str, int] = {}

        outer = QVBoxLayout(self)
        outer.setContentsMargins(0, 0, 0, 0)
        outer.setSpacing(0)
        outer.addWidget(self._stack)

        # Placeholder panes — will be replaced when set_preview_label() called
        self._system_pane  = SystemPane()
        self._camera_pane  = CameraPane()
        self._robot_pane   = RobotPane()
        self._laser_pane   = LaserPane()
        self.height_pane   = HeightPane(None, self._work_area_definitions)

        for tab_id, pane in zip(_PANE_IDS, [
            self._system_pane, self._camera_pane, self._robot_pane,
            self._laser_pane, self.height_pane,
        ]):
            idx = self._stack.addWidget(pane)
            self._pane_map[tab_id] = idx

        self._stack.setCurrentIndex(self._pane_map["camera"])   # default = camera tab
        self._wire_signals()

    def set_preview_label(self, preview_label) -> None:
        """Called after left panel is built so height pane gets the real preview label."""
        self.height_pane.area_grid_panel.preview_label = preview_label

    def _wire_signals(self) -> None:
        sp = self._system_pane
        cp = self._camera_pane
        rp = self._robot_pane
        lp = self._laser_pane
        hp = self.height_pane

        sp.calibrate_sequence_requested.connect(self.calibrate_sequence_requested)
        sp.stop_calibration_requested.connect(self.stop_calibration_requested)

        cp.capture_requested.connect(self.capture_requested)
        cp.calibrate_camera_requested.connect(self.calibrate_camera_requested)
        cp.crosshair_toggled.connect(lambda on: None)   # consumed by view directly
        cp.magnifier_toggled.connect(lambda on: None)

        rp.calibrate_robot_requested.connect(self.calibrate_robot_requested)
        rp.calibrate_camera_tcp_offset_requested.connect(self.calibrate_camera_tcp_offset_requested)
        rp.test_calibration_requested.connect(self.test_calibration_requested)

        lp.calibrate_laser_requested.connect(self.calibrate_laser_requested)
        lp.detect_laser_requested.connect(self.detect_laser_requested)

        hp.verify_saved_model_requested.connect(self.verify_saved_model_requested)
        hp.generate_area_grid_requested.connect(self.generate_area_grid_requested)
        hp.verify_area_grid_requested.connect(self.verify_area_grid_requested)
        hp.measure_area_grid_requested.connect(self.measure_area_grid_requested)
        hp.view_depth_map_requested.connect(self.view_depth_map_requested)
        hp.work_area_changed.connect(self.work_area_changed)
        hp.measurement_area_changed.connect(self.measurement_area_changed)

        # Save buttons emit save_calibration_settings_requested with merged dict
        for pane in [cp, rp, lp, hp]:
            if hasattr(pane, "save_btn"):
                pane.save_btn.clicked.connect(lambda _, p=pane: self._emit_save(p))

    def _emit_save(self, pane) -> None:
        values: dict = {}
        for p in [self._camera_pane, self._robot_pane, self._laser_pane, self.height_pane]:
            if hasattr(p, "get_settings_values"):
                values.update(p.get_settings_values())
        self.save_calibration_settings_requested.emit(values)

    # ------------------------------------------------------------------
    # Tab switching
    # ------------------------------------------------------------------

    def show_pane(self, tab_id: str) -> None:
        idx = self._pane_map.get(tab_id)
        if idx is not None:
            self._stack.setCurrentIndex(idx)

    # ------------------------------------------------------------------
    # Setter passthrough
    # ------------------------------------------------------------------

    def set_stop_calibration_enabled(self, enabled: bool) -> None:
        self._system_pane.stop_btn.setEnabled(enabled)

    def set_test_calibration_enabled(self, enabled: bool) -> None:
        self._robot_pane.test_btn.setEnabled(enabled)

    def set_camera_tcp_offset_enabled(self, enabled: bool) -> None:
        self._robot_pane.calibrate_tcp_btn.setEnabled(enabled)

    def set_measure_marker_heights_enabled(self, enabled: bool) -> None:
        pass   # hidden feature — no button in this design

    def set_depth_map_enabled(self, enabled: bool) -> None:
        self.height_pane.verify_saved_model_btn.setEnabled(enabled)

    def set_laser_actions_enabled(self, enabled: bool) -> None:
        self._laser_pane.calibrate_laser_btn.setEnabled(enabled)
        self._laser_pane.detect_laser_btn.setEnabled(enabled)

    def set_buttons_enabled(self, enabled: bool) -> None:
        for b in [
            self._camera_pane.capture_btn,
            self._camera_pane.calibrate_camera_btn,
            self._robot_pane.calibrate_robot_btn,
            self._system_pane.sequence_btn,
        ]:
            b.setEnabled(enabled)

    def set_settings_values(self, flat: dict) -> None:
        for pane in [self._camera_pane, self._robot_pane, self._laser_pane, self.height_pane]:
            if hasattr(pane, "set_settings_values"):
                pane.set_settings_values(flat)

    def iter_save_settings_buttons(self):
        return [
            p.save_btn
            for p in [self._camera_pane, self._robot_pane, self._laser_pane, self.height_pane]
            if hasattr(p, "save_btn")
        ]

