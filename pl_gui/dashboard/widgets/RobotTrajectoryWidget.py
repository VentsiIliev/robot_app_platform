import os
import time
import threading
from collections import deque

import cv2
import numpy as np
from PyQt6.QtCore import QTimer, Qt
from PyQt6.QtGui import QFont, QImage, QPixmap
from PyQt6.QtWidgets import QWidget, QVBoxLayout, QLabel, QHBoxLayout, QFrame, QSizePolicy

try:
    from ...core.IconLoader import LOGO, CAMERA_PREVIEW_PLACEHOLDER
except ImportError:
    try:
        from dashboard.core.IconLoader import LOGO, CAMERA_PREVIEW_PLACEHOLDER
    except ImportError:
        LOGO = ""
        CAMERA_PREVIEW_PLACEHOLDER = ""


try:
    from src.dashboard.resources.styles import BORDER, BG_COLOR, METRIC_BLUE, METRIC_GREEN, TEXT_VALUE, IMAGE_LABEL_STYLE, CONTAINER_FRAME_STYLE
except ImportError:
    try:
        from dashboard.styles import BORDER, BG_COLOR, METRIC_BLUE, METRIC_GREEN, TEXT_VALUE, IMAGE_LABEL_STYLE, CONTAINER_FRAME_STYLE
    except ImportError:
        BORDER = "#E4E6F0"
        BG_COLOR = "#F6F7FB"
        METRIC_BLUE = "#1976D2"
        METRIC_GREEN = "#388E3C"
        TEXT_VALUE = "#212121"
        IMAGE_LABEL_STYLE = CONTAINER_FRAME_STYLE = ""


class CompactTimeMetric(QWidget):
    """Compact time metric with horizontal layout"""

    def __init__(self, title, value="0.00 s", color=None, parent=None):
        super().__init__(parent)
        self.color = color or METRIC_BLUE
        self.init_ui(title, value)

    def init_ui(self, title, value):
        layout = QHBoxLayout(self)
        layout.setContentsMargins(12, 8, 12, 8)
        layout.setSpacing(8)

        self.title_label = QLabel(title + ":")
        self.title_label.setFont(QFont("Segoe UI", 9, QFont.Weight.Normal))
        self.title_label.setStyleSheet(f"color: {self.color}; font-weight: 500;")

        self.value_label = QLabel(value)
        self.value_label.setFont(QFont("Segoe UI", 12, QFont.Weight.Bold))
        self.value_label.setStyleSheet(f"color: {TEXT_VALUE}; font-weight: 600;")

        layout.addWidget(self.title_label)
        layout.addWidget(self.value_label)
        layout.addStretch()

    def update_value(self, value):
        self.value_label.setText(value)


class TrajectoryManager:
    def __init__(self, trail_length: int = 100):
        self.trail_length = trail_length
        self.trajectory_points = deque(maxlen=trail_length)
        self.current_position = None
        self.last_position = None
        self._lock = threading.Lock()

        self.trail_thickness = 2
        self.trail_fade = False
        self.show_current_point = True
        self.interpolate_motion = True

        self.trail_color = (156, 39, 176)     # Purple 500
        self.current_point_color = (0, 0, 128)  # Navy Blue

        self.start_time = time.time() * 1000
        self.update_count = 0
        self.is_running = True

        self.trajectory_break_pending = False

    def add_interpolated_points(self, start_pos, end_pos, num_interpolated=3):
        start_x, start_y = start_pos
        end_x, end_y = end_pos
        current_time = time.time()

        distance = np.sqrt((end_x - start_x) ** 2 + (end_y - start_y) ** 2)

        with self._lock:
            if distance > 5:
                for i in range(1, num_interpolated + 1):
                    t = i / (num_interpolated + 1)
                    interp_x = int(start_x + t * (end_x - start_x))
                    interp_y = int(start_y + t * (end_y - start_y))
                    self.trajectory_points.append((interp_x, interp_y, current_time, False))
            self.trajectory_points.append((end_x, end_y, current_time, False))

    def update_position(self, position):
        if self.trajectory_break_pending:
            self.last_position = None
            self.trajectory_break_pending = False
        else:
            self.last_position = self.current_position

        self.current_position = position

        if self.last_position is not None and self.interpolate_motion:
            self.add_interpolated_points(self.last_position, self.current_position)
        else:
            with self._lock:
                is_break_start = self.last_position is None
                self.trajectory_points.append((*position, time.time(), is_break_start))

    def break_trajectory(self):
        self.trajectory_break_pending = True

    def clear_trail(self):
        with self._lock:
            self.trajectory_points.clear()
            self.current_position = None
            self.last_position = None

    def get_trajectory_copy(self):
        with self._lock:
            return list(self.trajectory_points)


