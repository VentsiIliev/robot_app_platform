from __future__ import annotations

from PyQt6.QtCore import QEvent, QPointF, QRectF, Qt, QTimer, pyqtSignal
from PyQt6.QtGui import QColor, QPainter, QPen, QPolygonF
from PyQt6.QtWidgets import QHBoxLayout, QLabel, QPushButton, QVBoxLayout, QWidget

from pl_gui.settings.settings_view.styles import (
    ACTION_BTN_STYLE,
    BG_COLOR,
    BORDER,
    ERROR_COLOR,
    GHOST_BTN_STYLE,
    LABEL_STYLE,
    PRIMARY,
    TEXT_COLOR,
    TEXT_ON_PRIMARY,
)


class _PlateCanvas(QWidget):
    placement_held = pyqtSignal(int)

    def __init__(self, parent=None) -> None:
        super().__init__(parent)
        self._state: dict[str, object] = {}
        self._rects: dict[int, QRectF] = {}
        self._pressed_id: int | None = None
        self._selected_id: int | None = None
        self._hold_timer = QTimer(self)
        self._hold_timer.setSingleShot(True)
        self._hold_timer.setInterval(650)
        self._hold_timer.timeout.connect(self._emit_held)
        self.setMinimumSize(420, 300)

    def set_state(self, state: dict[str, object]) -> None:
        self._state = dict(state or {})
        ids = {int(item["placement_id"]) for item in self._state.get("placements", [])}
        if self._selected_id not in ids:
            self._selected_id = None
        self.update()

    def clear_selection(self) -> None:
        self._selected_id = None
        self.update()

    def paintEvent(self, _event) -> None:
        painter = QPainter(self)
        painter.setRenderHint(QPainter.RenderHint.Antialiasing)
        painter.fillRect(self.rect(), QColor(BG_COLOR))
        width = float(self._state.get("width_mm", 0.0) or 0.0)
        height = float(self._state.get("height_mm", 0.0) or 0.0)
        self._rects.clear()
        if width <= 0.0 or height <= 0.0:
            plate = QRectF(18, 18, max(1, self.width() - 36), max(1, self.height() - 36))
            painter.setPen(QPen(QColor(BORDER), 3))
            painter.setBrush(QColor(TEXT_ON_PRIMARY))
            painter.drawRoundedRect(plate, 10, 10)
            painter.setPen(QColor(TEXT_COLOR))
            painter.drawText(plate, Qt.AlignmentFlag.AlignCenter, self.tr("Tray is not configured"))
            return
        plate = self._scaled_plate_rect(width, height)
        painter.setPen(QPen(QColor(BORDER), 3))
        painter.setBrush(QColor(TEXT_ON_PRIMARY))
        painter.drawRoundedRect(plate, 10, 10)
        for item in self._state.get("placements", []):
            self._draw_placement(painter, plate, width, height, item, pending=False)
        pending = self._state.get("pending")
        if isinstance(pending, dict):
            self._draw_placement(painter, plate, width, height, pending, pending=True)

    def _scaled_plate_rect(self, width_mm: float, height_mm: float) -> QRectF:
        available_width = max(1.0, float(self.width() - 36))
        available_height = max(1.0, float(self.height() - 36))
        scale = min(available_width / width_mm, available_height / height_mm)
        plate_width = width_mm * scale
        plate_height = height_mm * scale
        return QRectF(
            (self.width() - plate_width) / 2.0,
            (self.height() - plate_height) / 2.0,
            plate_width,
            plate_height,
        )

    def _draw_placement(self, painter, plate, width, height, item, *, pending: bool) -> None:
        placement_id = int(item["placement_id"])
        rect = QRectF(
            plate.left() + float(item["left_mm"]) / width * plate.width(),
            plate.bottom() - (float(item["bottom_mm"]) + float(item["height_mm"])) / height * plate.height(),
            float(item["width_mm"]) / width * plate.width(),
            float(item["height_mm"]) / height * plate.height(),
        ).adjusted(2, 2, -2, -2)
        if not pending:
            self._rects[placement_id] = rect
        selected = placement_id == self._selected_id
        painter.setPen(QPen(QColor(ERROR_COLOR if selected else PRIMARY), 3 if selected else 2))
        fill = QColor(PRIMARY)
        if pending:
            fill.setAlpha(55)
        painter.setBrush(fill)
        outlines = item.get("outlines_mm") or ()
        if outlines:
            for outline in outlines:
                polygon = QPolygonF([
                    QPointF(
                        plate.left() + (float(item["left_mm"]) + float(x)) / width * plate.width(),
                        plate.bottom() - (float(item["bottom_mm"]) + float(y)) / height * plate.height(),
                    )
                    for x, y in outline
                ])
                if len(polygon) >= 3:
                    painter.drawPolygon(polygon)
                elif len(polygon) == 2:
                    painter.drawPolyline(polygon)
        else:
            painter.drawRoundedRect(rect, 5, 5)
        painter.setPen(QColor(TEXT_COLOR if pending else TEXT_ON_PRIMARY))
        painter.drawText(rect, Qt.AlignmentFlag.AlignCenter, str(placement_id))

    def mousePressEvent(self, event) -> None:
        if event.button() == Qt.MouseButton.LeftButton:
            self._pressed_id = next(
                (placement_id for placement_id, rect in self._rects.items() if rect.contains(event.position())),
                None,
            )
            if self._pressed_id is not None:
                self._hold_timer.start()
        super().mousePressEvent(event)

    def mouseReleaseEvent(self, event) -> None:
        self._hold_timer.stop()
        self._pressed_id = None
        super().mouseReleaseEvent(event)

    def _emit_held(self) -> None:
        if self._pressed_id is None:
            return
        self._selected_id = self._pressed_id
        self.update()
        self.placement_held.emit(self._pressed_id)


