from __future__ import annotations

import argparse
import os
import shutil
import sys
from pathlib import Path
from typing import Any

import cv2
import numpy as np
from PyQt6.QtCore import Qt, QTimer
from PyQt6.QtGui import QAction, QIcon, QImage, QKeySequence, QPixmap
from PyQt6.QtWidgets import (
    QApplication,
    QCheckBox,
    QComboBox,
    QDialog,
    QDialogButtonBox,
    QFileDialog,
    QFormLayout,
    QHBoxLayout,
    QLabel,
    QLineEdit,
    QMainWindow,
    QMessageBox,
    QPushButton,
    QSpinBox,
    QDoubleSpinBox,
    QTabWidget,
    QStatusBar,
    QVBoxLayout,
    QWidget,
)

from src.engine.cad import DxfContourExportOptions, export_contours_to_dxf
from src.tools.vision_dxf_exporter.calibration_transform import build_calibration_transformer
from src.tools.vision_dxf_exporter.contour_units import contours_to_calibrated_mm

try:
    from pl_gui.settings.settings_view.styles import (
        ACTION_BTN_STYLE,
        BG_COLOR,
        GHOST_BTN_STYLE,
        GROUP_STYLE,
        LABEL_STYLE,
        PRIMARY,
    )
except Exception:
    ACTION_BTN_STYLE = "QPushButton { min-height: 36px; padding: 0 14px; font-weight: bold; }"
    GHOST_BTN_STYLE = ACTION_BTN_STYLE
    GROUP_STYLE = ""
    LABEL_STYLE = "font-weight: bold;"
    BG_COLOR = "#F8F9FA"
    PRIMARY = "#905BA9"


_DXF_VERSIONS = ("R2010", "R2018", "R2013", "R2007", "R2004", "R2000", "R12")
_DXF_UNITS = ("mm", "cm", "m", "in", "ft", "unitless")
_POSTPROCESS_MODES = (
    ("None", "none"),
    ("Simplify", "simplify"),
    ("Moving average smooth", "moving_average"),
    ("Moving average + simplify", "moving_average_simplify"),
    ("Chaikin smooth", "chaikin"),
    ("Chaikin + simplify", "chaikin_simplify"),
)
_MM_TO_UNIT_SCALE = {
    "mm": 1.0,
    "cm": 0.1,
    "m": 0.001,
    "in": 1.0 / 25.4,
    "ft": 1.0 / 304.8,
    "unitless": 1.0,
}
_REPO_ROOT = Path(__file__).resolve().parents[3]
_DEFAULT_PAINT_VISION_ROOT = _REPO_ROOT / "src" / "robot_systems" / "paint" / "storage" / "settings" / "vision"
_APP_NAME = "PL DXF Vision"
_APP_DATA_DIR = "PLDxfVision"

_DARK_STYLESHEET = """
QMainWindow, QDialog, QWidget {
    background-color: #1e1e1e;
    color: #e0e0e0;
}
QLabel {
    color: #e0e0e0 !important;
}
QPushButton {
    background-color: #3c3c3c !important;
    color: #e0e0e0 !important;
    border: 1px solid #555 !important;
    border-radius: 4px;
    padding: 6px 12px;
    min-height: 28px;
}
QPushButton:hover {
    background-color: #4a4a4a !important;
}
QPushButton:pressed {
    background-color: #2a2a2a !important;
}
QComboBox {
    background-color: #3c3c3c !important;
    color: #e0e0e0 !important;
    border: 1px solid #555 !important;
    border-radius: 4px;
    padding: 4px 8px;
}
QComboBox::drop-down {
    border: none;
}
QComboBox::down-arrow {
    image: none;
    border-left: 5px solid transparent;
    border-right: 5px solid transparent;
    border-top: 6px solid #aaa;
    margin-right: 8px;
}
QSpinBox, QDoubleSpinBox {
    background-color: #3c3c3c !important;
    color: #e0e0e0 !important;
    border: 1px solid #555 !important;
    border-radius: 4px;
    padding: 4px;
}
QCheckBox {
    color: #e0e0e0 !important;
}
QCheckBox::indicator {
    background-color: #3c3c3c !important;
    border: 1px solid #555 !important;
    border-radius: 3px;
    width: 16px;
    height: 16px;
}
QCheckBox::indicator:checked {
    background-color: #905BA9 !important;
}
QTabWidget::pane {
    border: 1px solid #444;
    background-color: #252525;
}
QTabBar::tab {
    background-color: #2a2a2a;
    color: #aaa;
    padding: 8px 16px;
    border: 1px solid #444;
    border-bottom: none;
}
QTabBar::tab:selected {
    background-color: #3c3c3c;
    color: #e0e0e0;
}
QStatusBar {
    background-color: #252525;
    color: #aaa;
}
QGroupBox {
    border: 1px solid #444;
    border-radius: 6px;
    margin-top: 12px;
    padding-top: 12px;
    color: #e0e0e0;
    font-weight: bold;
}
QGroupBox::title {
    subcontrol-origin: margin;
    left: 10px;
    padding: 0 4px;
}
QScrollArea, QStackedWidget {
    background-color: #252525;
}
QListWidget, QTreeWidget, QTableWidget {
    background-color: #2a2a2a;
    color: #e0e0e0;
    border: 1px solid #444;
}
QListWidget::item, QTreeWidget::item, QTableWidget::item {
    background-color: #2a2a2a;
    color: #e0e0e0;
}
QListWidget::item:selected, QTreeWidget::item:selected, QTableWidget::item:selected {
    background-color: #905BA9;
}
"""

