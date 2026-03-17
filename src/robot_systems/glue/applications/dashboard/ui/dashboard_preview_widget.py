from __future__ import annotations

from enum import Enum

import cv2
import numpy as np
from PyQt6.QtCore import QEvent, QTimer, Qt
from PyQt6.QtGui import QImage, QPixmap
from PyQt6.QtWidgets import (
    QButtonGroup,
    QHBoxLayout,
    QLabel,
    QPushButton,
    QVBoxLayout,
    QWidget,
)

from pl_gui.dashboard.widgets.RobotTrajectoryWidget import (
    TrajectoryManager,
    draw_smooth_trail,
)
from pl_gui.settings.settings_view.styles import ACTION_BTN_STYLE, GHOST_BTN_STYLE


class PreviewDisplayMode(str, Enum):
    LIVE = "live"
    JOB_PROGRESS = "job_progress"


class DashboardPreviewWidget(QWidget):
    _PENDING_COLOR = (74, 196, 232)
    _DONE_COLOR = (88, 194, 122)
    _ACTIVE_RING_COLOR = (245, 245, 245)
    _ACTIVE_CORE_COLOR = (34, 42, 54)

    def __init__(self, image_width: int = 640, image_height: int = 360, fps_ms: int = 30, trail_length: int = 100):
        super().__init__()
        self.image_width = int(image_width)
        self.image_height = int(image_height)
        self._live_frame: np.ndarray | None = None
        self._progress_image: np.ndarray | None = None
        self._progress_segments: list[dict] = []
        self._progress_state: dict | None = None
        self._progress_robot_point: tuple[float, float] | None = None
        self._primary_mode = PreviewDisplayMode.LIVE
        self._inset_enabled = True
        self.drawing_enabled = False
        self.trajectory_manager = TrajectoryManager(trail_length=trail_length)

        self._build_ui()
        self._timer = QTimer(self)
        self._timer.timeout.connect(self._refresh_preview)
        self._timer.start(int(fps_ms))

    def _build_ui(self) -> None:
        root = QVBoxLayout(self)
        root.setContentsMargins(0, 0, 0, 0)
        root.setSpacing(6)

        controls = QHBoxLayout()
        controls.setContentsMargins(0, 0, 0, 0)
        controls.setSpacing(6)

        self._live_btn = QPushButton(self.tr("Live"))
        self._progress_btn = QPushButton(self.tr("Progress"))
        self._inset_btn = QPushButton(self.tr("Inset"))
        for btn in (self._live_btn, self._progress_btn, self._inset_btn):
            btn.setCheckable(True)
            btn.setStyleSheet(GHOST_BTN_STYLE)

        self._mode_group = QButtonGroup(self)
        self._mode_group.setExclusive(True)
        self._mode_group.addButton(self._live_btn)
        self._mode_group.addButton(self._progress_btn)

        self._live_btn.clicked.connect(lambda: self.set_primary_mode(PreviewDisplayMode.LIVE))
        self._progress_btn.clicked.connect(lambda: self.set_primary_mode(PreviewDisplayMode.JOB_PROGRESS))
        self._inset_btn.clicked.connect(self.set_inset_enabled)

        controls.addWidget(self._live_btn)
        controls.addWidget(self._progress_btn)
        controls.addWidget(self._inset_btn)
        controls.addStretch()

        self._image_label = QLabel()
        self._image_label.setFixedSize(self.image_width, self.image_height)
        self._image_label.setAlignment(Qt.AlignmentFlag.AlignCenter)

        root.addLayout(controls)
        root.addWidget(self._image_label, alignment=Qt.AlignmentFlag.AlignTop | Qt.AlignmentFlag.AlignLeft)

        self.setFixedSize(self.image_width + 8, self.image_height + 56)
        self._sync_controls()

    def set_image(self, message=None) -> None:
        self.set_live_frame(message)

    def set_live_frame(self, message=None) -> None:
        if message is None or not isinstance(message, dict) or "image" not in message:
            return
        frame = message.get("image")
        if frame is None:
            self._live_frame = None
            self.trajectory_manager.clear_trail()
            return
        try:
            self._live_frame = np.array(frame, copy=True)
        except Exception:
            self._live_frame = None
        self.trajectory_manager.clear_trail()

    def set_progress_snapshot(self, image, segments: list[dict]) -> None:
        self._progress_image = None if image is None else np.array(image, copy=True)
        self._progress_segments = list(segments)
        if self._primary_mode == PreviewDisplayMode.JOB_PROGRESS and self._progress_image is None:
            self._primary_mode = PreviewDisplayMode.LIVE
        self._sync_controls()

    def clear_progress_snapshot(self) -> None:
        self._progress_image = None
        self._progress_segments = []
        self._progress_state = None
        if self._primary_mode == PreviewDisplayMode.JOB_PROGRESS:
            self._primary_mode = PreviewDisplayMode.LIVE
        self._sync_controls()

    def set_progress_state(self, snapshot: dict | None) -> None:
        self._progress_state = dict(snapshot) if snapshot is not None else None

    def set_progress_robot_point(self, point) -> None:
        self._progress_robot_point = None if point is None else (float(point[0]), float(point[1]))

    def set_primary_mode(self, mode: PreviewDisplayMode | str) -> None:
        resolved = PreviewDisplayMode(mode)
        if resolved == PreviewDisplayMode.JOB_PROGRESS and self._progress_image is None:
            resolved = PreviewDisplayMode.LIVE
        self._primary_mode = resolved
        self._sync_controls()
        self._refresh_preview()

    def set_inset_enabled(self, enabled: bool) -> None:
        self._inset_enabled = bool(enabled)
        self._sync_controls()
        self._refresh_preview()

    def update_trajectory_point(self, message=None) -> None:
        if message is None:
            return
        x, y = message.get("x", 0), message.get("y", 0)
        self.trajectory_manager.update_position((int(x), int(y)))

    def break_trajectory(self) -> None:
        self.trajectory_manager.break_trajectory()

    def enable_drawing(self, _=None) -> None:
        self.drawing_enabled = True

    def disable_drawing(self, _=None) -> None:
        self.drawing_enabled = False
        self.trajectory_manager.clear_trail()

    def retranslateUi(self) -> None:
        self._live_btn.setText(self.tr("Live"))
        self._progress_btn.setText(self.tr("Progress"))
        self._inset_btn.setText(self.tr("Inset"))

    def changeEvent(self, event) -> None:
        if event.type() == QEvent.Type.LanguageChange:
            self.retranslateUi()
        super().changeEvent(event)

    def _sync_controls(self) -> None:
        self._live_btn.setChecked(self._primary_mode == PreviewDisplayMode.LIVE)
        self._progress_btn.setChecked(self._primary_mode == PreviewDisplayMode.JOB_PROGRESS)
        self._progress_btn.setEnabled(self._progress_image is not None)
        self._inset_btn.setChecked(self._inset_enabled)
        self._live_btn.setStyleSheet(ACTION_BTN_STYLE if self._live_btn.isChecked() else GHOST_BTN_STYLE)
        self._progress_btn.setStyleSheet(ACTION_BTN_STYLE if self._progress_btn.isChecked() else GHOST_BTN_STYLE)
        self._inset_btn.setStyleSheet(ACTION_BTN_STYLE if self._inset_btn.isChecked() else GHOST_BTN_STYLE)

    def _refresh_preview(self) -> None:
        canvas = self._compose_canvas()
        rgb_image = cv2.cvtColor(canvas, cv2.COLOR_BGR2RGB)
        h, w, ch = rgb_image.shape
        q_image = QImage(rgb_image.data, w, h, ch * w, QImage.Format.Format_RGB888)
        self._image_label.setPixmap(QPixmap.fromImage(q_image))

    def _compose_canvas(self) -> np.ndarray:
        primary = self._frame_for_mode(self._primary_mode)
        if primary is None:
            primary = np.zeros((self.image_height, self.image_width, 3), dtype=np.uint8)
        primary = cv2.resize(primary, (self.image_width, self.image_height))

        if not self._inset_enabled:
            return primary

        secondary_mode = (
            PreviewDisplayMode.JOB_PROGRESS
            if self._primary_mode == PreviewDisplayMode.LIVE else
            PreviewDisplayMode.LIVE
        )
        secondary = self._frame_for_mode(secondary_mode)
        if secondary is None:
            return primary

        inset_w = max(120, int(self.image_width * 0.28))
        inset_h = max(80, int(self.image_height * 0.28))
        inset = cv2.resize(secondary, (inset_w, inset_h))
        x = self.image_width - inset_w - 12
        y = 12
        shadow = primary.copy()
        cv2.rectangle(shadow, (x + 4, y + 6), (x + inset_w + 8, y + inset_h + 10), (0, 0, 0), thickness=-1)
        primary = cv2.addWeighted(shadow, 0.18, primary, 0.82, 0.0)
        cv2.rectangle(primary, (x - 3, y - 3), (x + inset_w + 3, y + inset_h + 3), (248, 248, 248), thickness=-1)
        cv2.rectangle(primary, (x - 3, y - 3), (x + inset_w + 3, y + inset_h + 3), (58, 66, 78), thickness=1)
        primary[y:y + inset_h, x:x + inset_w] = inset
        return primary

    def _frame_for_mode(self, mode: PreviewDisplayMode) -> np.ndarray | None:
        if mode == PreviewDisplayMode.LIVE:
            return self._build_live_frame()
        return self._build_progress_frame()

    def _build_live_frame(self) -> np.ndarray | None:
        if self._live_frame is None:
            return None
        frame = cv2.resize(np.array(self._live_frame, copy=True), (self.image_width, self.image_height))
        points = self.trajectory_manager.get_trajectory_copy()
        if self.drawing_enabled and points:
            try:
                draw_smooth_trail(frame, points)
            except Exception:
                pass
        return frame

    def _build_progress_frame(self) -> np.ndarray | None:
        if self._progress_image is None:
            return None
        frame = cv2.resize(np.array(self._progress_image, copy=True), (self.image_width, self.image_height))
        veil = np.full_like(frame, 18)
        frame = cv2.addWeighted(frame, 0.9, veil, 0.1, 0.0)
        scale_x = self.image_width / max(1, self._progress_image.shape[1])
        scale_y = self.image_height / max(1, self._progress_image.shape[0])

        completed_path_index = -1
        completed_point_index = 0
        if isinstance(self._progress_state, dict):
            dispensing = self._progress_state.get("dispensing") or {}
            completed_path_index = int(dispensing.get("current_path_index", -1))
            completed_point_index = int(dispensing.get("current_point_index", 0))

        for segment in self._progress_segments:
            points = [
                (int(x * scale_x), int(y * scale_y))
                for x, y in segment.get("points", [])
            ]
            if len(points) < 2:
                continue
            path_index = int(segment.get("path_index", -1))
            if path_index < completed_path_index:
                done_points = points
                pending_points = []
            elif path_index == completed_path_index:
                split_index = max(1, min(completed_point_index, len(points)))
                projected = self._projected_robot_point(scale_x, scale_y)
                if projected is not None:
                    nearest_index = self._nearest_forward_index(points, projected)
                    split_index = max(split_index, nearest_index)
                done_points = points[:split_index]
                pending_points = points[max(0, split_index - 1):]
            else:
                done_points = []
                pending_points = points

            self._draw_polyline(frame, pending_points, self._PENDING_COLOR, thickness=1, glow=False)
            self._draw_polyline(frame, done_points, self._DONE_COLOR, thickness=2, glow=True)
            if path_index == completed_path_index:
                projected = self._projected_robot_point(scale_x, scale_y)
                if projected is not None:
                    cv2.circle(frame, projected, 7, self._ACTIVE_RING_COLOR, thickness=2, lineType=cv2.LINE_AA)
                    cv2.circle(frame, projected, 3, self._ACTIVE_CORE_COLOR, thickness=-1, lineType=cv2.LINE_AA)
        return frame

    @staticmethod
    def _draw_polyline(
        frame: np.ndarray,
        points: list[tuple[int, int]],
        color: tuple[int, int, int],
        thickness: int,
        *,
        glow: bool,
    ) -> None:
        if len(points) < 2:
            return
        if glow:
            shadow = frame.copy()
            for idx in range(len(points) - 1):
                cv2.line(shadow, points[idx], points[idx + 1], (24, 34, 28), thickness=thickness + 3, lineType=cv2.LINE_AA)
            frame[:] = cv2.addWeighted(shadow, 0.28, frame, 0.72, 0.0)
        for idx in range(len(points) - 1):
            cv2.line(frame, points[idx], points[idx + 1], color, thickness=thickness, lineType=cv2.LINE_AA)

    def _projected_robot_point(self, scale_x: float, scale_y: float) -> tuple[int, int] | None:
        if self._progress_robot_point is None:
            return None
        return (
            int(self._progress_robot_point[0] * scale_x),
            int(self._progress_robot_point[1] * scale_y),
        )

    @staticmethod
    def _nearest_forward_index(points: list[tuple[int, int]], target: tuple[int, int]) -> int:
        best_index = 1
        best_distance = float("inf")
        tx, ty = target
        for index in range(1, len(points) + 1):
            px, py = points[index - 1]
            distance = ((px - tx) ** 2 + (py - ty) ** 2) ** 0.5
            if distance < best_distance:
                best_distance = distance
                best_index = index
        return best_index
