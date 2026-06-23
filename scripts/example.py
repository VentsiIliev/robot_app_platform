import sys
from pathlib import Path
from types import SimpleNamespace

import cv2
import numpy as np

from PyQt6.QtWidgets import QApplication, QWidget, QLabel, QPushButton, QVBoxLayout
from PyQt6.QtCore import QTimer, Qt
from PyQt6.QtGui import QImage, QPixmap

from scipy.optimize import least_squares


REPO_ROOT = Path(__file__).resolve().parents[1]
if str(REPO_ROOT) not in sys.path:
    sys.path.insert(0, str(REPO_ROOT))


# =====================================================
# TUNING PARAMETERS
# =====================================================

ACTIVE_WORK_AREA = "paint"

MIN_CONTOUR_AREA = 500

RESAMPLE_SPACING = 1.0

CORNER_EPSILON_RATIO = 0.004
# lower = more corners preserved
# higher = fewer corners, smoother outline

BEZIER_MAX_ERROR = 1.5
# lower = closer to original contour
# higher = smoother, less faithful

BEZIER_MIN_POINTS = 10
BEZIER_MAX_DEPTH = 10

BLUR_KERNEL = (5, 5)

MORPH_KERNEL_SIZE = 3
MORPH_CLOSE_ITERATIONS = 2
MORPH_OPEN_ITERATIONS = 1

ORIGINAL_CONTOUR_COLOR = (0, 0, 255)
ORIGINAL_CONTOUR_THICKNESS = 1

SMOOTH_CONTOUR_COLOR = (0, 255, 0)
SMOOTH_CONTOUR_THICKNESS = 2

CORNER_COLOR = (255, 0, 0)
CORNER_RADIUS = 4
DEVIATION_THRESHOLD_PX = 2.0
DEVIATION_COLOR = (0, 165, 255)
DEVIATION_RADIUS = 3

SAVE_CAPTURED_IMAGE = True
OUTPUT_FILENAME = "captured_bezier_contour.png"


# =====================================================
# CONTOUR RESAMPLING
# =====================================================

def resample_closed_contour(contour, spacing=RESAMPLE_SPACING):
    pts = contour[:, 0, :].astype(np.float64)
    pts = np.vstack([pts, pts[0]])

    d = np.linalg.norm(np.diff(pts, axis=0), axis=1)
    s = np.concatenate([[0], np.cumsum(d)])

    keep = np.r_[True, np.diff(s) > 1e-6]
    pts = pts[keep]
    s = s[keep]

    if s[-1] < 1e-6:
        return pts[:-1]

    new_s = np.arange(0, s[-1], spacing)

    x = np.interp(new_s, s, pts[:, 0])
    y = np.interp(new_s, s, pts[:, 1])

    return np.column_stack([x, y])


# =====================================================
# CORNER DETECTION
# =====================================================

def find_corner_indices(dense_pts, contour):
    cv_contour = contour_for_cv(contour)
    epsilon = CORNER_EPSILON_RATIO * cv2.arcLength(cv_contour, True)
    approx = cv2.approxPolyDP(cv_contour, epsilon, True)

    corners = approx[:, 0, :]

    indices = []
    for c in corners:
        i = np.argmin(np.linalg.norm(dense_pts - c, axis=1))
        indices.append(i)

    return sorted(set(indices))


def split_closed_points(points, corner_indices):
    n = len(points)
    corner_indices = sorted(corner_indices)

    segments = []

    for a, b in zip(corner_indices, corner_indices[1:] + [corner_indices[0] + n]):
        if b >= n:
            seg = np.vstack([points[a:], points[:b - n + 1]])
        else:
            seg = points[a:b + 1]

        if len(seg) >= 4:
            segments.append(seg)

    return segments


# =====================================================
# CUBIC BEZIER FITTING
# =====================================================

def bezier(t, p0, p1, p2, p3):
    t = t[:, None]

    return (
        (1 - t) ** 3 * p0
        + 3 * (1 - t) ** 2 * t * p1
        + 3 * (1 - t) * t ** 2 * p2
        + t ** 3 * p3
    )