_DARK_BTN_STYLE = """
QPushButton {
    background-color: #3c3c3c;
    color: #e0e0e0;
    border: 1px solid #555;
    border-radius: 4px;
    padding: 0 16px;
    font-weight: bold;
    min-height: 36px;
}
QPushButton:hover {
    background-color: #4a4a4a;
}
QPushButton:pressed {
    background-color: #2a2a2a;
}
"""


def _resource_path(relative_path: str) -> Path:
    root = Path(getattr(sys, "_MEIPASS", _REPO_ROOT))
    return root / relative_path


def _default_vision_root() -> Path:
    if getattr(sys, "frozen", False):
        user_root = Path(
            os.environ.get("LOCALAPPDATA")
            or os.environ.get("APPDATA")
            or Path.home()
        ) / _APP_DATA_DIR / "vision"
        bundled_root = Path(getattr(sys, "_MEIPASS", Path(sys.executable).resolve().parent)) / "vision"
        if not user_root.exists() and bundled_root.exists():
            shutil.copytree(bundled_root, user_root)
        return user_root
    return _DEFAULT_PAINT_VISION_ROOT


class VisionDxfExporterWindow(QMainWindow):
    def __init__(self, vision_service, parent=None):
        super().__init__(parent)
        self._vision_service = vision_service
        from src.engine.vision.capture_snapshot_service import CaptureSnapshotService

        self._snapshot_service = CaptureSnapshotService(vision_service, robot_service=None)
        self._transformer = build_calibration_transformer(vision_service)
        self._captured_contours: list[Any] = []
        self._captured_frame_height: float | None = None
        self._latest_contours: list[Any] = []
        self._latest_frame_height: float | None = None

        self.setWindowTitle(_APP_NAME)
        logo_path = _resource_path("assets/Logo.png")
        if logo_path.exists():
            self.setWindowIcon(QIcon(str(logo_path)))
        self.resize(1280, 820)
        self.setStyleSheet(_DARK_STYLESHEET)
        self._build_ui()
        self._build_shortcuts()

        self._timer = QTimer(self)
        self._timer.setInterval(60)
        self._timer.timeout.connect(self._refresh_preview)
        self._timer.start()

        self._roi_points: list[tuple[int, int]] = []
        self._roi_selecting = False
        self._roi_polygon = self._load_saved_roi()

        self._preview.mousePressEvent = self._on_preview_click

    def _build_ui(self) -> None:
        root = QWidget(self)
        layout = QVBoxLayout(root)
        layout.setContentsMargins(10, 10, 10, 10)
        layout.setSpacing(8)

        self._tabs = QTabWidget()
        layout.addWidget(self._tabs, 1)

        capture_tab = QWidget()
        capture_layout = QVBoxLayout(capture_tab)
        capture_layout.setContentsMargins(0, 0, 0, 0)
        capture_layout.setSpacing(8)

        toolbar = QHBoxLayout()
        self._capture_btn = QPushButton("Capture Contours")
        self._capture_btn.setCursor(Qt.CursorShape.PointingHandCursor)
        self._capture_btn.setStyleSheet(ACTION_BTN_STYLE)
        self._capture_btn.clicked.connect(self._capture_contours)
        toolbar.addWidget(self._capture_btn)

        self._export_btn = QPushButton("Export DXF")
        self._export_btn.setCursor(Qt.CursorShape.PointingHandCursor)
        self._export_btn.setStyleSheet(ACTION_BTN_STYLE)
        self._export_btn.clicked.connect(self._export_dxf)
        toolbar.addWidget(self._export_btn)

        self._settings_btn = QPushButton("Settings")
        self._settings_btn.setCursor(Qt.CursorShape.PointingHandCursor)
        self._settings_btn.setStyleSheet(GHOST_BTN_STYLE)
        self._settings_btn.clicked.connect(self._open_settings)
        toolbar.addWidget(self._settings_btn)

        self._roi_btn = QPushButton("Set ROI Area")
        self._roi_btn.setCursor(Qt.CursorShape.PointingHandCursor)
        self._roi_btn.setStyleSheet(GHOST_BTN_STYLE)
        self._roi_btn.clicked.connect(self._start_roi_selection)
        toolbar.addWidget(self._roi_btn)

        self._clear_roi_btn = QPushButton("Clear ROI")
        self._clear_roi_btn.setCursor(Qt.CursorShape.PointingHandCursor)
        self._clear_roi_btn.setStyleSheet(GHOST_BTN_STYLE)
        self._clear_roi_btn.clicked.connect(self._clear_roi)
        toolbar.addWidget(self._clear_roi_btn)

        self._version_combo = QComboBox()
        self._version_combo.addItems(_DXF_VERSIONS)
        self._version_combo.setCurrentText("R2010")
        toolbar.addWidget(QLabel("DXF"))
        toolbar.addWidget(self._version_combo)

        self._largest_only = QCheckBox("Largest only")
        toolbar.addWidget(self._largest_only)
        toolbar.addStretch(1)
        capture_layout.addLayout(toolbar)

        self._preview = QLabel()
        self._preview.setAlignment(Qt.AlignmentFlag.AlignCenter)
        self._preview.setMinimumSize(960, 640)
        self._preview.setStyleSheet("background: #111; color: #ddd;")
        self._preview.setText("Starting vision preview...")
        capture_layout.addWidget(self._preview, 1)

        self._info = QLabel("Contours: 0")
        self._info.setStyleSheet(LABEL_STYLE)
        capture_layout.addWidget(self._info)

        self._tabs.addTab(capture_tab, "Capture")
        self._tabs.addTab(CalibrationTab(self._vision_service, self._reload_transformer), "Calibration")
        self.setCentralWidget(root)
        self.setStatusBar(QStatusBar(self))
        self._apply_dark_mode_to_buttons()

    def _apply_dark_mode_to_buttons(self) -> None:
        for widget in self.findChildren(QPushButton):
            widget.setStyleSheet(_DARK_BTN_STYLE)

    def _start_roi_selection(self) -> None:
        self._roi_points = []
        self._roi_selecting = True
        self._roi_polygon = None
        self._roi_btn.setText("Click 4 corners...")
        self._roi_btn.setEnabled(False)
        self.statusBar().showMessage("Click 4 corners on the preview to define ROI area", 5000)

    def _load_saved_roi(self) -> list | None:
        dm = self._vision_service._vision_system.service.data_manager
        pts = dm.get_named_area_points("detection")
        if pts is not None and len(pts) > 0:
            self._roi_points = [(int(p[0]), int(p[1])) for p in pts]
            return list(self._roi_points)
        return None

    def _preview_widget_to_image(self, wx: int, wy: int) -> tuple[int, int] | None:
        pix = self._preview.pixmap()
        if pix is None or pix.isNull():
            return None
        pw, ph = pix.width(), pix.height()
        lw, lh = self._preview.width(), self._preview.height()
        dx = (lw - pw) // 2
        dy = (lh - ph) // 2
        px = wx - dx
        py = wy - dy
        if px < 0 or py < 0 or px >= pw or py >= ph:
            return None
        frame = self._vision_service.get_latest_frame()
        if frame is None:
            return None
        fh, fw = frame.shape[:2]
        return (int(round(px * fw / pw)), int(round(py * fh / ph)))

    def _on_preview_click(self, event) -> None:
        if not self._roi_selecting:
            return

        pos = self._preview_widget_to_image(event.pos().x(), event.pos().y())
        if pos is None:
            return
        x, y = pos

        if len(self._roi_points) < 4:
            self._roi_points.append((x, y))
            self.statusBar().showMessage(f"Point {len(self._roi_points)}/4 selected", 2000)

            if len(self._roi_points) == 4:
                self._finish_roi_selection()

    def _finish_roi_selection(self) -> None:
        self._roi_selecting = False
        self._roi_btn.setText("Set ROI Area")
        self._roi_btn.setEnabled(True)

        if len(self._roi_points) == 4:
            self._roi_polygon = self._roi_points
            self.statusBar().showMessage(f"ROI set: {self._roi_polygon}", 5000)

            ok, msg = self._vision_service.save_work_area("detection", self._roi_points)
            if ok:
                QMessageBox.information(self, "ROI Area", f"ROI area set successfully!\n{msg}")
            else:
                QMessageBox.warning(self, "ROI Area", f"Failed to save ROI:\n{msg}")
        else:
            self._roi_points = []

    def _clear_roi(self) -> None:
        self._roi_points = []
        self._roi_polygon = None
        dm = self._vision_service._vision_system.service.data_manager
        dm.namedAreaPoints.pop("detection", None)
        import os
        path = os.path.join(dm.named_areas_dir, "detection.npy")
        if os.path.exists(path):
            os.remove(path)
        self.statusBar().showMessage("ROI cleared", 3000)

    def _build_shortcuts(self) -> None:
        settings_action = QAction("Settings", self)
        settings_action.setShortcut(QKeySequence("Ctrl+,"))
        settings_action.triggered.connect(self._open_settings)
        self.addAction(settings_action)

        capture_action = QAction("Capture Contours", self)
        capture_action.setShortcut(QKeySequence("Space"))
        capture_action.triggered.connect(self._capture_contours)
        self.addAction(capture_action)

        export_action = QAction("Export DXF", self)
        export_action.setShortcut(QKeySequence("Ctrl+E"))
        export_action.triggered.connect(self._export_dxf)
        self.addAction(export_action)

    def _refresh_preview(self) -> None:
        frame = self._vision_service.get_latest_frame()
        if frame is None:
            return

        contours = list(self._vision_service.get_latest_contours() or [])
        self._latest_contours = contours
        self._latest_frame_height = _frame_height(frame)
        if self._vision_service._vision_system.get_camera_settings().get_draw_contours():
            rendered = _draw_contours(frame, contours)
        else:
            rendered = np.asarray(frame).copy()
            if rendered.ndim == 2:
                rendered = cv2.cvtColor(rendered, cv2.COLOR_GRAY2BGR)

        if self._roi_polygon and len(self._roi_polygon) == 4:
            xs = [p[0] for p in self._roi_polygon]
            ys = [p[1] for p in self._roi_polygon]
            x, y = min(xs), min(ys)
            w, h = max(xs) - x, max(ys) - y
            if w > 0 and h > 0:
                roi_crop = rendered[y:y + h, x:x + w]
                if roi_crop.size > 0:
                    pixmap = _to_pixmap(roi_crop)
                    preview_size = self._preview.size()
                    if pixmap.width() <= preview_size.width() and pixmap.height() <= preview_size.height():
                        self._preview.setPixmap(pixmap)
                    else:
                        self._preview.setPixmap(pixmap.scaled(
                            preview_size,
                            Qt.AspectRatioMode.KeepAspectRatio,
                            Qt.TransformationMode.FastTransformation,
                        ))
                    self._info.setText(
                        f"Live contours: {len(contours)} | Captured contours: {len(self._captured_contours)} | "
                        f"Units: mm ({self._transformer.source_label()}) | ROI zoom"
                    )
                    return

        self._preview.setPixmap(_to_pixmap(rendered).scaled(
            self._preview.size(),
            Qt.AspectRatioMode.KeepAspectRatio,
            Qt.TransformationMode.FastTransformation,
        ))
        self._info.setText(
            f"Live contours: {len(contours)} | Captured contours: {len(self._captured_contours)} | "
            f"Units: mm ({self._transformer.source_label()})"
        )

    def _capture_contours(self) -> None:
        snapshot = self._snapshot_service.capture_snapshot(source="vision_dxf_exporter")
        self._captured_contours = list(snapshot.contours or [])
        self._captured_frame_height = _frame_height(snapshot.frame)
        self.statusBar().showMessage(f"Captured {len(self._captured_contours)} contour(s)", 4000)

    def _export_dxf(self) -> None:
        contours = self._captured_contours or self._latest_contours
        if not contours:
            QMessageBox.warning(self, "Export DXF", "No contours available to export.")
            return

        dialog = ExportOptionsDialog(
            self,
            dxf_version=self._version_combo.currentText(),
            largest_only=self._largest_only.isChecked(),
        )
        if dialog.exec() != QDialog.DialogCode.Accepted:
            return

        path, _ = QFileDialog.getSaveFileName(
            self,
            "Export DXF",
            os.path.expanduser("~/contours.dxf"),
            "DXF files (*.dxf)",
        )
        if not path:
            return
        if not path.lower().endswith(".dxf"):
            path += ".dxf"

        options = dialog.export_options()
        try:
            self._reload_transformer()
            export_contours = contours_to_calibrated_mm(contours, self._transformer)
            export_contours = _scale_contours_from_mm(export_contours, options.units)
            result = export_contours_to_dxf(
                export_contours,
                path,
                options=options,
                image_height=None,
                source="vision_dxf_exporter",
            )
        except Exception as exc:
            QMessageBox.critical(self, "Export DXF", f"DXF export failed:\n{exc}")
            return

        QMessageBox.information(
            self,
            "Export DXF",
            f"Exported {result.exported_count} contour(s).\nSkipped {result.skipped_count}.\n\n{result.path}",
        )

    def _reload_transformer(self) -> bool:
        return self._transformer.reload()

    def _open_settings(self) -> None:
        dialog = VisionSettingsDialog(self._vision_service, self)
        if dialog.exec() == QDialog.DialogCode.Accepted:
            self.statusBar().showMessage("Vision settings updated", 4000)

    def closeEvent(self, event) -> None:
        try:
            self._timer.stop()
            self._vision_service.stop()
        finally:
            super().closeEvent(event)


