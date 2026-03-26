from __future__ import annotations

import cv2
import numpy as np

from PyQt6.QtCore import QPointF, Qt, pyqtSignal
from PyQt6.QtGui import QColor, QBrush, QPainter, QPainterPath, QPen, QPolygonF
from PyQt6.QtWidgets import (
    QComboBox,
    QFormLayout,
    QHBoxLayout,
    QLabel,
    QTextEdit,
    QSizePolicy,
    QSpinBox,
    QVBoxLayout,
    QWidget,
)

from pl_gui.utils.utils_widgets.MaterialButton import MaterialButton
from pl_gui.utils.utils_widgets.camera_view import CameraView
from src.applications.base.app_styles import (
    APP_BG,
    APP_CAPTION_STYLE,
    APP_CARD_STYLE,
    APP_LOG_STYLE,
    APP_PRIMARY_BUTTON_STYLE,
    APP_SECONDARY_BUTTON_STYLE,
    section_hint,
    section_label,
)
from src.shared_contracts.declarations import WorkAreaDefinition

_GRID_POINT_COLOR = QColor("#FF7043")
_GRID_POINT_FILL = QColor(255, 112, 67, 180)
_GRID_LABEL_COLOR = QColor("#1A1A2E")
_GRID_REACHABLE_COLOR = QColor("#2E7D32")
_GRID_REACHABLE_FILL = QColor(46, 125, 50, 190)
_GRID_UNREACHABLE_COLOR = QColor("#D32F2F")
_GRID_UNREACHABLE_FILL = QColor(211, 47, 47, 190)
_SUBSTITUTE_PALETTE = [
    (QColor("#F9A825"), QColor(249, 168, 37, 55)),
    (QColor("#7B1FA2"), QColor(123, 31, 162, 55)),
    (QColor("#0288D1"), QColor(2, 136, 209, 55)),
    (QColor("#E64A19"), QColor(230, 74, 25, 55)),
    (QColor("#00838F"), QColor(0, 131, 143, 55)),
]


class _GridCameraView(CameraView):
    def __init__(self, parent=None):
        super().__init__(parent)
        self._grid_points: list[tuple[float, float]] = []
        self._grid_labels: list[str] = []
        self._point_statuses: dict[str, str] = {}
        self._substitute_polygons: dict[str, list[tuple[float, float]]] = {}

    def set_grid_points(
        self,
        points: list[tuple[float, float]],
        *,
        point_labels: list[str] | None = None,
        point_statuses: dict[str, str] | None = None,
    ) -> None:
        self._grid_points = [(float(x), float(y)) for x, y in points]
        self._grid_labels = [str(label) for label in (point_labels or [])]
        self._point_statuses = {
            str(label): str(status)
            for label, status in (point_statuses or {}).items()
        }
        self.update()

    def set_substitute_regions(self, polygons: dict[str, list[tuple[float, float]]]) -> None:
        self._substitute_polygons = dict(polygons)
        self.update()

    def _paint_overlay(self, painter: QPainter, image_rect) -> None:
        if not self._grid_points and not self._substitute_polygons:
            return

        painter.setRenderHint(QPainter.RenderHint.Antialiasing)

        ordered_labels = list(self._substitute_polygons.keys())
        area_corners = self.get_area_corners(self._active_area) if self._active_area else []
        area_path: QPainterPath | None = None
        if len(area_corners) >= 3:
            area_path = QPainterPath()
            area_path.addPolygon(QPolygonF([QPointF(*self._to_pixel(xn, yn)) for xn, yn in area_corners]))
            area_path.closeSubpath()

        for i, (u_label, poly_norm) in enumerate(self._substitute_polygons.items()):
            if len(poly_norm) < 3:
                continue
            color_line, color_fill = _SUBSTITUTE_PALETTE[i % len(_SUBSTITUTE_PALETTE)]
            painter.setPen(QPen(color_line, 1.0, Qt.PenStyle.DashLine))
            painter.setBrush(QBrush(color_fill))
            circle_path = QPainterPath()
            circle_path.addPolygon(QPolygonF([QPointF(*self._to_pixel(xn, yn)) for xn, yn in poly_norm]))
            circle_path.closeSubpath()
            draw_path = circle_path.intersected(area_path) if area_path is not None else circle_path
            painter.drawPath(draw_path)

        pen = QPen(_GRID_POINT_COLOR, 1.5)
        painter.setPen(pen)
        painter.setBrush(QBrush(_GRID_POINT_FILL))

        for index, (xn, yn) in enumerate(self._grid_points):
            px, py = self._to_pixel(xn, yn)
            point_name = self._grid_labels[index] if index < len(self._grid_labels) else str(index + 1)
            status = self._point_statuses.get(point_name, "")
            if status in ("direct", "via_anchor", "reachable"):
                painter.setPen(QPen(_GRID_REACHABLE_COLOR, 1.5))
                painter.setBrush(QBrush(_GRID_REACHABLE_FILL))
            elif status == "unreachable":
                painter.setPen(QPen(_GRID_UNREACHABLE_COLOR, 1.5))
                painter.setBrush(QBrush(_GRID_UNREACHABLE_FILL))
            elif status == "substitute":
                u_label = point_name[:-4]
                pair_idx = ordered_labels.index(u_label) if u_label in ordered_labels else 0
                color_line, _ = _SUBSTITUTE_PALETTE[pair_idx % len(_SUBSTITUTE_PALETTE)]
                painter.setPen(QPen(color_line, 1.5))
                painter.setBrush(QBrush(color_line))
            else:
                painter.setPen(pen)
                painter.setBrush(QBrush(_GRID_POINT_FILL))
            painter.drawEllipse(int(px) - 4, int(py) - 4, 8, 8)
            painter.setPen(_GRID_LABEL_COLOR)
            painter.drawText(int(px) + 6, int(py) - 6, point_name)
            painter.setPen(pen)


