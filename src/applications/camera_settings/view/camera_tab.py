from typing import Tuple, Callable, Optional

from PyQt6.QtCore import Qt
from PyQt6.QtWidgets import QPushButton, QVBoxLayout, QHBoxLayout, QWidget, QLabel

from pl_gui.settings.settings_view.group_widget import GenericSettingGroup
from pl_gui.settings.settings_view.settings_view import SettingsView
from pl_gui.settings.settings_view.styles import BG_COLOR
from pl_gui.utils.utils_widgets.MaterialButton import MaterialButton
from src.applications.camera_settings.view.camera_settings_view import CameraSettingsView
from src.applications.camera_settings.view.camera_settings_schema import (
    CORE_GROUP, CONTOUR_GROUP, PREPROCESSING_GROUP,
    CALIBRATION_GROUP, BRIGHTNESS_GROUP, ARUCO_GROUP,
)

_LABEL_DARK  = "color: #AAAACC; font-size: 10pt; background: transparent;"
_DIVIDER_CSS = "background: #333355;"

_AREA_COLORS = {
    "pickup_area":     "#50DC64",
    "spray_area":      "#FF8C32",
    "brightness_area": "#00CCFF",
}

_AREA_BTN_BASE = """
QPushButton {{
    background-color: transparent;
    color: {color};
    border: 1.5px solid {color};
    border-radius: 6px;
    padding: 6px 10px;
    font-size: 9pt;
    font-weight: bold;
    min-height: 36px;
}}
QPushButton:checked {{
    background-color: {color};
    color: #12121F;
}}
"""


def _area_btn(label: str, color: str) -> QPushButton:
    btn = QPushButton(label)
    btn.setCheckable(True)
    btn.setStyleSheet(_AREA_BTN_BASE.format(color=color))
    btn.setCursor(Qt.CursorShape.PointingHandCursor)
    return btn


def _divider() -> QWidget:
    d = QWidget()
    d.setFixedHeight(1)
    d.setStyleSheet(_DIVIDER_CSS)
    return d


def _section_label(text: str) -> QLabel:
    lbl = QLabel(text)
    lbl.setStyleSheet(_LABEL_DARK)
    return lbl


def camera_tab_factory(mapper: Callable, parent=None) -> Tuple[CameraSettingsView, SettingsView]:
    settings_view = SettingsView(
        component_name="CameraSettings",
        mapper=mapper,
        parent=parent,
    )
    settings_view.add_tab("Core",      [CORE_GROUP])
    settings_view.add_tab("Detection", [CONTOUR_GROUP, PREPROCESSING_GROUP])
    settings_view.add_tab("Calibration", [CALIBRATION_GROUP])

    # ── Brightness tab ────────────────────────────────────────────────
    brightness_group_widget = GenericSettingGroup(BRIGHTNESS_GROUP)
    brightness_group_widget.value_changed.connect(
        lambda k, v: settings_view.value_changed_signal.emit(k, v, "CameraSettings")
    )
    settings_view._groups.append(brightness_group_widget)

    # Edit-area toggle button — same style as Areas tab
    brightness_area_btn = _area_btn("Edit Brightness Area on Preview",
                                    _AREA_COLORS["brightness_area"])
    save_brightness_btn = MaterialButton("Save Brightness Area")

    brightness_tab = QWidget()
    brightness_tab.setStyleSheet(f"background: {BG_COLOR};")
    bl = QVBoxLayout(brightness_tab)
    bl.setContentsMargins(16, 16, 16, 16)
    bl.setSpacing(16)
    bl.addWidget(brightness_group_widget)
    bl.addWidget(_divider())
    bl.addWidget(_section_label("Edit brightness measurement area on preview:"))
    bl.addWidget(brightness_area_btn)
    bl.addWidget(_divider())
    bl.addWidget(_section_label("Save brightness area to settings:"))
    bl.addWidget(save_brightness_btn)
    bl.addStretch()
    settings_view.add_raw_tab("Brightness", brightness_tab)

    settings_view.add_tab("ArUco", [ARUCO_GROUP])

    # ── Areas tab ─────────────────────────────────────────────────────
    _active_area: list[Optional[str]] = [None]

    pickup_btn = _area_btn("Pickup Area", _AREA_COLORS["pickup_area"])
    spray_btn  = _area_btn("Spray Area",  _AREA_COLORS["spray_area"])
    save_btn   = MaterialButton("Save Area")

    areas_tab = QWidget()
    areas_tab.setStyleSheet(f"background: {BG_COLOR};")
    al = QVBoxLayout(areas_tab)
    al.setContentsMargins(16, 16, 16, 16)
    al.setSpacing(12)
    al.addWidget(_section_label("Select area to edit on preview:"))

    btn_row = QWidget()
    btn_row.setStyleSheet("background: transparent;")
    btn_hl = QHBoxLayout(btn_row)
    btn_hl.setContentsMargins(0, 0, 0, 0)
    btn_hl.setSpacing(10)
    btn_hl.addWidget(pickup_btn)
    btn_hl.addWidget(spray_btn)
    al.addWidget(btn_row)
    al.addWidget(_divider())
    al.addWidget(_section_label("Save current corners to storage:"))
    al.addWidget(save_btn)
    al.addStretch()
    settings_view.add_raw_tab("Areas", areas_tab)

    # ── Build view (must come after all tabs are added) ───────────────
    view = CameraSettingsView(settings_view)

    # ── Shared deselect helper ────────────────────────────────────────

    def _deselect_all() -> None:
        for b in (pickup_btn, spray_btn, brightness_area_btn):
            b.blockSignals(True)
            b.setChecked(False)
            b.blockSignals(False)
        _active_area[0] = None
        if view.preview_label:
            view.preview_label.set_active_area(None)

    def _activate(area_name: str, clicked_btn: QPushButton,
                  *others: QPushButton) -> None:
        for b in others:
            b.blockSignals(True)
            b.setChecked(False)
            b.blockSignals(False)
        if clicked_btn.isChecked():
            _active_area[0] = area_name
            if view.preview_label:
                view.preview_label.set_active_area(area_name)
        else:
            _active_area[0] = None
            if view.preview_label:
                view.preview_label.set_active_area(None)

    # ── Area button wiring ────────────────────────────────────────────

    def _on_pickup_clicked() -> None:
        _activate("pickup_area", pickup_btn, spray_btn, brightness_area_btn)

    def _on_spray_clicked() -> None:
        _activate("spray_area", spray_btn, pickup_btn, brightness_area_btn)

    def _on_brightness_area_clicked() -> None:
        _activate("brightness_area", brightness_area_btn, pickup_btn, spray_btn)

    def _on_save_clicked() -> None:
        if _active_area[0] and _active_area[0] != "brightness_area":
            view.save_area_requested.emit(_active_area[0])

    def _on_save_brightness_clicked() -> None:
        corners = view.get_area_corners("brightness_area")
        if corners:
            view.save_brightness_area_requested.emit(corners)

    pickup_btn.clicked.connect(_on_pickup_clicked)
    spray_btn.clicked.connect(_on_spray_clicked)
    brightness_area_btn.clicked.connect(_on_brightness_area_clicked)
    save_btn.clicked.connect(_on_save_clicked)
    save_brightness_btn.clicked.connect(_on_save_brightness_clicked)

    return view, settings_view
