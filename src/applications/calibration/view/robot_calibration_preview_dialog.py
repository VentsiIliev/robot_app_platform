from __future__ import annotations

import cv2

from PyQt6.QtCore import Qt
from PyQt6.QtGui import QImage, QPixmap
from PyQt6.QtWidgets import QLabel, QTextEdit, QVBoxLayout

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

        details = QTextEdit()
        details.setReadOnly(True)
        details.setMaximumHeight(180)
        details.setStyleSheet(
            "background: #0f1317; color: #d7dde5; border: 1px solid #4a4f55; "
            "border-radius: 8px; padding: 8px; font-family: monospace; font-size: 9pt;"
        )
        details.setPlainText(self._details_text())
        layout.addWidget(details)

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
            "H = homography targets (green), R = residual targets (blue), V = validation targets (amber). "
            "U = known unreachable markers (red). D = detected candidates inside the active work area (grey). "
            "X = detected markers outside the active work area (dark grey). "
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
        report = self._preview.report or {}
        all_detected_count = int(report.get("all_detected_count", available_count))
        in_work_area_count = int(report.get("in_work_area_count", available_count))
        homography_count = len(report.get("homography_ids", []) or [])
        residual_count = len(report.get("residual_ids", []) or [])
        validation_count = len(report.get("validation_ids", []) or [])
        known_unreachable_count = len(report.get("known_unreachable_ids", []) or [])
        status = "Ready to calibrate." if self._preview.ok else "Preview is not ready for calibration."
        return (
            f"{status}\n"
            f"{self._preview.message}\n"
            f"All detected markers: {all_detected_count} | In active work area: {in_work_area_count} | "
            f"Selected targets: {selected_count} (H={homography_count}, R={residual_count}, V={validation_count}) | "
            f"Known unreachable: {known_unreachable_count}"
        )

    def _details_text(self) -> str:
        report = self._preview.report or {}
        homography_ids = [int(v) for v in (report.get("homography_ids") or [])]
        residual_ids = [int(v) for v in (report.get("residual_ids") or [])]
        validation_ids = [int(v) for v in (report.get("validation_ids") or [])]
        selected_ids = [int(v) for v in (report.get("selected_ids") or self._preview.selected_ids or [])]
        available_ids = [int(v) for v in (report.get("available_ids") or self._preview.available_ids or [])]
        all_detected_ids = [int(v) for v in (report.get("all_detected_ids") or [])]
        known_unreachable_ids = [int(v) for v in (report.get("known_unreachable_ids") or [])]

        def _fmt(label: str, ids: list[int]) -> str:
            ids_text = ", ".join(str(v) for v in ids) if ids else "-"
            return f"{label} ({len(ids)}): {ids_text}"

        return "\n".join(
            [
                _fmt("Homography", homography_ids),
                _fmt("Residual", residual_ids),
                _fmt("Validation", validation_ids),
                _fmt("Selected total", selected_ids),
                _fmt("In work area", available_ids),
                _fmt("Known unreachable", known_unreachable_ids),
                _fmt("All detected", all_detected_ids),
            ]
        )

    @staticmethod
    def _pixmap_from_frame(frame) -> QPixmap | None:
        if frame is None:
            return None
        rgb = cv2.cvtColor(frame, cv2.COLOR_BGR2RGB)
        height, width, channels = rgb.shape
        image = QImage(rgb.data, width, height, channels * width, QImage.Format.Format_RGB888)
        return QPixmap.fromImage(image.copy())
