from __future__ import annotations

from typing import Callable

from PyQt6.QtCore import Qt
from PyQt6.QtWidgets import (
    QDialog,
    QDoubleSpinBox,
    QFormLayout,
    QHBoxLayout,
    QLabel,
    QPushButton,
    QVBoxLayout,
)

from src.robot_systems.paint.domain.manual_dxf_alignment import (
    apply_manual_similarity_transform_to_raw,
)


class ManualDxfAlignmentDialog(QDialog):
    """Paint-only dialog for manual image-space DXF alignment refinement."""

    def __init__(
        self,
        *,
        base_raw: dict,
        preview_callback: Callable[[dict], None],
        parent=None,
    ) -> None:
        super().__init__(parent)
        self._base_raw = dict(base_raw or {})
        self._preview_callback = preview_callback
        self._result_raw = dict(self._base_raw)

        self.setWindowTitle("Adjust DXF Alignment")
        self.resize(460, 260)

        self._tx = self._build_spinbox(-5000.0, 5000.0, 0.0, 1.0, 2)
        self._ty = self._build_spinbox(-5000.0, 5000.0, 0.0, 1.0, 2)
        self._rotation = self._build_spinbox(-180.0, 180.0, 0.0, 0.1, 3)
        self._scale = self._build_spinbox(0.5, 1.5, 1.0, 0.001, 4)

        self._build_ui()
        self._connect_signals()
        self._emit_preview()

    @staticmethod
    def _build_spinbox(
        minimum: float,
        maximum: float,
        value: float,
        step: float,
        decimals: int,
    ) -> QDoubleSpinBox:
        spin = QDoubleSpinBox()
        spin.setRange(minimum, maximum)
        spin.setDecimals(decimals)
        spin.setSingleStep(step)
        spin.setValue(value)
        spin.setMinimumHeight(36)
        return spin

    def _build_ui(self) -> None:
        root = QVBoxLayout(self)
        root.setContentsMargins(16, 16, 16, 16)
        root.setSpacing(12)

        note = QLabel(
            "Fine-tune the auto-aligned DXF in image space. "
            "Translation is in pixels; positive rotation is counterclockwise on screen; scale is uniform."
        )
        note.setWordWrap(True)
        root.addWidget(note)

        form = QFormLayout()
        form.addRow("Translate X (px)", self._tx)
        form.addRow("Translate Y (px)", self._ty)
        form.addRow("Rotation (deg, CCW)", self._rotation)
        form.addRow("Scale", self._scale)
        root.addLayout(form)

        buttons = QHBoxLayout()
        buttons.addStretch(1)

        reset_btn = QPushButton("Reset")
        reset_btn.setCursor(Qt.CursorShape.PointingHandCursor)
        reset_btn.clicked.connect(self._reset)
        buttons.addWidget(reset_btn)

        cancel_btn = QPushButton("Cancel")
        cancel_btn.setCursor(Qt.CursorShape.PointingHandCursor)
        cancel_btn.clicked.connect(self.reject)
        buttons.addWidget(cancel_btn)

        apply_btn = QPushButton("Apply")
        apply_btn.setCursor(Qt.CursorShape.PointingHandCursor)
        apply_btn.clicked.connect(self._accept_with_result)
        buttons.addWidget(apply_btn)

        root.addLayout(buttons)

    def _connect_signals(self) -> None:
        for widget in (self._tx, self._ty, self._rotation, self._scale):
            widget.valueChanged.connect(self._emit_preview)

    def _reset(self) -> None:
        self._tx.setValue(0.0)
        self._ty.setValue(0.0)
        self._rotation.setValue(0.0)
        self._scale.setValue(1.0)

    def _current_raw(self) -> dict:
        return apply_manual_similarity_transform_to_raw(
            self._base_raw,
            rotation_deg=-float(self._rotation.value()),
            scale=float(self._scale.value()),
            translation_x_px=float(self._tx.value()),
            translation_y_px=float(self._ty.value()),
        )

    def _emit_preview(self) -> None:
        self._result_raw = self._current_raw()
        self._preview_callback(self._result_raw)

    def _accept_with_result(self) -> None:
        self._result_raw = self._current_raw()
        self.accept()

    def result_raw(self) -> dict:
        return dict(self._result_raw)