class ExportOptionsDialog(QDialog):
    def __init__(self, parent=None, *, dxf_version: str = "R2010", largest_only: bool = False):
        super().__init__(parent)
        self.setWindowTitle("Export DXF Options")
        self.setStyleSheet(_DARK_STYLESHEET)
        self._dxf_version = str(dxf_version or "R2010")
        self._largest_only_default = bool(largest_only)
        self._build_ui()
        self._load_defaults()

    def _build_ui(self) -> None:
        layout = QVBoxLayout(self)
        layout.setContentsMargins(16, 16, 16, 16)
        layout.setSpacing(12)

        form_panel = QWidget()
        form_panel.setStyleSheet(GROUP_STYLE)
        form = QFormLayout(form_panel)

        self._version = QComboBox()
        self._version.addItems(_DXF_VERSIONS)
        form.addRow("DXF standard", self._version)

        self._units = QComboBox()
        self._units.addItems(_DXF_UNITS)
        form.addRow("Units", self._units)

        self._layer = QLineEdit()
        form.addRow("Layer", self._layer)

        self._postprocess = QComboBox()
        for label, mode in _POSTPROCESS_MODES:
            self._postprocess.addItem(label, mode)
        form.addRow("Post-processing", self._postprocess)

        self._simplify_tolerance = _double_spin(0.0, 1000.0, decimals=4, step=0.05)
        self._simplify_tolerance.setSuffix(" units")
        form.addRow("Simplify tolerance", self._simplify_tolerance)

        self._smooth_window = _spin(3, 99)
        form.addRow("Smooth window", self._smooth_window)

        self._smooth_iterations = _spin(0, 8)
        form.addRow("Smooth iterations", self._smooth_iterations)

        self._min_area = _double_spin(0.0, 100_000_000.0, decimals=3, step=1.0)
        self._min_area.setSuffix(" square units")
        form.addRow("Minimum area", self._min_area)

        self._largest_only = QCheckBox()
        form.addRow("Largest contour only", self._largest_only)

        self._normalize_to_origin = QCheckBox()
        form.addRow("Move lower-left to 0,0", self._normalize_to_origin)

        self._close_contours = QCheckBox()
        form.addRow("Close contours", self._close_contours)

        layout.addWidget(form_panel)

        buttons = QDialogButtonBox(
            QDialogButtonBox.StandardButton.Ok | QDialogButtonBox.StandardButton.Cancel
        )
        ok_button = buttons.button(QDialogButtonBox.StandardButton.Ok)
        cancel_button = buttons.button(QDialogButtonBox.StandardButton.Cancel)
        if ok_button is not None:
            ok_button.setText("Export")
            ok_button.setCursor(Qt.CursorShape.PointingHandCursor)
            ok_button.setStyleSheet(_DARK_BTN_STYLE)
        if cancel_button is not None:
            cancel_button.setCursor(Qt.CursorShape.PointingHandCursor)
            cancel_button.setStyleSheet(_DARK_BTN_STYLE)
        buttons.accepted.connect(self.accept)
        buttons.rejected.connect(self.reject)
        layout.addWidget(buttons)

    def _load_defaults(self) -> None:
        self._version.setCurrentText(self._dxf_version)
        self._units.setCurrentText("mm")
        self._layer.setText("OUTER_CONTOURS")
        self._postprocess.setCurrentIndex(0)
        self._simplify_tolerance.setValue(0.0)
        self._smooth_window.setValue(5)
        self._smooth_iterations.setValue(1)
        self._min_area.setValue(1.0)
        self._largest_only.setChecked(self._largest_only_default)
        self._normalize_to_origin.setChecked(False)
        self._close_contours.setChecked(True)

    def export_options(self) -> DxfContourExportOptions:
        return DxfContourExportOptions(
            dxf_version=self._version.currentText(),
            units=self._units.currentText(),
            layer_name=self._layer.text().strip() or "OUTER_CONTOURS",
            close_contours=self._close_contours.isChecked(),
            largest_only=self._largest_only.isChecked(),
            min_area=self._min_area.value(),
            postprocess_mode=str(self._postprocess.currentData() or "none"),
            simplify_tolerance=self._simplify_tolerance.value(),
            smooth_window=_odd(self._smooth_window.value()),
            smooth_iterations=self._smooth_iterations.value(),
            normalize_to_origin=self._normalize_to_origin.isChecked(),
            image_coordinates=False,
            invert_y_axis=False,
        )