def draw_icon_at_position(icon, image, position):
    if icon is None:
        raise ValueError("Logo icon is None")
    if image is None:
        raise ValueError("Image is None")
    if position is None:
        raise ValueError("Current position is None")

    image_width = image.shape[1]
    image_height = image.shape[0]
    x, y = position
    h, w = icon.shape[:2]
    x1, y1 = x - w // 2, y - h // 2
    x2, y2 = x1 + w, y1 + h

    if x1 >= 0 and y1 >= 0 and x2 <= image_width and y2 <= image_height:
        if len(icon.shape) == 3 and icon.shape[2] == 4:
            alpha_logo = icon[:, :, 3] / 255.0
            alpha_bg = 1.0 - alpha_logo
            for c in range(0, 3):
                image[y1:y2, x1:x2, c] = (
                    alpha_logo * icon[:, :, c] +
                    alpha_bg * image[y1:y2, x1:x2, c]
                ).astype(np.uint8)
        else:
            image[y1:y2, x1:x2] = icon


def draw_smooth_trail(image, trajectory_points_with_breaks):
    if len(trajectory_points_with_breaks) < 2:
        return

    image_width = image.shape[1]
    image_height = image.shape[0]

    segments = []
    current_segment = []

    for point_data in trajectory_points_with_breaks:
        if len(point_data) >= 4:
            x, y, timestamp, is_break = point_data[:4]
            if is_break and current_segment:
                if len(current_segment) > 1:
                    segments.append(current_segment)
                current_segment = [(x, y)]
            else:
                current_segment.append((x, y))
        else:
            x, y = point_data[:2]
            current_segment.append((x, y))

    if len(current_segment) > 1:
        segments.append(current_segment)

    for segment in segments:
        if len(segment) < 2:
            continue

        segment_points = np.array(segment, dtype=np.float32)
        smoothed_points = []
        kernel_size = 3

        for i in range(len(segment_points)):
            start = max(0, i - kernel_size + 1)
            avg_x = np.mean(segment_points[start:i + 1, 0])
            avg_y = np.mean(segment_points[start:i + 1, 1])
            smoothed_points.append((int(avg_x), int(avg_y)))

        total = len(smoothed_points)

        for i in range(total - 1):
            progress = (i + 1) / total
            if progress < 0.3:
                fade_factor = progress / 0.3
                color = (int(200 * fade_factor), int(100 * fade_factor), int(50 * fade_factor))
            elif progress < 0.7:
                fade_factor = (progress - 0.3) / 0.4
                color = (int(156 + (100 * fade_factor)),
                         int(39 + (50 * fade_factor)),
                         int(176 + (79 * fade_factor)))
            else:
                fade_factor = (progress - 0.7) / 0.3
                color = (int(255 * fade_factor), int(89 * fade_factor), int(255 * fade_factor))

            thickness = max(1, int(2 + (progress * 4)))
            p1 = smoothed_points[i]
            p2 = smoothed_points[i + 1]

            if (0 <= p1[0] < image_width and 0 <= p1[1] < image_height and
                    0 <= p2[0] < image_width and 0 <= p2[1] < image_height):
                cv2.line(image, p1, p2, color, thickness, lineType=cv2.LINE_AA)

        if len(smoothed_points) > 5:
            recent_points = smoothed_points[-5:]
            for i in range(len(recent_points) - 1):
                p1 = recent_points[i]
                p2 = recent_points[i + 1]
                if (0 <= p1[0] < image_width and 0 <= p1[1] < image_height and
                        0 <= p2[0] < image_width and 0 <= p2[1] < image_height):
                    cv2.line(image, p1, p2, (255, 200, 255), 6, lineType=cv2.LINE_AA)
                    cv2.line(image, p1, p2, (255, 100, 255), 2, lineType=cv2.LINE_AA)


