from __future__ import annotations

from dataclasses import replace

import numpy as np
from PyQt6.QtCore import QPoint, QRect, Qt, pyqtSignal
from PyQt6.QtGui import QColor, QImage, QPainter, QPen
from PyQt6.QtWidgets import (
    QCheckBox,
    QComboBox,
    QFormLayout,
    QGridLayout,
    QGroupBox,
    QHBoxLayout,
    QLabel,
    QLineEdit,
    QPushButton,
    QSizePolicy,
    QSlider,
    QScrollArea,
    QSplitter,
    QTabWidget,
    QVBoxLayout,
    QWidget,
)

from pl_gui.settings.settings_view.styles import (
    ACTION_BTN_STYLE,
    BG_COLOR,
    BORDER,
    ERROR_COLOR,
    GROUP_STYLE,
    LABEL_STYLE,
    PRIMARY,
    TEXT_COLOR,
    SAVE_BUTTON_STYLE,
)
from src.applications.base.i_application_view import IApplicationView
from src.applications.base.widgets.custom_virtual_keyboard import (
    KeyboardDoubleSpinBox,
    KeyboardLineEdit,
    KeyboardSpinBox,
)
from src.applications.shaft_alignment.service.i_shaft_alignment_service import AlignmentSnapshot
from src.applications.shaft_alignment.settings.shaft_alignment_settings import ShaftAlignmentSettings

_OK_COLOR = "#2E7D32"