class VisionSettingsDialog(QDialog):
    def __init__(self, vision_service, parent=None):
        super().__init__(parent)
        self._vision_service = vision_service
        self._settings = vision_service._vision_system.get_camera_settings()
        self.setWindowTitle("Camera and Contour Settings")
        self.setStyleSheet(_DARK_STYLESHEET)
        self._build_ui()
        self._load()

    def _build_ui(self) -> None:
        layout = QVBoxLayout(self)
        form = QFormLayout()

        self._contour_detection = QCheckBox()
        form.addRow("Contour detection", self._contour_detection)

        self._draw_contours = QCheckBox()
        form.addRow("Draw contours", self._draw_contours)

        self._threshold = _spin(0, 255)
        form.addRow("Threshold", self._threshold)

        self._pickup_threshold = _spin(0, 255)
        form.addRow("Pickup threshold", self._pickup_threshold)

        self._epsilon = _double_spin(0.0, 1.0, decimals=5, step=0.001)
        form.addRow("Epsilon", self._epsilon)

        self._min_area = _double_spin(0.0, 100_000_000.0, decimals=1, step=100.0)
        form.addRow("Min contour area", self._min_area)

        self._max_area = _double_spin(0.0, 100_000_000.0, decimals=1, step=1000.0)
        form.addRow("Max contour area", self._max_area)

        self._threshold_type = QComboBox()
        self._threshold_type.addItems(["binary", "binary_inv", "trunc", "tozero", "tozero_inv"])
        form.addRow("Threshold type", self._threshold_type)

        self._gaussian_blur = QCheckBox()
        form.addRow("Gaussian blur", self._gaussian_blur)

        self._blur_kernel = _spin(1, 99)
        form.addRow("Blur kernel", self._blur_kernel)

        self._dilate_enabled = QCheckBox()
        form.addRow("Dilate enabled", self._dilate_enabled)

        self._dilate_kernel = _spin(1, 99)
        form.addRow("Dilate kernel", self._dilate_kernel)

        self._dilate_iterations = _spin(0, 30)
        form.addRow("Dilate iterations", self._dilate_iterations)

        self._erode_enabled = QCheckBox()
        form.addRow("Erode enabled", self._erode_enabled)

        self._erode_kernel = _spin(1, 99)
        form.addRow("Erode kernel", self._erode_kernel)

        self._erode_iterations = _spin(0, 30)
        form.addRow("Erode iterations", self._erode_iterations)

        # Brightness section
        self._brightness_auto = QCheckBox()
        form.addRow("Auto brightness", self._brightness_auto)

        self._target_brightness = _spin(0, 255)
        form.addRow("Target brightness", self._target_brightness)

        self._brightness_kp = _double_spin(0.0, 10.0, decimals=3, step=0.1)
        form.addRow("PID Kp", self._brightness_kp)

        self._brightness_ki = _double_spin(0.0, 10.0, decimals=3, step=0.1)
        form.addRow("PID Ki", self._brightness_ki)

        self._brightness_kd = _double_spin(0.0, 10.0, decimals=3, step=0.1)
        form.addRow("PID Kd", self._brightness_kd)

        layout.addLayout(form)
        buttons = QDialogButtonBox(
            QDialogButtonBox.StandardButton.Save | QDialogButtonBox.StandardButton.Cancel
        )
        buttons.accepted.connect(self._save)
        buttons.rejected.connect(self.reject)
        layout.addWidget(buttons)

    def _load(self) -> None:
        s = self._settings
        self._contour_detection.setChecked(bool(s.get_contour_detection()))
        self._draw_contours.setChecked(bool(s.get_draw_contours()))
        self._threshold.setValue(int(s.get_threshold()))
        self._pickup_threshold.setValue(int(s.get_threshold_pickup_area()))
        self._epsilon.setValue(float(s.get_epsilon()))
        self._min_area.setValue(float(s.get_min_contour_area()))
        self._max_area.setValue(float(s.get_max_contour_area()))
        self._threshold_type.setCurrentText(str(s.get_threshold_type()))
        self._gaussian_blur.setChecked(bool(s.get_gaussian_blur()))
        self._blur_kernel.setValue(int(s.get_blur_kernel_size()))
        self._dilate_enabled.setChecked(bool(s.get_dilate_enabled()))
        self._dilate_kernel.setValue(int(s.get_dilate_kernel_size()))
        self._dilate_iterations.setValue(int(s.get_dilate_iterations()))
        self._erode_enabled.setChecked(bool(s.get_erode_enabled()))
        self._erode_kernel.setValue(int(s.get_erode_kernel_size()))
        self._erode_iterations.setValue(int(s.get_erode_iterations()))
        self._brightness_auto.setChecked(bool(s.get_brightness_auto()))
        self._target_brightness.setValue(int(s.get_target_brightness()))
        self._brightness_kp.setValue(float(s.get_brightness_kp()))
        self._brightness_ki.setValue(float(s.get_brightness_ki()))
        self._brightness_kd.setValue(float(s.get_brightness_kd()))

    def _save(self) -> None:
        payload = {
            "Contour detection": self._contour_detection.isChecked(),
            "Draw contours": self._draw_contours.isChecked(),
            "Threshold": self._threshold.value(),
            "Threshold pickup area": self._pickup_threshold.value(),
            "Epsilon": self._epsilon.value(),
            "Min contour area": self._min_area.value(),
            "Max contour area": self._max_area.value(),
            "Preprocessing": {
                "Threshold type": self._threshold_type.currentText(),
                "Gaussian blur": self._gaussian_blur.isChecked(),
                "Blur kernel size": _odd(self._blur_kernel.value()),
                "Dilate enabled": self._dilate_enabled.isChecked(),
                "Dilate kernel size": _odd(self._dilate_kernel.value()),
                "Dilate iterations": self._dilate_iterations.value(),
                "Erode enabled": self._erode_enabled.isChecked(),
                "Erode kernel size": _odd(self._erode_kernel.value()),
                "Erode iterations": self._erode_iterations.value(),
            },
            "Enable auto adjust": self._brightness_auto.isChecked(),
            "Target brightness": self._target_brightness.value(),
            "Kp": self._brightness_kp.value(),
            "Ki": self._brightness_ki.value(),
            "Kd": self._brightness_kd.value(),
        }
        ok, message = self._vision_service.update_settings(payload)
        if not ok:
            QMessageBox.warning(self, "Settings", message)
            return
        try:
            self._vision_service._vision_system.service.saveSettings(
                self._vision_service._vision_system.get_camera_settings().to_dict()
            )
        except Exception as exc:
            QMessageBox.warning(self, "Settings", f"Settings applied but not saved:\n{exc}")
            return
        self.accept()