def load_logo_icon():
    if not LOGO or not os.path.exists(LOGO):
        return None
    try:
        from PIL import Image
        pil_image = Image.open(LOGO).convert('RGBA')
        logo = np.array(pil_image)
        logo = cv2.cvtColor(logo, cv2.COLOR_RGBA2BGRA)
        return cv2.resize(logo, (36, 36), interpolation=cv2.INTER_AREA)
    except Exception:
        return None


class RobotTrajectoryWidget(QWidget):
    """
    Pure UI widget: displays a background camera frame and draws a robot
    trajectory trail on top.

    Has zero knowledge of MessageBroker or topics.
    Call set_image(), update_trajectory_point(), break_trajectory(),
    enable_drawing(), disable_drawing() from the adapter.
    """

    def __init__(self, image_width=640, image_height=360,
                 fps_ms: int = 30, trail_length: int = 100):
        super().__init__()

        self.image_width = image_width
        self.image_height = image_height

        self.estimated_time_value = 0.0
        self.time_left_value = 0.0

        self.base_frame = None
        self.current_frame = None
        self.trajectory_manager = TrajectoryManager(trail_length=trail_length)

        self.init_ui()

        self.logo_icon = load_logo_icon()
        self.load_placeholder_image()
        self.drawing_enabled = False

        self.timer = QTimer()
        self.timer.timeout.connect(self.update_display)
        self.timer.start(fps_ms)

    def init_ui(self):
        self.setWindowTitle("Trajectory Tracker")

        self.estimated_metric = CompactTimeMetric("Est. Time", "0.00 s", METRIC_BLUE)
        self.time_left_metric = CompactTimeMetric("Time Left", "0.00 s", METRIC_GREEN)

        metrics_layout = QHBoxLayout()
        metrics_layout.setSpacing(16)
        metrics_layout.addWidget(self.estimated_metric)
        metrics_layout.addWidget(self.time_left_metric)
        metrics_layout.addStretch()
        metrics_widget = QWidget()
        metrics_widget.setLayout(metrics_layout)
        metrics_widget.setVisible(False)

        self.image_label = QLabel()
        self.image_label.setFixedSize(self.image_width, self.image_height)
        self.image_label.setStyleSheet(IMAGE_LABEL_STYLE)
        self.image_label.setAlignment(Qt.AlignmentFlag.AlignCenter)
        self.image_label.setScaledContents(False)
        self.image_label.setSizePolicy(QSizePolicy.Policy.Expanding, QSizePolicy.Policy.Expanding)

        container_layout = QVBoxLayout()
        container_layout.setSpacing(4)
        container_layout.setContentsMargins(4, 4, 4, 4)
        container_layout.addWidget(metrics_widget)
        container_layout.addWidget(self.image_label)

        container_frame = QFrame()
        container_frame.setLayout(container_layout)
        container_frame.setStyleSheet(CONTAINER_FRAME_STYLE)

        main_layout = QVBoxLayout(self)
        main_layout.setContentsMargins(0, 0, 0, 0)
        main_layout.addWidget(container_frame)

        self.setSizePolicy(QSizePolicy.Policy.Fixed, QSizePolicy.Policy.Fixed)
        self.setFixedSize(self.image_width + 8, self.image_height + 8)

    def load_placeholder_image(self):
        try:
            if not CAMERA_PREVIEW_PLACEHOLDER or not os.path.exists(CAMERA_PREVIEW_PLACEHOLDER):
                placeholder_image = np.zeros((self.image_height, self.image_width, 3), dtype=np.uint8)
            else:
                placeholder_image = cv2.imread(CAMERA_PREVIEW_PLACEHOLDER)
                placeholder_image = cv2.resize(placeholder_image, (self.image_width, self.image_height))
            self.base_frame = placeholder_image.copy()
            self.current_frame = placeholder_image.copy()
            self._update_label_from_frame()
        except Exception as e:
            raise ValueError(f"Error loading placeholder image: {e}")

    # ------------------------------------------------------------------ #
    #  Public setter API                                                   #
    # ------------------------------------------------------------------ #

    def update_trajectory_point(self, message=None) -> None:
        """Receive a trajectory point message and update the manager."""
        if message is None:
            return
        x, y = message.get("x", 0), message.get("y", 0)
        self.trajectory_manager.update_position((int(x), int(y)))

    def break_trajectory(self) -> None:
        self.trajectory_manager.break_trajectory()

    def set_image(self, message=None) -> None:
        if message is None or not isinstance(message, dict) or "image" not in message:
            return
        frame = message.get("image")
        if frame is None:
            self.load_placeholder_image()
            return
        try:
            frame = cv2.resize(frame, (self.image_width, self.image_height))
            self.base_frame = frame.copy()
            self.trajectory_manager.clear_trail()
        except Exception:
            self.load_placeholder_image()

    def enable_drawing(self, _=None) -> None:
        self.drawing_enabled = True

    def disable_drawing(self, _=None) -> None:
        self.drawing_enabled = False
        self.trajectory_manager.clear_trail()

    # ------------------------------------------------------------------ #
    #  Internal display update                                             #
    # ------------------------------------------------------------------ #

    def update_display(self):
        if self.base_frame is None:
            return

        self.current_frame = self.base_frame.copy()
        trajectory_points_copy = self.trajectory_manager.get_trajectory_copy()

        if self.drawing_enabled and trajectory_points_copy:
            try:
                draw_smooth_trail(image=self.current_frame,
                                  trajectory_points_with_breaks=trajectory_points_copy)
            except (IndexError, ValueError):
                pass

        self._update_label_from_frame()
        self.trajectory_manager.update_count += 1
        self.estimated_metric.update_value(f"{self.estimated_time_value:.2f} s")
        self.time_left_metric.update_value(f"{self.time_left_value:.2f} s")

    def _update_label_from_frame(self):
        if self.current_frame is None:
            return
        rgb_image = cv2.cvtColor(self.current_frame, cv2.COLOR_BGR2RGB)
        h, w, ch = rgb_image.shape
        q_image = QImage(rgb_image.data, w, h, ch * w, QImage.Format.Format_RGB888)
        self.image_label.setPixmap(QPixmap.fromImage(q_image))

    def get_image_dimensions(self):
        return self.image_width, self.image_height

    def closeEvent(self, event):
        self.trajectory_manager.is_running = False
        self.timer.stop()
        event.accept()


if __name__ == "__main__":
    from PyQt6.QtWidgets import QApplication

    app = QApplication([])
    widget = RobotTrajectoryWidget(image_width=800, image_height=450)
    widget.show()

    def simulate_trajectory():
        import random
        for _ in range(200):
            x = random.randint(0, widget.image_width - 1)
            y = random.randint(0, widget.image_height - 1)
            widget.update_trajectory_point({"x": x, "y": y})
            time.sleep(0.1)

    threading.Thread(target=simulate_trajectory, daemon=True).start()
    app.exec()