def fit_cubic_bezier(points):
    points = points.astype(np.float64)

    p0 = points[0]
    p3 = points[-1]

    chord = p3 - p0

    p1_init = p0 + chord / 3.0
    p2_init = p0 + 2.0 * chord / 3.0

    d = np.linalg.norm(np.diff(points, axis=0), axis=1)
    s = np.concatenate([[0], np.cumsum(d)])

    if s[-1] < 1e-6:
        return p0, p1_init, p2_init, p3, 0.0

    t = s / s[-1]

    def residual(x):
        p1 = x[:2]
        p2 = x[2:]

        curve = bezier(t, p0, p1, p2, p3)
        return (curve - points).ravel()

    x0 = np.hstack([p1_init, p2_init])

    result = least_squares(
        residual,
        x0,
        max_nfev=80
    )

    p1 = result.x[:2]
    p2 = result.x[2:]

    fitted = bezier(t, p0, p1, p2, p3)
    error = np.max(np.linalg.norm(fitted - points, axis=1))

    return p0, p1, p2, p3, error


def adaptive_bezier_fit(points, depth=0):
    if len(points) < BEZIER_MIN_POINTS or depth >= BEZIER_MAX_DEPTH:
        p0, p1, p2, p3, _ = fit_cubic_bezier(points)
        return [(p0, p1, p2, p3)]

    p0, p1, p2, p3, error = fit_cubic_bezier(points)

    if error <= BEZIER_MAX_ERROR:
        return [(p0, p1, p2, p3)]

    mid = len(points) // 2

    left = adaptive_bezier_fit(points[:mid + 1], depth + 1)
    right = adaptive_bezier_fit(points[mid:], depth + 1)

    return left + right


def sample_bezier_segment(ctrl):
    p0, p1, p2, p3 = ctrl

    approx_len = (
        np.linalg.norm(p1 - p0)
        + np.linalg.norm(p2 - p1)
        + np.linalg.norm(p3 - p2)
    )

    n = max(8, int(approx_len / RESAMPLE_SPACING))

    t = np.linspace(0, 1, n)
    return bezier(t, p0, p1, p2, p3)


def smooth_contour_with_beziers(contour):
    dense = resample_closed_contour(contour, RESAMPLE_SPACING)

    corner_indices = find_corner_indices(dense, contour)

    if len(corner_indices) < 3:
        return dense.astype(np.float64), []

    segments = split_closed_points(dense, corner_indices)

    all_points = []

    for seg in segments:
        beziers = adaptive_bezier_fit(seg)

        for ctrl in beziers:
            sampled = sample_bezier_segment(ctrl)
            all_points.append(sampled[:-1])

    if not all_points:
        return dense.astype(np.float64), corner_indices

    result = np.vstack(all_points)
    return result.astype(np.float64), corner_indices


# =====================================================
# IMAGE PROCESSING
# =====================================================

def process_frame(frame, contours):
    output = frame.copy()

    contour = pick_largest_contour(contours)

    if contour is None:
        return output

    dense = resample_closed_contour(contour, RESAMPLE_SPACING)
    if len(dense) < 3:
        return output
    smooth, corner_indices = smooth_contour_with_beziers(contour)
    raw_rect = min_rect_metrics(contour[:, 0, :])
    processed_rect = min_rect_metrics(smooth)
    deviation = contour_deviation_metrics(contour[:, 0, :], smooth)
    print_min_rect_comparison(raw_rect, processed_rect, deviation)

    cv2.drawContours(
        output,
        [contour_for_drawing(contour)],
        -1,
        ORIGINAL_CONTOUR_COLOR,
        ORIGINAL_CONTOUR_THICKNESS
    )

    smooth_cv = polyline_for_drawing(smooth)
    if len(smooth_cv) < 2:
        return output

    cv2.polylines(
        output,
        [smooth_cv],
        True,
        SMOOTH_CONTOUR_COLOR,
        SMOOTH_CONTOUR_THICKNESS
    )

    for idx in corner_indices:
        if idx < 0 or idx >= len(dense):
            continue
        p = dense[idx].astype(int)
        cv2.circle(
            output,
            tuple(p),
            CORNER_RADIUS,
            CORNER_COLOR,
            -1
        )

    draw_min_rect(output, raw_rect, (0, 0, 255), "raw")
    draw_min_rect(output, processed_rect, (0, 255, 0), "processed")
    draw_deviation_points(output, deviation)
    draw_min_rect_text(output, raw_rect, processed_rect, deviation)

    return output