class CalibrationTab(QWidget):
    def __init__(self, vision_service, on_calibration_changed, parent=None):
        super().__init__(parent)
        self._vision_service = vision_service
        self._on_calibration_changed = on_calibration_changed
        self._settings = vision_service._vision_system.get_camera_settings()
        self._auto_calibrate_thread = None
        self._build_ui()

    def _build_ui(self) -> None:
        layout = QVBoxLayout(self)
        layout.setContentsMargins(10, 10, 10, 10)
        layout.setSpacing(10)

        board_type_layout = QHBoxLayout()
        board_type_layout.addWidget(QLabel("Board type:"))
        self._board_type = QComboBox()
        self._board_type.addItems(["Chessboard", "CharUco"])
        self._board_type.currentTextChanged.connect(self._on_board_type_changed)
        board_type_layout.addWidget(self._board_type)
        board_type_layout.addStretch(1)
        layout.addLayout(board_type_layout)

        self._chessboard_panel = QWidget()
        chessboard_layout = QFormLayout(self._chessboard_panel)
        chessboard_layout.setContentsMargins(0, 0, 0, 0)

        self._chessboard_width = _spin(2, 200)
        self._chessboard_width.setValue(int(self._settings.get_chessboard_width()))
        chessboard_layout.addRow("Chessboard width", self._chessboard_width)

        self._chessboard_height = _spin(2, 200)
        self._chessboard_height.setValue(int(self._settings.get_chessboard_height()))
        chessboard_layout.addRow("Chessboard height", self._chessboard_height)

        self._square_size = _double_spin(0.1, 500.0, decimals=3, step=1.0)
        self._square_size.setSuffix(" mm")
        self._square_size.setValue(float(self._settings.get_square_size_mm()))
        chessboard_layout.addRow("Square size", self._square_size)
        self._chessboard_panel.setStyleSheet(GROUP_STYLE)
        layout.addWidget(self._chessboard_panel)

        self._charuco_panel = QWidget()
        charuco_layout = QFormLayout(self._charuco_panel)
        charuco_layout.setContentsMargins(0, 0, 0, 0)

        self._charuco_width = _spin(2, 50)
        self._charuco_width.setValue(int(getattr(self._settings, 'charuco_board_width', 5)))
        charuco_layout.addRow("CharUco width", self._charuco_width)

        self._charuco_height = _spin(2, 50)
        self._charuco_height.setValue(int(getattr(self._settings, 'charuco_board_height', 7)))
        charuco_layout.addRow("CharUco height", self._charuco_height)

        self._charuco_square_size = _double_spin(0.1, 500.0, decimals=3, step=1.0)
        self._charuco_square_size.setSuffix(" mm")
        self._charuco_square_size.setValue(float(getattr(self._settings, 'charuco_square_size_mm', 25.0)))
        charuco_layout.addRow("Square size", self._charuco_square_size)

        self._charuco_marker_size = _double_spin(0.1, 500.0, decimals=3, step=1.0)
        self._charuco_marker_size.setSuffix(" mm")
        self._charuco_marker_size.setValue(float(getattr(self._settings, 'charuco_marker_size_mm', 18.75)))
        charuco_layout.addRow("Marker size", self._charuco_marker_size)
        self._charuco_panel.setStyleSheet(GROUP_STYLE)
        self._charuco_panel.setVisible(False)
        layout.addWidget(self._charuco_panel)

        actions = QHBoxLayout()
        capture = QPushButton("Capture Calibration Image")
        capture.setCursor(Qt.CursorShape.PointingHandCursor)
        capture.setStyleSheet(ACTION_BTN_STYLE)
        capture.clicked.connect(self._capture)
        actions.addWidget(capture)

        calibrate = QPushButton("Calibrate Camera")
        calibrate.setCursor(Qt.CursorShape.PointingHandCursor)
        calibrate.setStyleSheet(ACTION_BTN_STYLE)
        calibrate.clicked.connect(self._calibrate)
        actions.addWidget(calibrate)

        auto_calibrate = QPushButton("Auto Capture & Calibrate")
        auto_calibrate.setCursor(Qt.CursorShape.PointingHandCursor)
        auto_calibrate.setStyleSheet(ACTION_BTN_STYLE)
        auto_calibrate.clicked.connect(self._show_auto_calibrate_dialog)
        actions.addWidget(auto_calibrate)

        actions.addStretch(1)
        layout.addLayout(actions)

        self._status = QLabel("Calibration images: 0")
        self._status.setStyleSheet(LABEL_STYLE)
        layout.addWidget(self._status)
        layout.addStretch(1)

    def _on_board_type_changed(self, text: str) -> None:
        is_charuco = text == "CharUco"
        self._chessboard_panel.setVisible(not is_charuco)
        self._charuco_panel.setVisible(is_charuco)

    def _show_auto_calibrate_dialog(self) -> None:
        dialog = AutoCalibrateDialog(
            self,
            board_type=self._board_type.currentText(),
            chessboard_width=self._chessboard_width.value(),
            chessboard_height=self._chessboard_height.value(),
            square_size=self._square_size.value(),
            charuco_width=self._charuco_width.value(),
            charuco_height=self._charuco_height.value(),
            charuco_square_size=self._charuco_square_size.value(),
            charuco_marker_size=self._charuco_marker_size.value(),
        )
        if dialog.exec() == QDialog.DialogCode.Accepted:
            params = dialog.get_parameters()
            self._start_auto_calibrate(params)

    def _start_auto_calibrate(self, params: dict) -> None:
        self._apply_settings()
        self._status.setText("Auto calibrating...")
        QTimer.singleShot(100, lambda: self._auto_calibrate_threaded(params))

    def _auto_calibrate_threaded(self, params: dict) -> None:
        import threading
        import time

        board_type = params["board_type"]
        target_images = params["target_images"]
        delay_ms = params["delay_ms"]
        auto_calibrate_after = params["auto_calibrate_after"]

        captured = 0
        for i in range(target_images):
            ok, msg = self._vision_service.capture_calibration_image()
            if ok:
                captured += 1
                self._status.setText(f"Captured {captured}/{target_images} images...")
                QApplication.processEvents()
                time.sleep(delay_ms / 1000.0)

        self._status.setText(f"Captured {captured} images. Calibrating...")

        ok, msg = self._vision_service.calibrate_camera()
        if ok:
            self._on_calibration_changed()
            QMessageBox.information(self, "Auto Calibrate", f"Calibration successful!\n{msg}")
        else:
            QMessageBox.warning(self, "Auto Calibrate", f"Calibration failed:\n{msg}")

        self._status.setText(f"Calibration images: {captured}")

    def _apply_settings(self) -> bool:
        board_type = self._board_type.currentText()
        if board_type == "CharUco":
            payload = {
                "Calibration": {
                    "Chessboard width": self._charuco_width.value(),
                    "Chessboard height": self._charuco_height.value(),
                    "Square size (mm)": self._charuco_square_size.value(),
                }
            }
        else:
            payload = {
                "Calibration": {
                    "Chessboard width": self._chessboard_width.value(),
                    "Chessboard height": self._chessboard_height.value(),
                    "Square size (mm)": self._square_size.value(),
                }
            }
        ok, message = self._vision_service.update_settings(payload)
        if not ok:
            QMessageBox.warning(self, "Calibration", message)
            return False
        try:
            self._vision_service._vision_system.service.saveSettings(
                self._vision_service._vision_system.get_camera_settings().to_dict()
            )
        except Exception as exc:
            QMessageBox.warning(self, "Calibration", f"Settings applied but not saved:\n{exc}")
            return False
        return True

    def _capture(self) -> None:
        if not self._apply_settings():
            return
        ok, message = self._vision_service.capture_calibration_image()
        QMessageBox.information(self, "Calibration", message) if ok else QMessageBox.warning(self, "Calibration", message)

    def _calibrate(self) -> None:
        if not self._apply_settings():
            return
        ok, message = self._vision_service.calibrate_camera()
        if ok:
            self._on_calibration_changed()
            QMessageBox.information(self, "Calibration", message)
        else:
            QMessageBox.warning(self, "Calibration", message)