class _CameraCanvas(QLabel):
    def __init__(self) -> None:
        super().__init__()
        self.setAlignment(Qt.AlignmentFlag.AlignCenter)
        self.setMinimumSize(560, 420)
        self.setSizePolicy(QSizePolicy.Policy.Expanding, QSizePolicy.Policy.Expanding)
        self.setStyleSheet(f"background-color: {TEXT_COLOR}; border: 1px solid {BORDER};")
        self._source: QImage | None = None
        self._corners: tuple[tuple[float, float], ...] = ()
        self._reference_corners: tuple[tuple[float, float], ...] = ()
        self._point_of_interest: tuple[float, float] | None = None
        self._detection_region: tuple[float, float, float, float] | None = None
        self._misaligned = False
        self._correction: tuple[float, float, float] | None = None

    def set_frame(
        self,
        frame,
        corners,
        reference_corners,
        point_of_interest,
        misaligned: bool,
        detection_region=None,
        correction=None,
    ) -> None:
        self._source = self._to_image(frame)
        self._corners = tuple(corners)
        self._reference_corners = tuple(reference_corners)
        self._point_of_interest = point_of_interest
        self._misaligned = bool(misaligned)
        self._detection_region = detection_region
        self._correction = correction
        self.update()

    def paintEvent(self, event) -> None:
        super().paintEvent(event)
        painter = QPainter(self)
        if self._source is None:
            painter.setPen(QColor(BG_COLOR))
            painter.drawText(self.rect(), Qt.AlignmentFlag.AlignCenter, self.tr("No camera frame"))
            return
        image_rect = self._image_rect()
        painter.drawImage(image_rect, self._source)
        if self._detection_region is not None:
            left, top, right, bottom = self._detection_region
            painter.setPen(QPen(QColor(PRIMARY), 3, Qt.PenStyle.DashLine))
            painter.drawRect(
                QRect(
                    round(image_rect.left() + left * image_rect.width()),
                    round(image_rect.top() + top * image_rect.height()),
                    round((right - left) * image_rect.width()),
                    round((bottom - top) * image_rect.height()),
                )
            )
        if len(self._reference_corners) == 4:
            painter.setPen(QPen(QColor(PRIMARY), 3, Qt.PenStyle.DotLine))
            reference_points = [
                QPoint(
                    round(image_rect.left() + x * image_rect.width()),
                    round(image_rect.top() + y * image_rect.height()),
                )
                for x, y in self._reference_corners
            ]
            for start, end in zip(
                reference_points, reference_points[1:] + reference_points[:1]
            ):
                painter.drawLine(start, end)
            painter.drawText(reference_points[0] + QPoint(6, -6), self.tr("Reference"))
        if len(self._corners) == 4:
            color = QColor(ERROR_COLOR if self._misaligned else _OK_COLOR)
            painter.setPen(QPen(color, 4))
            points = [
                QPoint(
                    round(image_rect.left() + x * image_rect.width()),
                    round(image_rect.top() + y * image_rect.height()),
                )
                for x, y in self._corners
            ]
            for start, end in zip(points, points[1:] + points[:1]):
                painter.drawLine(start, end)
        if self._point_of_interest is not None:
            x, y = self._point_of_interest
            center = QPoint(
                round(image_rect.left() + x * image_rect.width()),
                round(image_rect.top() + y * image_rect.height()),
            )
            painter.setPen(QPen(QColor(PRIMARY), 3))
            painter.drawEllipse(center, 7, 7)
            painter.drawText(center + QPoint(11, -8), self.tr("POI"))
        if self._correction is not None:
            self._draw_correction_guide(painter, image_rect)

    def _draw_correction_guide(self, painter: QPainter, image_rect: QRect) -> None:
        correction_x, correction_y, correction_rz = self._correction
        panel = QRect(image_rect.left() + 16, image_rect.bottom() - 124, 330, 108)
        background = QColor(BG_COLOR)
        background.setAlpha(225)
        painter.fillRect(panel, background)
        color = QColor(ERROR_COLOR if self._misaligned else _OK_COLOR)
        painter.setPen(QPen(color, 3))
        origin = QPoint(panel.left() + 76, panel.top() + 62)
        x_length = 48 if correction_x >= 0.0 else -48
        y_length = -42 if correction_y >= 0.0 else 42
        self._draw_arrow(painter, origin, QPoint(origin.x() + x_length, origin.y()))
        self._draw_arrow(painter, origin, QPoint(origin.x(), origin.y() + y_length))
        painter.drawText(
            panel.adjusted(126, 12, -8, -8),
            Qt.AlignmentFlag.AlignLeft | Qt.AlignmentFlag.AlignTop,
            self.tr("Tool correction")
            + f"\nX {correction_x:+.3f} mm"
            + f"\nY {correction_y:+.3f} mm"
            + f"\nRZ {correction_rz:+.2f} deg "
            + ("↶" if correction_rz >= 0.0 else "↷"),
        )
        painter.drawText(origin + QPoint(x_length + 5, 5), "X")
        painter.drawText(origin + QPoint(5, y_length + (2 if y_length > 0 else -5)), "Y")

    @staticmethod
    def _draw_arrow(painter: QPainter, start: QPoint, end: QPoint) -> None:
        painter.drawLine(start, end)
        dx = end.x() - start.x()
        dy = end.y() - start.y()
        length = max(1.0, (dx * dx + dy * dy) ** 0.5)
        ux, uy = dx / length, dy / length
        perpendicular_x, perpendicular_y = -uy, ux
        for side in (-1, 1):
            painter.drawLine(
                end,
                QPoint(
                    round(end.x() - ux * 12 + side * perpendicular_x * 6),
                    round(end.y() - uy * 12 + side * perpendicular_y * 6),
                ),
            )

    def _image_rect(self) -> QRect:
        if self._source is None or self._source.isNull():
            return self.rect()
        scaled = self._source.size().scaled(self.size(), Qt.AspectRatioMode.KeepAspectRatio)
        return QRect(
            (self.width() - scaled.width()) // 2,
            (self.height() - scaled.height()) // 2,
            scaled.width(),
            scaled.height(),
        )

    @staticmethod
    def _to_image(frame) -> QImage | None:
        if not isinstance(frame, np.ndarray) or frame.size == 0:
            return None
        if frame.ndim == 2:
            height, width = frame.shape
            return QImage(frame.data, width, height, width, QImage.Format.Format_Grayscale8).copy()
        height, width, channels = frame.shape
        if channels != 3:
            return None
        rgb = frame[..., ::-1].copy()
        return QImage(rgb.data, width, height, width * 3, QImage.Format.Format_RGB888).copy()