class CalibrationAreaGridPanel(QWidget):
    work_area_changed = pyqtSignal(str)
    measurement_area_changed = pyqtSignal()
    generate_area_grid_requested = pyqtSignal()
    verify_area_grid_requested = pyqtSignal()
    measure_area_grid_requested = pyqtSignal()
    view_depth_map_requested = pyqtSignal()

    def __init__(
        self,
        preview_label: _GridCameraView,
        work_area_definitions: list[WorkAreaDefinition] | None = None,
        parent=None,
    ):
        super().__init__(parent)
        self.preview_label = preview_label
        self._work_area_definitions = [
            definition for definition in (work_area_definitions or []) if definition.supports_height_mapping
        ]
        self._active_area_key: str | None = None
        self._build_ui()

    def _build_ui(self) -> None:
        layout = QVBoxLayout(self)
        layout.setContentsMargins(0, 0, 0, 0)
        layout.setSpacing(12)

        area_card = QWidget()
        area_card.setStyleSheet(APP_CARD_STYLE)
        area_layout = QVBoxLayout(area_card)
        area_layout.setContentsMargins(16, 12, 16, 16)
        area_layout.setSpacing(10)

        area_layout.addWidget(section_label("Step 3: Define Area and Grid"))
        area_layout.addWidget(
            section_hint("Choose a work area, mark its four corners on the preview, then generate and verify the grid.")
        )

        area_top = QHBoxLayout()
        area_top.setSpacing(12)

        form = QFormLayout()
        self.work_area_combo = QComboBox()
        for definition in self._work_area_definitions:
            self.work_area_combo.addItem(definition.label, definition.id)
        self.grid_rows_spin = QSpinBox()
        self.grid_rows_spin.setRange(2, 50)
        self.grid_rows_spin.setValue(5)
        self.grid_cols_spin = QSpinBox()
        self.grid_cols_spin.setRange(2, 50)
        self.grid_cols_spin.setValue(4)
        form.addRow("Area:", self.work_area_combo)
        form.addRow("Rows:", self.grid_rows_spin)
        form.addRow("Cols:", self.grid_cols_spin)
        area_top.addLayout(form, stretch=0)

        area_actions = QVBoxLayout()
        area_actions.setSpacing(8)
        self.generate_area_grid_btn = MaterialButton("▦  Generate Grid")
        self.generate_area_grid_btn.setStyleSheet(APP_PRIMARY_BUTTON_STYLE)
        area_actions.addWidget(self.generate_area_grid_btn)

        self.measure_area_grid_btn = MaterialButton("📐  Measure Area Grid")
        self.measure_area_grid_btn.setStyleSheet(APP_PRIMARY_BUTTON_STYLE)
        self.measure_area_grid_btn.setEnabled(False)
        area_actions.addWidget(self.measure_area_grid_btn)

        self.verify_area_grid_btn = MaterialButton("🧭  Verify Grid")
        self.verify_area_grid_btn.setStyleSheet(APP_PRIMARY_BUTTON_STYLE)
        self.verify_area_grid_btn.setEnabled(False)
        area_actions.addWidget(self.verify_area_grid_btn)
        area_actions.addStretch()
        area_top.addLayout(area_actions, stretch=1)
        area_layout.addLayout(area_top)

        area_bottom = QHBoxLayout()
        area_bottom.setSpacing(8)

        self.clear_area_grid_btn = MaterialButton("✎  Clear Area")
        self.clear_area_grid_btn.setStyleSheet(APP_SECONDARY_BUTTON_STYLE)
        area_bottom.addWidget(self.clear_area_grid_btn)

        self.view_depth_map_btn = MaterialButton("📈  View Depth Map")
        self.view_depth_map_btn.setStyleSheet(APP_PRIMARY_BUTTON_STYLE)
        self.view_depth_map_btn.setEnabled(False)
        area_bottom.addWidget(self.view_depth_map_btn)

        area_layout.addLayout(area_bottom)

        layout.addWidget(area_card, stretch=0)

        self.work_area_combo.currentIndexChanged.connect(self._on_work_area_changed)
        self.generate_area_grid_btn.clicked.connect(self.generate_area_grid_requested.emit)
        self.measure_area_grid_btn.clicked.connect(self.measure_area_grid_requested.emit)
        self.verify_area_grid_btn.clicked.connect(self.verify_area_grid_requested.emit)
        self.clear_area_grid_btn.clicked.connect(self.clear_measurement_area)
        self.view_depth_map_btn.clicked.connect(self.view_depth_map_requested.emit)

    def _on_work_area_changed(self) -> None:
        self._active_area_key = self.current_height_mapping_area_key()
        self.preview_label.set_active_area(self._active_area_key)
        self.preview_label.set_grid_points([])
        self.work_area_changed.emit(self.current_work_area_id())

    def _on_measurement_area_changed(self, _area: str, _idx: int, _xn: float, _yn: float) -> None:
        self.preview_label.set_grid_points([])
        self.measurement_area_changed.emit()

    def _on_measurement_area_empty_clicked(self, _area: str, _xn: float, _yn: float) -> None:
        self.preview_label.set_grid_points([])
        self.measurement_area_changed.emit()

    def set_measure_area_grid_enabled(self, enabled: bool) -> None:
        self.measure_area_grid_btn.setEnabled(enabled)
        self.verify_area_grid_btn.setEnabled(enabled)

    def set_verify_area_grid_busy(self, busy: bool, current: int = 0, total: int = 0) -> None:
        if busy:
            if total > 0:
                self.verify_area_grid_btn.setText(f"⏳  Verifying Grid... {current}/{total}")
            else:
                self.verify_area_grid_btn.setText("⏳  Verifying Grid...")
            return
        self.verify_area_grid_btn.setText("🧭  Verify Grid")

    def set_depth_map_enabled(self, enabled: bool) -> None:
        self.view_depth_map_btn.setEnabled(enabled)

    def set_enabled(self, enabled: bool) -> None:
        self.generate_area_grid_btn.setEnabled(enabled)
        self.clear_area_grid_btn.setEnabled(enabled)
        self.grid_rows_spin.setEnabled(enabled)
        self.grid_cols_spin.setEnabled(enabled)
        self.work_area_combo.setEnabled(enabled)

    def current_work_area_id(self) -> str:
        value = self.work_area_combo.currentData()
        return str(value or "")

    def set_current_work_area_id(self, area_id: str) -> None:
        index = self.work_area_combo.findData(str(area_id or ""))
        if index >= 0:
            self.work_area_combo.setCurrentIndex(index)

    def current_height_mapping_area_key(self) -> str | None:
        area_id = self.current_work_area_id()
        for definition in self._work_area_definitions:
            if definition.id == area_id:
                return definition.id
        return None

    def set_work_area_options(self, definitions: list[WorkAreaDefinition]) -> None:
        self._work_area_definitions = [definition for definition in definitions if definition.supports_height_mapping]
        self.work_area_combo.blockSignals(True)
        self.work_area_combo.clear()
        for definition in self._work_area_definitions:
            self.work_area_combo.addItem(definition.label, definition.id)
            self.preview_label.add_area(definition.id, definition.color)
        self.work_area_combo.blockSignals(False)
        self._on_work_area_changed()

    def get_measurement_area_corners(self) -> list[tuple[float, float]]:
        area_key = self.current_height_mapping_area_key()
        return self.preview_label.get_area_corners(area_key) if area_key else []

    def clear_measurement_area(self) -> None:
        area_key = self.current_height_mapping_area_key()
        if area_key:
            self.preview_label.clear_area(area_key)
        self.preview_label.set_grid_points([])

    def set_measurement_area_corners(self, area_id: str, corners: list[tuple[float, float]]) -> None:
        for definition in self._work_area_definitions:
            if definition.id == area_id:
                self.preview_label.set_area_corners(definition.id, corners)
                return

    def set_generated_grid_points(
        self,
        points: list[tuple[float, float]],
        *,
        point_labels: list[str] | None = None,
        point_statuses: dict[str, str] | None = None,
    ) -> None:
        self.preview_label.set_grid_points(
            points,
            point_labels=point_labels,
            point_statuses=point_statuses,
        )

    def set_substitute_regions(self, polygons: dict[str, list[tuple[float, float]]]) -> None:
        self.preview_label.set_substitute_regions(polygons)

    def get_area_grid_shape(self) -> tuple[int, int]:
        return int(self.grid_rows_spin.value()), int(self.grid_cols_spin.value())