class AutoCalibrateDialog(QDialog):
    def __init__(self, parent=None, board_type="Chessboard", chessboard_width=32, chessboard_height=20, square_size=25.0, charuco_width=5, charuco_height=7, charuco_square_size=25.0, charuco_marker_size=18.75):
        super().__init__(parent)
        self.setWindowTitle("Auto Capture & Calibrate")
        self.setStyleSheet(_DARK_STYLESHEET)
        self._board_type = board_type
        self._build_ui()

    def _build_ui(self) -> None:
        layout = QVBoxLayout(self)
        layout.setContentsMargins(16, 16, 16, 16)
        layout.setSpacing(12)

        form = QFormLayout()

        self._target_images = _spin(5, 50)
        self._target_images.setValue(10)
        form.addRow("Number of images", self._target_images)

        self._delay_ms = _spin(100, 5000)
        self._delay_ms.setValue(500)
        form.addRow("Delay between captures (ms)", self._delay_ms)

        self._auto_calibrate_after = _spin(3, 50)
        self._auto_calibrate_after.setValue(10)
        form.addRow("Auto-calibrate after N images", self._auto_calibrate_after)

        layout.addLayout(form)

        buttons = QDialogButtonBox(QDialogButtonBox.StandardButton.Ok | QDialogButtonBox.StandardButton.Cancel)
        ok_btn = buttons.button(QDialogButtonBox.StandardButton.Ok)
        ok_btn.setText("Start")
        ok_btn.setStyleSheet(_DARK_BTN_STYLE)
        cancel_btn = buttons.button(QDialogButtonBox.StandardButton.Cancel)
        cancel_btn.setStyleSheet(_DARK_BTN_STYLE)
        buttons.accepted.connect(self.accept)
        buttons.rejected.connect(self.reject)
        layout.addWidget(buttons)

    def get_parameters(self) -> dict:
        return {
            "board_type": self._board_type,
            "target_images": self._target_images.value(),
            "delay_ms": self._delay_ms.value(),
            "auto_calibrate_after": self._auto_calibrate_after.value(),
        }