class ShaftAlignmentView(IApplicationView):
    SHOW_JOG_WIDGET = True

    capture_reference_requested = pyqtSignal(int)
    thresholds_changed = pyqtSignal(float, float, float, float, float)
    save_settings_requested = pyqtSignal(object)
    check_alignment_requested = pyqtSignal()

    def __init__(self, parent=None) -> None:
        super().__init__("Shaft Alignment", parent)

    def setup_ui(self) -> None:
        self._continuous_mode = True
        self.setStyleSheet(f"background-color: {BG_COLOR};")
        root = QVBoxLayout(self)
        root.setContentsMargins(12, 12, 12, 12)
        root.setSpacing(12)
        self._tabs = QTabWidget()
        alignment_page = QWidget()
        alignment_layout = QHBoxLayout(alignment_page)
        alignment_layout.setContentsMargins(0, 0, 0, 0)
        splitter = QSplitter(Qt.Orientation.Horizontal)
        self._camera = _CameraCanvas()
        splitter.addWidget(self._camera)

        controls = QWidget()
        controls_layout = QVBoxLayout(controls)
        controls_layout.setSpacing(10)
        self._status = QLabel()
        self._status.setAlignment(Qt.AlignmentFlag.AlignCenter)
        self._status.setMinimumHeight(48)
        controls_layout.addWidget(self._status)

        mode_row = QHBoxLayout()
        self._mode_label = QLabel()
        self._mode_label.setStyleSheet(LABEL_STYLE)
        self._mode = QComboBox()
        self._mode.addItem("", "continuous")
        self._mode.addItem("", "once")
        self._mode.currentIndexChanged.connect(self._on_mode_changed)
        self._check_alignment = QPushButton()
        self._check_alignment.setStyleSheet(ACTION_BTN_STYLE)
        self._check_alignment.setCursor(Qt.CursorShape.PointingHandCursor)
        self._check_alignment.clicked.connect(self._on_check_alignment)
        self._check_alignment.setVisible(False)
        mode_row.addWidget(self._mode_label)
        mode_row.addWidget(self._mode, stretch=1)
        mode_row.addWidget(self._check_alignment)
        controls_layout.addLayout(mode_row)

        self._measurement_box = QGroupBox()
        self._measurement_box.setStyleSheet(GROUP_STYLE)
        measurement_layout = QGridLayout(self._measurement_box)
        self._measurement_values = {}
        for row, key in enumerate(("TCP X", "TCP Y", "RZ", "Marker width", "Marker height")):
            label = QLabel()
            label.setStyleSheet(LABEL_STYLE)
            value = QLabel("—")
            value.setAlignment(Qt.AlignmentFlag.AlignRight)
            measurement_layout.addWidget(label, row, 0)
            measurement_layout.addWidget(value, row, 1)
            self._measurement_values[key] = (label, value)
        controls_layout.addWidget(self._measurement_box)

        self._reference_box = QGroupBox()
        self._reference_box.setStyleSheet(GROUP_STYLE)
        reference_measurement_layout = QGridLayout(self._reference_box)
        self._reference_values = {}
        for row, key in enumerate(
            ("TCP X", "TCP Y", "RZ", "Marker width", "Marker height")
        ):
            label = QLabel()
            label.setStyleSheet(LABEL_STYLE)
            value = QLabel("—")
            value.setAlignment(Qt.AlignmentFlag.AlignRight)
            reference_measurement_layout.addWidget(label, row, 0)
            reference_measurement_layout.addWidget(value, row, 1)
            self._reference_values[key] = (label, value)
        controls_layout.addWidget(self._reference_box)

        self._threshold_box = QGroupBox()
        self._threshold_box.setStyleSheet(GROUP_STYLE)
        threshold_layout = QGridLayout(self._threshold_box)
        self._thresholds = {}
        threshold_specs = (
            ("dX", 10, "mm"), ("dY", 10, "mm"), ("dRZ", 10, "deg"),
            ("dW", 5, "mm"), ("dH", 5, "mm"),
        )
        for row, (name, initial, unit) in enumerate(threshold_specs):
            label = QLabel(name)
            label.setStyleSheet(LABEL_STYLE)
            slider = QSlider(Qt.Orientation.Horizontal)
            slider.setRange(1, 50)
            slider.setValue(initial)
            value = QLabel()
            value.setMinimumWidth(70)
            value.setAlignment(Qt.AlignmentFlag.AlignRight)
            slider.valueChanged.connect(self._on_threshold_changed)
            threshold_layout.addWidget(label, row, 0)
            threshold_layout.addWidget(slider, row, 1)
            threshold_layout.addWidget(value, row, 2)
            self._thresholds[name] = (slider, value, unit)
        controls_layout.addWidget(self._threshold_box)

        reference_row = QHBoxLayout()
        self._sample_count = KeyboardSpinBox()
        self._sample_count.setRange(1, 200)
        self._sample_count.setValue(30)
        self._capture = QPushButton()
        self._capture.setStyleSheet(ACTION_BTN_STYLE)
        self._capture.setCursor(Qt.CursorShape.PointingHandCursor)
        self._capture.clicked.connect(self._on_capture_reference)
        reference_row.addWidget(self._sample_count)
        reference_row.addWidget(self._capture, stretch=1)
        controls_layout.addLayout(reference_row)

        self._reference_progress = QLabel()
        self._misalignment = QLabel()
        self._misalignment.setWordWrap(True)
        controls_layout.addWidget(self._reference_progress)
        controls_layout.addWidget(self._misalignment)
        controls_layout.addStretch(1)
        splitter.insertWidget(0, controls)
        splitter.setStretchFactor(0, 2)
        splitter.setStretchFactor(1, 3)
        alignment_layout.addWidget(splitter)
        self._tabs.addTab(alignment_page, "")
        self._tabs.addTab(self._build_settings_tab(), "")
        root.addWidget(self._tabs)
        self._on_threshold_changed()
        self.retranslateUi()

    def threshold_values(self) -> tuple[float, float, float, float, float]:
        return tuple(self._thresholds[name][0].value() / 10.0 for name in ("dX", "dY", "dRZ", "dW", "dH"))

    def set_settings(self, settings: ShaftAlignmentSettings) -> None:
        self._loaded_settings = settings
        for name, widget in self._settings_fields.items():
            value = getattr(settings, name)
            if name in ("calibration_pose", "capture_pose"):
                widget.setText(", ".join(str(item) for item in value))
            elif isinstance(widget, QComboBox):
                widget.setCurrentText(str(value))
            elif isinstance(widget, QCheckBox):
                widget.setChecked(bool(value))
            elif isinstance(widget, QLineEdit):
                widget.setText(str(value))
            else:
                widget.setValue(value)
        for name, value in (
            ("dX", settings.misalignment_dx_threshold_mm),
            ("dY", settings.misalignment_dy_threshold_mm),
            ("dRZ", settings.misalignment_drz_threshold_deg),
            ("dW", settings.misalignment_dw_threshold_mm),
            ("dH", settings.misalignment_dh_threshold_mm),
        ):
            self._thresholds[name][0].setValue(round(value * 10.0))
        self._sample_count.setValue(settings.reference_capture_samples)
        self._settings_status.clear()

    def settings_values(self) -> ShaftAlignmentSettings:
        values = {}
        for name, widget in self._settings_fields.items():
            if name in ("calibration_pose", "capture_pose"):
                values[name] = tuple(float(item.strip()) for item in widget.text().split(","))
            elif isinstance(widget, QComboBox):
                values[name] = widget.currentText()
            elif isinstance(widget, QCheckBox):
                values[name] = widget.isChecked()
            elif isinstance(widget, QLineEdit):
                values[name] = widget.text().strip()
            else:
                values[name] = widget.value()
        return replace(self._loaded_settings, **values)

    def set_persisted_settings(self, settings: ShaftAlignmentSettings) -> None:
        """Refresh hidden runtime state without disturbing editable controls."""
        self._loaded_settings = settings

    def set_snapshot(self, snapshot: AlignmentSnapshot) -> None:
        self._camera.set_frame(
            snapshot.frame,
            snapshot.marker_corners_normalized,
            snapshot.reference_marker_corners_normalized,
            snapshot.point_of_interest_normalized,
            snapshot.misaligned,
            snapshot.detection_region_normalized,
            (
                (-snapshot.dx_mm, -snapshot.dy_mm, -snapshot.drz_deg)
                if snapshot.dx_mm is not None
                and snapshot.dy_mm is not None
                and snapshot.drz_deg is not None
                else None
            ),
        )
        self._set_measurement("TCP X", snapshot.tcp_x_mm, "mm")
        self._set_measurement("TCP Y", snapshot.tcp_y_mm, "mm")
        self._set_measurement("RZ", snapshot.orientation_deg, "deg")
        self._set_measurement("Marker width", snapshot.marker_width_mm, "mm")
        self._set_measurement("Marker height", snapshot.marker_height_mm, "mm")
        self._set_reference_measurement("TCP X", snapshot.reference_tcp_x_mm, "mm")
        self._set_reference_measurement("TCP Y", snapshot.reference_tcp_y_mm, "mm")
        self._set_reference_measurement("RZ", snapshot.reference_orientation_deg, "deg")
        self._set_reference_measurement(
            "Marker width", snapshot.reference_marker_width_mm, "mm"
        )
        self._set_reference_measurement(
            "Marker height", snapshot.reference_marker_height_mm, "mm"
        )
        if self._continuous_mode:
            if snapshot.configuration_warning:
                status_color = ERROR_COLOR
                status_text = self.tr(
                    "Detection region is not defined for work area '{area}'. "
                    "Configure it in Work Area Settings."
                ).format(area=self._loaded_settings.active_work_area)
            elif snapshot.reference_available and snapshot.dx_mm is not None:
                status_color = ERROR_COLOR if snapshot.misaligned else _OK_COLOR
                status_text = (
                    self.tr("MISALIGNMENT DETECTED")
                    if snapshot.misaligned else self.tr("ALIGNMENT OK")
                )
            else:
                status_color = TEXT_COLOR
                status_text = snapshot.message
            self._status.setText(status_text)
            self._status.setStyleSheet(f"color: {status_color}; font-size: 14pt; font-weight: bold;")
        if snapshot.reference_capturing:
            self._reference_progress.setText(
                self.tr("Capturing reference: {current}/{required}").format(
                    current=snapshot.reference_samples,
                    required=snapshot.reference_samples_required,
                )
            )
        elif snapshot.reference_available:
            self._reference_progress.setText(self.tr("Reference captured"))
        else:
            self._reference_progress.setText(self.tr("Reference not captured"))
        if snapshot.dx_mm is None:
            self._misalignment.setText(self.tr("Capture a reference to report misalignment."))
        else:
            exceeded = ", ".join(snapshot.exceeded_limits) or self.tr("none")
            self._misalignment.setText(
                f"dX {snapshot.dx_mm:+.3f} mm   dY {snapshot.dy_mm:+.3f} mm   "
                f"dRZ {snapshot.drz_deg:+.2f} deg\n"
                f"dW {snapshot.dw_mm:+.3f} mm   dH {snapshot.dh_mm:+.3f} mm\n"
                f"{self.tr('Exceeded')}: {exceeded}"
            )

    def set_error(self, message: str) -> None:
        self._status.setText(message)
        self._status.setStyleSheet(f"color: {ERROR_COLOR}; font-size: 12pt; font-weight: bold;")

    def retranslateUi(self) -> None:
        labels = {
            "TCP X": self.tr("TCP X"), "TCP Y": self.tr("TCP Y"), "RZ": self.tr("RZ"),
            "Marker width": self.tr("Marker width"), "Marker height": self.tr("Marker height"),
        }
        for key, text in labels.items():
            self._measurement_values[key][0].setText(text)
            self._reference_values[key][0].setText(text)
        self._measurement_box.setTitle(self.tr("Current measurement"))
        self._reference_box.setTitle(self.tr("Saved reference"))
        self._threshold_box.setTitle(self.tr("Misalignment thresholds"))
        self._capture.setText(self.tr("Capture reference"))
        self._sample_count.setSuffix(self.tr(" samples"))
        self._mode_label.setText(self.tr("Check mode"))
        self._mode.setItemText(0, self.tr("Continuous"))
        self._mode.setItemText(1, self.tr("Check once"))
        self._check_alignment.setText(self.tr("Check alignment"))
        self._tabs.setTabText(0, self.tr("Alignment"))
        self._tabs.setTabText(1, self.tr("Settings"))
        self._save_settings.setText(self.tr("Save settings"))
        for name, label in self._settings_labels.items():
            label.setText(self.tr(self._setting_label_text(name)))

    def clean_up(self) -> None:
        pass

    def show_settings_saved(self) -> None:
        self._settings_status.setText(self.tr("Settings saved and applied."))
        self._settings_status.setStyleSheet(f"color: {_OK_COLOR}; font-weight: bold;")

    def set_settings_error(self, message: str) -> None:
        self._settings_status.setText(message)
        self._settings_status.setStyleSheet(f"color: {ERROR_COLOR}; font-weight: bold;")

    def show_alignment_check(self, aligned: bool) -> None:
        self._status.setText(
            self.tr("ALIGNMENT OK") if aligned else self.tr("ALIGNMENT FAILED")
        )
        color = _OK_COLOR if aligned else ERROR_COLOR
        self._status.setStyleSheet(f"color: {color}; font-size: 14pt; font-weight: bold;")

    def _build_settings_tab(self) -> QWidget:
        scroll = QScrollArea()
        scroll.setWidgetResizable(True)
        content = QWidget()
        form = QFormLayout(content)
        form.setContentsMargins(18, 18, 18, 18)
        form.setSpacing(10)
        self._settings_fields = {}
        self._settings_labels = {}

        integer_specs = {
            "marker_id": (0, 999), "base_region_width_px": (1, 10000),
            "base_region_height_px": (1, 10000), "tracking_region_padding_px": (0, 2000),
            "tracking_region_minimum_width_px": (1, 10000),
            "tracking_region_minimum_height_px": (1, 10000),
            "tracking_recovery_expansion_px": (0, 2000),
            "marker_misses_before_region_fallback": (1, 1000),
            "detections_before_tracking": (1, 1000), "acquisition_misses_before_reset": (1, 1000),
            "stability_required_samples": (1, 1000), "stability_misses_before_reset": (1, 1000),
            "reference_capture_samples": (1, 200),
            "alignment_check_samples": (1, 200),
        }
        double_specs = {
            "marker_size_mm": (0.01, 1000.0, 3), "minimum_area_px2": (0.0, 10000000.0, 1),
            "point_of_interest_x_offset_mm": (-1000.0, 1000.0, 3),
            "point_of_interest_y_offset_mm": (-1000.0, 1000.0, 3),
            "tracking_position_filter_alpha": (0.01, 1.0, 2),
            "tracking_prediction_gain": (0.0, 1.0, 2),
            "tracking_maximum_center_jump_px": (0.01, 10000.0, 2),
            "tracking_maximum_area_ratio_change": (1.01, 100.0, 2),
            "stability_maximum_center_spread_px": (0.0, 1000.0, 2),
            "stability_maximum_orientation_spread_deg": (0.0, 180.0, 2),
            "misalignment_dx_threshold_mm": (0.1, 5.0, 1),
            "misalignment_dy_threshold_mm": (0.1, 5.0, 1),
            "misalignment_drz_threshold_deg": (0.1, 5.0, 1),
            "misalignment_dw_threshold_mm": (0.1, 5.0, 1),
            "misalignment_dh_threshold_mm": (0.1, 5.0, 1),
            "detection_interval_s": (0.0, 10.0, 3),
        }
        persisted_state_fields = {
            "reference_tcp_x_mm", "reference_tcp_y_mm", "reference_orientation_deg",
            "reference_marker_width_mm", "reference_marker_height_mm",
            "reference_marker_corners_normalized",
            "reference_point_of_interest_normalized",
        }
        ordered_names = tuple(
            name for name in ShaftAlignmentSettings.__dataclass_fields__
            if name not in persisted_state_fields
        )
        for name in ordered_names:
            if name in integer_specs:
                widget = KeyboardSpinBox()
                widget.setRange(*integer_specs[name])
            elif name in double_specs:
                widget = KeyboardDoubleSpinBox()
                minimum, maximum, decimals = double_specs[name]
                widget.setRange(minimum, maximum)
                widget.setDecimals(decimals)
            elif name == "raw_mode":
                widget = QCheckBox()
            elif name == "orientation_strategy":
                widget = QComboBox()
                widget.addItems(["compare", "solve_pnp", "corner_edge"])
            elif name == "orientation_primary_strategy":
                widget = QComboBox()
                widget.addItems(["corner_edge", "solve_pnp"])
            else:
                widget = KeyboardLineEdit()
            label = QLabel()
            label.setStyleSheet(LABEL_STYLE)
            self._settings_fields[name] = widget
            self._settings_labels[name] = label
            form.addRow(label, widget)
        self._save_settings = QPushButton()
        self._save_settings.setCursor(Qt.CursorShape.PointingHandCursor)
        self._save_settings.setStyleSheet(SAVE_BUTTON_STYLE)
        self._save_settings.clicked.connect(self._on_save_settings)
        form.addRow(self._save_settings)
        self._settings_status = QLabel()
        self._settings_status.setWordWrap(True)
        form.addRow(self._settings_status)
        scroll.setWidget(content)
        return scroll

    @staticmethod
    def _setting_label_text(name: str) -> str:
        return name.replace("_", " ").title()

    def _set_measurement(self, key: str, value: float | None, unit: str) -> None:
        self._measurement_values[key][1].setText("—" if value is None else f"{value:+.3f} {unit}")

    def _set_reference_measurement(
        self, key: str, value: float | None, unit: str
    ) -> None:
        self._reference_values[key][1].setText(
            "—" if value is None else f"{value:+.3f} {unit}"
        )

    def _on_threshold_changed(self, _value: int = 0) -> None:
        for slider, value, unit in self._thresholds.values():
            value.setText(f"{slider.value() / 10.0:.1f} {unit}")
        if hasattr(self, "thresholds_changed"):
            self.thresholds_changed.emit(*self.threshold_values())

    def _on_capture_reference(self) -> None:
        self.capture_reference_requested.emit(self._sample_count.value())

    def _on_save_settings(self) -> None:
        try:
            settings = self.settings_values()
            settings.validate()
        except (TypeError, ValueError) as exc:
            self.set_settings_error(str(exc))
            return
        self.save_settings_requested.emit(settings)

    def _on_mode_changed(self, _index: int) -> None:
        self._continuous_mode = self._mode.currentData() == "continuous"
        self._check_alignment.setVisible(not self._continuous_mode)
        if not self._continuous_mode:
            self._status.setText(self.tr("Press Check alignment for a single verdict."))
            self._status.setStyleSheet(f"color: {TEXT_COLOR}; font-size: 12pt; font-weight: bold;")

    def _on_check_alignment(self) -> None:
        self.check_alignment_requested.emit()
