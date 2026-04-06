from __future__ import annotations

import cv2

from PyQt6.QtCore import Qt
from PyQt6.QtGui import QImage, QPixmap
from PyQt6.QtWidgets import QLabel, QVBoxLayout

from src.applications.base.app_dialog import AppDialog
from src.applications.calibration.service.i_calibration_service import RobotCalibrationPreview


class RobotCalibrationPreviewDialog(AppDialog):
    def __init__(self, preview: RobotCalibrationPreview, parent=None):
        super().__init__("Robot Calibration Preview", min_width=980, parent=parent)
        self._preview = preview
        self.setMinimumHeight(760)
        self._build_ui()

    def _build_ui(self) -> None:
        layout = QVBoxLayout(self)
        layout.setContentsMargins(16, 16, 16, 12)
        layout.setSpacing(10)

        summary = QLabel(self._summary_text())
        summary.setWordWrap(True)
        summary.setStyleSheet("font-size: 10pt; font-weight: 600;")
        layout.addWidget(summary)

        image_label = QLabel()
        image_label.setAlignment(Qt.AlignmentFlag.AlignCenter)
        image_label.setStyleSheet(
            "background: #101418; border: 1px solid #4a4f55; border-radius: 8px; padding: 8px;"
        )
        pixmap = self._pixmap_from_frame(self._preview.frame)
        if pixmap is not None:
            image_label.setPixmap(
                pixmap.scaled(
                    920,
                    620,
                    Qt.AspectRatioMode.KeepAspectRatio,
                    Qt.TransformationMode.SmoothTransformation,
                )
            )
        else:
            image_label.setText("No preview image available")
        layout.addWidget(image_label, stretch=1)

        legend = QLabel(
            "Green markers are selected calibration targets. Grey markers are detected candidates. "
            "Yellow outline is the selected hull. Green lines show the planned target grid."
        )
        legend.setWordWrap(True)
        legend.setStyleSheet("font-size: 9pt; font-weight: 500; color: #444;")
        layout.addWidget(legend)

        layout.addWidget(
            self._build_button_row(
                ok_label="Proceed" if self._preview.ok else "Close",
                cancel_label="Cancel",
            )
        )

    def accept(self) -> None:
        if self._preview.ok:
            super().accept()
            return
        super().reject()

    def _summary_text(self) -> str:
        available_count = len(self._preview.available_ids or [])
        selected_count = len(self._preview.selected_ids or [])
        min_targets = int(self._preview.min_targets or 0)
        max_targets = int(self._preview.max_targets or 0)
        status = "Ready to calibrate." if self._preview.ok else "Preview is not ready for calibration."
        return (
            f"{status}\n"
            f"{self._preview.message}\n"
            f"Detected candidates: {available_count} | Selected targets: {selected_count} | "
            f"Target range: {min_targets}..{max_targets}"
        )

    @staticmethod
    def _pixmap_from_frame(frame) -> QPixmap | None:
        if frame is None:
            return None
        rgb = cv2.cvtColor(frame, cv2.COLOR_BGR2RGB)
        height, width, channels = rgb.shape
        image = QImage(rgb.data, width, height, channels * width, QImage.Format.Format_RGB888)
        return QPixmap.fromImage(image.copy())