def build_vision_service(data_storage_path: str, settings_file_path: str):
    from src.engine.vision.implementation.VisionSystem.VisionSystem import VisionSystem
    from src.engine.vision.implementation.VisionSystem.core.service.internal_service import Service
    from src.engine.vision.vision_service import VisionService

    os.makedirs(data_storage_path, exist_ok=True)
    internal_service = Service(
        data_storage_path=data_storage_path,
        settings_file_path=settings_file_path,
    )
    vision_system = VisionSystem(
        storage_path=data_storage_path,
        messaging_service=None,
        service=internal_service,
        work_area_service=None,
    )
    return VisionService(vision_system)


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description="Standalone vision contour DXF exporter")
    parser.add_argument(
        "--self-test",
        action="store_true",
        help=argparse.SUPPRESS,
    )
    parser.add_argument(
        "--data-storage-path",
        default=str(_default_vision_root() / "data"),
        help="Vision data directory containing calibration artifacts",
    )
    parser.add_argument(
        "--settings-file",
        default=str(_default_vision_root() / "camera_settings.json"),
        help="Camera settings JSON path",
    )
    args = parser.parse_args(argv)
    if args.self_test:
        from src.engine.vision.implementation.VisionSystem.VisionSystem import VisionSystem as _VisionSystem

        return 0 if _VisionSystem is not None else 1

    app = QApplication(sys.argv[:1])
    app.setApplicationName(_APP_NAME)
    app.setDesktopFileName("PLDxfVision")
    logo_path = _resource_path("assets/Logo.png")
    if logo_path.exists():
        app.setWindowIcon(QIcon(str(logo_path)))
    vision_service = build_vision_service(args.data_storage_path, args.settings_file)
    try:
        vision_service.start()
    except Exception as exc:
        QMessageBox.critical(None, _APP_NAME, f"Failed to start vision:\n{exc}")
        return 1

    window = VisionDxfExporterWindow(vision_service)
    window.show()
    return app.exec()


