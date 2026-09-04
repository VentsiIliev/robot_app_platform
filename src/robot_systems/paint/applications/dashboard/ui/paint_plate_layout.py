from __future__ import annotations

from datetime import datetime

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
        self._selected_id: int | None = None
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
        display_width, display_height = (
            (height_mm, width_mm) if height_mm > width_mm else (width_mm, height_mm)
        )
        available_width = max(1.0, float(self.width() - 36))
        available_height = max(1.0, float(self.height() - 36))
        scale = min(available_width / display_width, available_height / display_height)
        plate_width = display_width * scale
        plate_height = display_height * scale
        return QRectF(
            (self.width() - plate_width) / 2.0,
            (self.height() - plate_height) / 2.0,
            plate_width,
            plate_height,
        )

    def _draw_placement(self, painter, plate, width, height, item, *, pending: bool) -> None:
        placement_id = int(item["placement_id"])
        left = float(item["left_mm"])
        bottom = float(item["bottom_mm"])
        item_width = float(item["width_mm"])
        item_height = float(item["height_mm"])
        corners = (
            self._to_canvas_point(left, bottom, width, height, plate),
            self._to_canvas_point(left + item_width, bottom + item_height, width, height, plate),
        )
        rect = QRectF(corners[0], corners[1]).normalized().adjusted(2, 2, -2, -2)
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
                    self._to_canvas_point(
                        left + float(x),
                        bottom + float(y),
                        width,
                        height,
                        plate,
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

    @staticmethod
    def _to_canvas_point(
        x_mm: float,
        y_mm: float,
        tray_width_mm: float,
        tray_height_mm: float,
        plate: QRectF,
    ) -> QPointF:
        if tray_height_mm > tray_width_mm:
            display_x = y_mm
            display_y = tray_width_mm - x_mm
            display_width = tray_height_mm
            display_height = tray_width_mm
        else:
            display_x = x_mm
            display_y = y_mm
            display_width = tray_width_mm
            display_height = tray_height_mm
        return QPointF(
            plate.left() + display_x / display_width * plate.width(),
            plate.bottom() - display_y / display_height * plate.height(),
        )

    def mousePressEvent(self, event) -> None:
        if event.button() == Qt.MouseButton.LeftButton:
            placement_id = next(
                (placement_id for placement_id, rect in self._rects.items() if rect.contains(event.position())),
                None,
            )
            if placement_id is not None:
                self._selected_id = placement_id
                self.update()
                self.placement_held.emit(placement_id)
        super().mousePressEvent(event)


class PaintPlateLayout(QWidget):
    new_tray_requested = pyqtSignal()
    remove_requested = pyqtSignal(int)

    def __init__(self, parent=None) -> None:
        super().__init__(parent)
        self._selected_id: int | None = None
        self._state: dict[str, object] = {}
        self._drying_timer = QTimer(self)
        self._drying_timer.setInterval(1000)
        self._drying_timer.timeout.connect(self._render_selection_metadata)
        self.setStyleSheet(f"background-color: {BG_COLOR};")
        layout = QVBoxLayout(self)
        layout.setContentsMargins(0, 0, 0, 0)
        header = QHBoxLayout()
        self._hint = QLabel()
        self._hint.setStyleSheet(LABEL_STYLE)
        self._new_tray = QPushButton()
        self._new_tray.setStyleSheet(ACTION_BTN_STYLE)
        self._new_tray.setCursor(Qt.CursorShape.PointingHandCursor)
        self._new_tray.clicked.connect(self._on_new_tray)
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
        self._state = dict(state or {})
        self._canvas.set_state(state)
        placement_ids = {
            int(item["placement_id"])
            for item in self._state.get("placements", [])
        }
        if self._selected_id not in placement_ids:
            self.clear_selection()
        else:
            self._render_selection_metadata()

    def set_editable(self, editable: bool) -> None:
        self._new_tray.setEnabled(editable)
        self._remove.setEnabled(editable)

    def set_new_tray_button_visible(self, visible: bool) -> None:
        self._new_tray.setVisible(bool(visible))

    def clear_selection(self) -> None:
        self._selected_id = None
        self._drying_timer.stop()
        self._remove.hide()
        self._canvas.clear_selection()
        self._hint.setText(self.tr("Press a workpiece to select it"))

    def _on_new_tray(self) -> None:
        self.new_tray_requested.emit()

    def _on_placement_held(self, placement_id: int) -> None:
        self._selected_id = placement_id
        self._remove.show()
        self._render_selection_metadata()
        self._drying_timer.start()

    def _render_selection_metadata(self) -> None:
        placement = next(
            (
                item
                for item in self._state.get("placements", [])
                if int(item["placement_id"]) == self._selected_id
            ),
            None,
        )
        if placement is None:
            return
        raw_timestamp = str(placement.get("painted_at", "") or "")
        try:
            painted_at = datetime.fromisoformat(raw_timestamp)
            if painted_at.tzinfo is None:
                painted_at = painted_at.astimezone()
            now = datetime.now().astimezone()
            elapsed_seconds = max(0, int((now - painted_at).total_seconds()))
            painted_time = painted_at.astimezone().strftime("%H:%M:%S")
        except (TypeError, ValueError):
            self._hint.setText(self.tr("Drying time is unavailable"))
            return
        self._hint.setText(
            f"{self.tr('Painted at')}: {painted_time}   •   "
            f"{self.tr('Drying for')}: {self._format_duration(elapsed_seconds)}   •   "
            f"{self.tr('Passes')}: {int(placement.get('paint_pass_count', 0) or 0)}"
        )

    @staticmethod
    def _format_duration(total_seconds: int) -> str:
        days, remainder = divmod(max(0, int(total_seconds)), 86400)
        hours, remainder = divmod(remainder, 3600)
        minutes, seconds = divmod(remainder, 60)
        if days:
            return f"{days}d {hours}h {minutes}m"
        if hours:
            return f"{hours}h {minutes}m {seconds}s"
        if minutes:
            return f"{minutes}m {seconds}s"
        return f"{seconds}s"

    def _on_remove(self) -> None:
        if self._selected_id is not None:
            self.remove_requested.emit(self._selected_id)

    def retranslateUi(self) -> None:
        if self._selected_id is None:
            self._hint.setText(self.tr("Press a workpiece to select it"))
        else:
            self._render_selection_metadata()
        self._new_tray.setText(self.tr("New Tray"))
        self._remove.setText(self.tr("Remove"))

    def changeEvent(self, event: QEvent) -> None:
        if event.type() == QEvent.Type.LanguageChange:
            self.retranslateUi()
        super().changeEvent(event)