def normalize_contour(contour):
    if hasattr(contour, "get") and callable(contour.get):
        contour = contour.get()
    try:
        points = np.asarray(contour, dtype=np.float64).reshape(-1, 2)
    except Exception:
        return None
    if len(points) < 3:
        return None
    finite = np.isfinite(points).all(axis=1)
    points = points[finite]
    if len(points) < 3:
        return None
    return np.ascontiguousarray(points.astype(np.float64).reshape(-1, 1, 2))


def pick_largest_contour(contours):
    best = None
    best_area = 0.0
    for contour in contours or []:
        candidate = normalize_contour(contour)
        if candidate is None or len(candidate) < 3:
            continue
        area = float(abs(cv2.contourArea(contour_for_cv(candidate))))
        if area < MIN_CONTOUR_AREA:
            continue
        if area > best_area:
            best = candidate
            best_area = area
    return best


def contour_for_cv(contour):
    points = np.asarray(contour, dtype=np.float32).reshape(-1, 1, 2)
    return np.ascontiguousarray(points)


def contour_for_drawing(contour):
    points = np.asarray(contour, dtype=np.float64).reshape(-1, 2)
    return np.ascontiguousarray(np.round(points).astype(np.int32).reshape(-1, 1, 2))


def polyline_for_drawing(points):
    pts = np.asarray(points, dtype=np.float64).reshape(-1, 2)
    return np.ascontiguousarray(np.round(pts).astype(np.int32).reshape(-1, 1, 2))


def min_rect_metrics(points):
    pts = np.asarray(points, dtype=np.float32).reshape(-1, 2)
    if len(pts) < 3:
        return {
            "center": (0.0, 0.0),
            "width": 0.0,
            "height": 0.0,
            "major": 0.0,
            "minor": 0.0,
            "angle": 0.0,
            "area": 0.0,
            "box": np.zeros((4, 2), dtype=np.float32),
        }
    rect = cv2.minAreaRect(pts.reshape(-1, 1, 2))
    (cx, cy), (width, height), angle = rect
    width = float(width)
    height = float(height)
    angle = float(angle)
    major = width
    minor = height
    if minor > major:
        major, minor = minor, major
        angle += 90.0
    return {
        "center": (float(cx), float(cy)),
        "width": width,
        "height": height,
        "major": major,
        "minor": minor,
        "angle": normalize_rect_angle(angle),
        "area": major * minor,
        "box": cv2.boxPoints(rect).astype(np.float32),
    }


def normalize_rect_angle(angle):
    value = float(angle)
    while value <= -90.0:
        value += 180.0
    while value > 90.0:
        value -= 180.0
    return value


def rect_angle_delta(before, after):
    delta = float(after) - float(before)
    while delta <= -90.0:
        delta += 180.0
    while delta > 90.0:
        delta -= 180.0
    return delta


def contour_deviation_metrics(raw_points, processed_points):
    raw = np.asarray(raw_points, dtype=np.float64).reshape(-1, 2)
    processed = np.asarray(processed_points, dtype=np.float64).reshape(-1, 2)
    if len(raw) == 0 or len(processed) == 0:
        return {
            "raw_to_processed_mean": 0.0,
            "raw_to_processed_max": 0.0,
            "processed_to_raw_mean": 0.0,
            "processed_to_raw_max": 0.0,
            "hausdorff": 0.0,
            "raw_error_points": np.empty((0, 2), dtype=np.float64),
            "processed_error_points": np.empty((0, 2), dtype=np.float64),
        }

    raw_distances = point_to_polyline_distances(raw, processed, closed=True)
    processed_distances = point_to_polyline_distances(processed, raw, closed=True)
    raw_bad = raw[raw_distances > DEVIATION_THRESHOLD_PX]
    processed_bad = processed[processed_distances > DEVIATION_THRESHOLD_PX]
    return {
        "raw_to_processed_mean": float(np.mean(raw_distances)),
        "raw_to_processed_max": float(np.max(raw_distances)),
        "processed_to_raw_mean": float(np.mean(processed_distances)),
        "processed_to_raw_max": float(np.max(processed_distances)),
        "hausdorff": float(max(np.max(raw_distances), np.max(processed_distances))),
        "raw_error_points": raw_bad,
        "processed_error_points": processed_bad,
    }