class CalibrationPreviewPanel(QWidget):
    def __init__(self, work_area_definitions: list[WorkAreaDefinition] | None = None, parent=None):
        super().__init__(parent)
        self._work_area_definitions = [
            definition for definition in (work_area_definitions or []) if definition.supports_height_mapping
        ]
        self.setStyleSheet(f"background: {APP_BG};")
        self._build_ui()

    def _build_ui(self) -> None:
        layout = QVBoxLayout(self)
        layout.setContentsMargins(12, 12, 12, 12)
        layout.setSpacing(12)

        preview_card = QWidget()
        preview_card.setStyleSheet(APP_CARD_STYLE)
        preview_layout = QVBoxLayout(preview_card)
        preview_layout.setContentsMargins(0, 0, 0, 0)
        preview_layout.setSpacing(0)

        caption = QLabel("Camera Preview")
        caption.setAlignment(Qt.AlignmentFlag.AlignCenter)
        caption.setFixedHeight(24)
        caption.setStyleSheet(APP_CAPTION_STYLE)

        self.preview_label = _GridCameraView()
        self.preview_label.setSizePolicy(QSizePolicy.Policy.Expanding, QSizePolicy.Policy.Expanding)
        for definition in self._work_area_definitions:
            self.preview_label.add_area(definition.id, definition.color)
        if self._work_area_definitions:
            self.preview_label.set_active_area(self._work_area_definitions[0].id)

        preview_layout.addWidget(caption, stretch=0)
        preview_layout.addWidget(self.preview_label, stretch=1)

        log_card = QWidget()
        log_card.setStyleSheet(APP_CARD_STYLE)
        log_layout = QVBoxLayout(log_card)
        log_layout.setContentsMargins(16, 12, 16, 16)
        log_layout.setSpacing(10)
        log_layout.addWidget(section_label("Activity"))
        log_layout.addWidget(section_hint("Live task output and verification reports appear here."))

        self.log = QTextEdit()
        self.log.setReadOnly(True)
        self.log.setStyleSheet(APP_LOG_STYLE)
        self.log.setSizePolicy(QSizePolicy.Policy.Expanding, QSizePolicy.Policy.Expanding)
        log_layout.addWidget(self.log, stretch=1)

        layout.addWidget(preview_card, stretch=5)
        layout.addWidget(log_card, stretch=2)