def _draw_contours(frame, contours: list[Any]):
    image = np.asarray(frame).copy()
    if image.ndim == 2:
        image = cv2.cvtColor(image, cv2.COLOR_GRAY2BGR)
    for contour in contours:
        try:
            pts = np.asarray(contour, dtype=np.int32).reshape(-1, 1, 2)
        except Exception:
            continue
        if len(pts) >= 2:
            cv2.polylines(image, [pts], True, (0, 255, 0), 2)
    return image


def _to_pixmap(frame) -> QPixmap:
    image = np.asarray(frame)
    if image.ndim == 2:
        rgb = cv2.cvtColor(image, cv2.COLOR_GRAY2RGB)
    else:
        rgb = cv2.cvtColor(image, cv2.COLOR_BGR2RGB)
    rgb = np.ascontiguousarray(rgb)
    height, width, channels = rgb.shape
    qimage = QImage(rgb.data, width, height, channels * width, QImage.Format.Format_RGB888)
    return QPixmap.fromImage(qimage.copy())


def _frame_height(frame) -> float | None:
    if frame is None:
        return None
    try:
        return float(frame.shape[0])
    except Exception:
        return None


def _scale_contours_from_mm(contours: list[Any], units: str) -> list[np.ndarray]:
    scale = _MM_TO_UNIT_SCALE.get(str(units or "mm").strip().lower(), 1.0)
    if abs(scale - 1.0) <= 1e-12:
        return [np.asarray(contour, dtype=float) for contour in contours]
    scaled: list[np.ndarray] = []
    for contour in contours:
        scaled.append(np.asarray(contour, dtype=float) * scale)
    return scaled


def _spin(minimum: int, maximum: int) -> QSpinBox:
    widget = QSpinBox()
    widget.setRange(minimum, maximum)
    return widget


def _double_spin(minimum: float, maximum: float, *, decimals: int, step: float) -> QDoubleSpinBox:
    widget = QDoubleSpinBox()
    widget.setRange(minimum, maximum)
    widget.setDecimals(decimals)
    widget.setSingleStep(step)
    return widget


def _odd(value: int) -> int:
    value = max(1, int(value))
    return value if value % 2 == 1 else value + 1