def point_to_polyline_distances(points, polyline, closed):
    pts = np.asarray(points, dtype=np.float64).reshape(-1, 2)
    line = np.asarray(polyline, dtype=np.float64).reshape(-1, 2)
    if len(pts) == 0 or len(line) == 0:
        return np.zeros(len(pts), dtype=np.float64)
    if len(line) == 1:
        return np.linalg.norm(pts - line[0], axis=1)

    starts = line
    ends = np.roll(line, -1, axis=0) if closed else line[1:]
    if not closed:
        starts = line[:-1]

    distances = np.full(len(pts), np.inf, dtype=np.float64)
    for start, end in zip(starts, ends):
        segment = end - start
        length_sq = float(np.dot(segment, segment))
        if length_sq <= 1e-12:
            candidate = np.linalg.norm(pts - start, axis=1)
        else:
            t = np.clip(((pts - start) @ segment) / length_sq, 0.0, 1.0)
            projection = start + t[:, None] * segment
            candidate = np.linalg.norm(pts - projection, axis=1)
        distances = np.minimum(distances, candidate)
    return distances


def print_min_rect_comparison(raw_rect, processed_rect, deviation):
    print(
        "min_rect raw="
        f"{raw_rect['major']:.3f}x{raw_rect['minor']:.3f}px angle={raw_rect['angle']:.3f}deg "
        "processed="
        f"{processed_rect['major']:.3f}x{processed_rect['minor']:.3f}px angle={processed_rect['angle']:.3f}deg "
        "delta="
        f"{processed_rect['major'] - raw_rect['major']:+.3f}x"
        f"{processed_rect['minor'] - raw_rect['minor']:+.3f}px "
        f"angle_delta={rect_angle_delta(raw_rect['angle'], processed_rect['angle']):+.3f}deg "
        f"area_delta={processed_rect['area'] - raw_rect['area']:+.3f}px2 "
        "deviation "
        f"raw_to_proc mean/max={deviation['raw_to_processed_mean']:.3f}/{deviation['raw_to_processed_max']:.3f}px "
        f"proc_to_raw mean/max={deviation['processed_to_raw_mean']:.3f}/{deviation['processed_to_raw_max']:.3f}px "
        f"hausdorff={deviation['hausdorff']:.3f}px"
    )


def draw_min_rect(frame, rect, color, label):
    box = np.asarray(rect["box"], dtype=np.int32).reshape(-1, 1, 2)
    if len(box) != 4:
        return
    cv2.polylines(frame, [box], True, color, 1, cv2.LINE_AA)
    point = tuple(box[0, 0].tolist())
    cv2.putText(frame, label, point, cv2.FONT_HERSHEY_SIMPLEX, 0.45, color, 1, cv2.LINE_AA)


def draw_deviation_points(frame, deviation):
    for points in (deviation["raw_error_points"], deviation["processed_error_points"]):
        for point in np.round(points).astype(np.int32):
            cv2.circle(
                frame,
                (int(point[0]), int(point[1])),
                DEVIATION_RADIUS,
                DEVIATION_COLOR,
                -1,
                cv2.LINE_AA,
            )


def draw_min_rect_text(frame, raw_rect, processed_rect, deviation):
    lines = [
        f"raw rect: {raw_rect['major']:.2f} x {raw_rect['minor']:.2f}px  a={raw_rect['angle']:.2f}",
        f"proc rect: {processed_rect['major']:.2f} x {processed_rect['minor']:.2f}px  a={processed_rect['angle']:.2f}",
        (
            "delta: "
            f"{processed_rect['major'] - raw_rect['major']:+.2f} x "
            f"{processed_rect['minor'] - raw_rect['minor']:+.2f}px  "
            f"da={rect_angle_delta(raw_rect['angle'], processed_rect['angle']):+.2f}"
        ),
        (
            "curve dev: "
            f"r2p {deviation['raw_to_processed_mean']:.2f}/{deviation['raw_to_processed_max']:.2f}px  "
            f"p2r {deviation['processed_to_raw_mean']:.2f}/{deviation['processed_to_raw_max']:.2f}px  "
            f"H {deviation['hausdorff']:.2f}px"
        ),
    ]
    x, y = 12, 24
    for line in lines:
        cv2.putText(frame, line, (x, y), cv2.FONT_HERSHEY_SIMPLEX, 0.55, (0, 0, 0), 3, cv2.LINE_AA)
        cv2.putText(frame, line, (x, y), cv2.FONT_HERSHEY_SIMPLEX, 0.55, (255, 255, 255), 1, cv2.LINE_AA)
        y += 22