class PaintPlateLayout(QWidget):
    new_tray_requested = pyqtSignal()
    remove_requested = pyqtSignal(int)

    def __init__(self, parent=None) -> None:
        super().__init__(parent)
        self._selected_id: int | None = None
        self.setStyleSheet(f"background-color: {BG_COLOR};")
        layout = QVBoxLayout(self)
        layout.setContentsMargins(0, 0, 0, 0)
        header = QHBoxLayout()
        self._title = QLabel()
        self._title.setStyleSheet(LABEL_STYLE)
        self._hint = QLabel()
        self._hint.setStyleSheet(LABEL_STYLE)
        self._new_tray = QPushButton()
        self._new_tray.setStyleSheet(ACTION_BTN_STYLE)
        self._new_tray.setCursor(Qt.CursorShape.PointingHandCursor)
        self._new_tray.clicked.connect(self._on_new_tray)
        header.addWidget(self._title)
        header.addStretch()
        header.addWidget(self._new_tray)
        layout.addLayout(header)
        self._canvas = _PlateCanvas()
        self._canvas.placement_held.connect(self._on_placement_held)
        layout.addWidget(self._canvas, 1)
        footer = QHBoxLayout()
        footer.addWidget(self._hint)
        footer.addStretch()
        self._remove = QPushButton()
        self._remove.setStyleSheet(GHOST_BTN_STYLE)
        self._remove.setCursor(Qt.CursorShape.PointingHandCursor)
        self._remove.clicked.connect(self._on_remove)
        self._remove.hide()
        footer.addWidget(self._remove)
        layout.addLayout(footer)
        self.retranslateUi()

    def set_state(self, state: dict[str, object]) -> None:
        self._canvas.set_state(state)

    def set_editable(self, editable: bool) -> None:
        self._new_tray.setEnabled(editable)
        self._remove.setEnabled(editable)

    def clear_selection(self) -> None:
        self._selected_id = None
        self._remove.hide()
        self._canvas.clear_selection()

    def _on_new_tray(self) -> None:
        self.new_tray_requested.emit()

    def _on_placement_held(self, placement_id: int) -> None:
        self._selected_id = placement_id
        self._remove.show()

    def _on_remove(self) -> None:
        if self._selected_id is not None:
            self.remove_requested.emit(self._selected_id)

    def retranslateUi(self) -> None:
        self._title.setText(self.tr("Manual Dryer Tray"))
        self._hint.setText(self.tr("Press and hold a workpiece to select it"))
        self._new_tray.setText(self.tr("New Tray"))
        self._remove.setText(self.tr("Remove"))

    def changeEvent(self, event: QEvent) -> None:
        if event.type() == QEvent.Type.LanguageChange:
            self.retranslateUi()
        super().changeEvent(event)