def ensure_bgr(frame):
    if frame is None:
        return None
    image = np.asarray(frame)
    if image.ndim == 2:
        return cv2.cvtColor(image, cv2.COLOR_GRAY2BGR)
    if image.ndim == 3 and image.shape[2] == 4:
        return cv2.cvtColor(image, cv2.COLOR_BGRA2BGR)
    if image.ndim == 3 and image.shape[2] == 3:
        return image.copy()
    return None


def build_paint_vision_service(active_area=ACTIVE_WORK_AREA):
    from src.engine.common_service_ids import CommonServiceID
    from src.engine.core.message_broker import MessageBroker
    from src.engine.repositories.settings_service_factory import build_from_specs
    from src.engine.work_areas.work_area_service import WorkAreaService
    from src.robot_systems.default_service_builders import build_vision_service
    from src.robot_systems.paint.paint_robot_system import PaintRobotSystem

    settings_service = build_from_specs(
        PaintRobotSystem.settings_specs,
        PaintRobotSystem.metadata.settings_root,
        PaintRobotSystem,
    )
    work_area_service = WorkAreaService(
        settings_service=settings_service,
        definitions=PaintRobotSystem.work_areas,
        default_active_area_id=PaintRobotSystem.default_active_work_area_id,
    )
    if active_area:
        work_area_service.set_active_area_id(active_area)

    ctx = SimpleNamespace(
        settings=settings_service,
        system_class=PaintRobotSystem,
        services={CommonServiceID.WORK_AREAS: work_area_service},
        messaging_service=MessageBroker(),
    )
    vision_service = build_vision_service(ctx)
    if active_area:
        vision_service.set_active_work_area(active_area)
    return vision_service


# =====================================================
# PYQT6 APP
# =====================================================

class CameraApp(QWidget):
    def __init__(self):
        super().__init__()

        self.setWindowTitle("Corner-Preserving Bezier Contour Capture")

        self.camera_label = QLabel()
        self.camera_label.setAlignment(Qt.AlignmentFlag.AlignCenter)

        self.result_label = QLabel("Captured result will appear here")
        self.result_label.setAlignment(Qt.AlignmentFlag.AlignCenter)

        self.capture_button = QPushButton("Capture")
        self.capture_button.clicked.connect(self.capture)

        layout = QVBoxLayout()
        layout.addWidget(self.camera_label)
        layout.addWidget(self.capture_button)
        layout.addWidget(self.result_label)

        self.setLayout(layout)

        self.vision = build_paint_vision_service()
        self.vision.start()
        self.current_frame = None
        self.current_contours = []

        self.timer = QTimer()
        self.timer.timeout.connect(self.update_camera)
        self.timer.start(30)

    def update_camera(self):
        try:
            frame = ensure_bgr(self.vision.get_latest_frame())
            contours = list(self.vision.get_latest_contours())
        except Exception:
            return

        if frame is None:
            return
        self.current_frame = frame.copy()
        self.current_contours = contours
        self.show_image(self.camera_label, frame)

    def capture(self):
        if self.current_frame is None:
            return

        result = process_frame(self.current_frame, self.current_contours)

        self.show_image(self.result_label, result)

        if SAVE_CAPTURED_IMAGE:
            cv2.imwrite(OUTPUT_FILENAME, result)

    def show_image(self, label, frame):
        rgb = cv2.cvtColor(frame, cv2.COLOR_BGR2RGB)

        h, w, ch = rgb.shape
        bytes_per_line = ch * w

        qimg = QImage(
            rgb.data,
            w,
            h,
            bytes_per_line,
            QImage.Format.Format_RGB888
        )

        pixmap = QPixmap.fromImage(qimg)

        label_w = max(label.width(), 100)
        label_h = max(label.height(), 100)

        pixmap = pixmap.scaled(
            label_w,
            label_h,
            Qt.AspectRatioMode.KeepAspectRatio,
            Qt.TransformationMode.SmoothTransformation
        )

        label.setPixmap(pixmap)

    def closeEvent(self, event):
        self.timer.stop()
        self.vision.stop()
        event.accept()


# =====================================================
# MAIN
# =====================================================

if __name__ == "__main__":
    app = QApplication(sys.argv)

    window = CameraApp()
    window.resize(1000, 900)
    window.show()

    sys.exit(app.exec())
