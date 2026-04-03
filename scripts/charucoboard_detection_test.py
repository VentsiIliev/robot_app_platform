from __future__ import annotations

import os
import pickle
import sys
import threading
import time
from datetime import datetime

import cv2
import numpy as np

PROJECT_ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
if PROJECT_ROOT not in sys.path:
    sys.path.insert(0, PROJECT_ROOT)

from PyQt6.QtCore import Qt, pyqtSignal, QObject
from PyQt6.QtGui import QImage, QPixmap
from PyQt6.QtWidgets import (
    QApplication,
    QDoubleSpinBox,
    QFormLayout,
    QGroupBox,
    QHBoxLayout,
    QLabel,
    QMainWindow,
    QPushButton,
    QSizePolicy,
    QSpinBox,
    QTextEdit,
    QVBoxLayout,
    QWidget,
)

from src.engine.common_settings_ids import CommonSettingsID
from src.engine.core.message_broker import MessageBroker
from src.engine.repositories.settings_service_factory import build_from_specs
from src.engine.vision.implementation.VisionSystem.VisionSystem import VisionSystem
from src.engine.vision.implementation.VisionSystem.core.service.internal_service import Service
from src.engine.vision.vision_service import VisionService
from src.engine.work_areas.work_area_service import WorkAreaService
from src.robot_systems.glue.glue_robot_system import GlueRobotSystem

# ── Board defaults (charuco_a4_11x8_18mm_12mm.png) ────────────────────────────
_DEFAULT_COLS        = 26
_DEFAULT_ROWS        = 17
_DEFAULT_SQUARE_MM   = 18.0
_DEFAULT_MARKER_MM   = 12.0
_DEFAULT_DICT_NAME   = "DICT_4X4_250"
_MIN_CORNERS         = 20    # corners required per calibration frame
_MIN_CALIB_FRAMES    = 15    # frames required before calibration is allowed
_OUTPUT_FILE         = os.path.join(os.path.dirname(__file__), "calibration.pckl")


# ── Vision bootstrap ──────────────────────────────────────────────────────────

def _build_vision_service() -> VisionService:
    settings_service = build_from_specs(
        GlueRobotSystem.settings_specs,
        GlueRobotSystem.metadata.settings_root,
        GlueRobotSystem,
    )
    work_area_service = WorkAreaService(
        settings_service=settings_service,
        definitions=GlueRobotSystem.work_areas,
        default_active_area_id=GlueRobotSystem.default_active_work_area_id,
    )
    settings_repo = settings_service.get_repo(CommonSettingsID.VISION_CAMERA_SETTINGS)
    data_storage_path = GlueRobotSystem.storage_path("settings", "vision", "data")
    os.makedirs(data_storage_path, exist_ok=True)

    internal_service = Service(
        data_storage_path=data_storage_path,
        settings_file_path=settings_repo.file_path,
    )
    vision_system = VisionSystem(
        storage_path=data_storage_path,
        messaging_service=MessageBroker(),
        service=internal_service,
        work_area_service=work_area_service,
    )
    return VisionService(vision_system, work_area_service=work_area_service)


# ── Bridge + Collector ────────────────────────────────────────────────────────

class _Bridge(QObject):
    frame_ready    = pyqtSignal(object, str, bool)   # annotated frame, log msg, good detection
    capture_added  = pyqtSignal(int)                 # total calibration frames collected


class _Collector:
    def __init__(self, vision: VisionService) -> None:
        self._vision   = vision
        self._running  = False
        self._thread: threading.Thread | None = None
        self.bridge    = _Bridge()

        self._lock             = threading.Lock()
        self._cols             = _DEFAULT_COLS
        self._rows             = _DEFAULT_ROWS
        self._square_size      = _DEFAULT_SQUARE_MM / 1000.0
        self._marker_size      = _DEFAULT_MARKER_MM / 1000.0
        self._dict_name        = _DEFAULT_DICT_NAME
        self._auto_capture     = True

        self._calib_corners: list[np.ndarray] = []
        self._calib_ids:     list[np.ndarray] = []
        self._image_size:    tuple[int, int] | None = None
        self._pending_capture = False   # manual capture requested

    def configure(self, cols: int, rows: int, square_mm: float,
                  marker_mm: float, dict_name: str, auto_capture: bool) -> None:
        with self._lock:
            self._cols         = cols
            self._rows         = rows
            self._square_size  = square_mm / 1000.0
            self._marker_size  = marker_mm / 1000.0
            self._dict_name    = dict_name
            self._auto_capture = auto_capture

    def request_capture(self) -> None:
        self._pending_capture = True

    def clear_frames(self) -> None:
        with self._lock:
            self._calib_corners.clear()
            self._calib_ids.clear()
            self._image_size = None
        self.bridge.capture_added.emit(0)

    def get_frame_count(self) -> int:
        return len(self._calib_corners)

    def calibrate(self) -> tuple[bool, str]:
        with self._lock:
            if len(self._calib_corners) < _MIN_CALIB_FRAMES:
                return False, f"Need ≥ {_MIN_CALIB_FRAMES} frames, have {len(self._calib_corners)}"
            corners = list(self._calib_corners)
            ids     = list(self._calib_ids)
            img_sz  = self._image_size
            cols    = self._cols
            rows    = self._rows
            sq      = self._square_size
            mk      = self._marker_size
            dn      = self._dict_name

        aruco_dict = cv2.aruco.getPredefinedDictionary(getattr(cv2.aruco, dn, cv2.aruco.DICT_4X4_250))
        board = cv2.aruco.CharucoBoard((cols, rows), sq, mk, aruco_dict)
        try:
            _, cam_matrix, dist_coeffs, rvecs, tvecs = cv2.aruco.calibrateCameraCharuco(
                charucoCorners=corners,
                charucoIds=ids,
                board=board,
                imageSize=img_sz,
                cameraMatrix=None,
                distCoeffs=None,
            )
        except Exception as exc:
            return False, f"calibrateCameraCharuco failed: {exc}"

        with open(_OUTPUT_FILE, "wb") as f:
            pickle.dump((cam_matrix, dist_coeffs, rvecs, tvecs), f)

        return True, (
            f"Calibration saved to {_OUTPUT_FILE}\n"
            f"Matrix:\n{cam_matrix}\nDist:\n{dist_coeffs}"
        )

    def start(self) -> None:
        if self._running:
            return
        self._running = True
        self._thread  = threading.Thread(target=self._loop, daemon=True)
        self._thread.start()

    def stop(self) -> None:
        self._running = False
        if self._thread:
            self._thread.join(timeout=2.0)
            self._thread = None

    # ── internal loop ─────────────────────────────────────────────────────────

    def _loop(self) -> None:
        with self._lock:
            cols        = self._cols
            rows        = self._rows
            square_size = self._square_size
            marker_size = self._marker_size
            dict_name   = self._dict_name

        dict_id    = getattr(cv2.aruco, dict_name, cv2.aruco.DICT_4X4_250)
        aruco_dict = cv2.aruco.getPredefinedDictionary(dict_id)
        board      = cv2.aruco.CharucoBoard((cols, rows), square_size, marker_size, aruco_dict)

        det_params = cv2.aruco.DetectorParameters()
        det_params.cornerRefinementMethod        = cv2.aruco.CORNER_REFINE_SUBPIX
        det_params.adaptiveThreshWinSizeMin       = 3
        det_params.adaptiveThreshWinSizeMax       = 53
        det_params.adaptiveThreshWinSizeStep      = 4
        det_params.errorCorrectionRate            = 0.8
        det_params.maxErroneousBitsInBorderRate   = 0.5
        det_params.minMarkerPerimeterRate         = 0.02
        aruco_detector   = cv2.aruco.ArucoDetector(aruco_dict, det_params)
        charuco_detector = cv2.aruco.CharucoDetector(
            board, cv2.aruco.CharucoParameters(), det_params, cv2.aruco.RefineParameters(),
        )

        board_max_id = (cols * rows) // 2 - 1
        last_frame: np.ndarray | None = None

        while self._running:
            frame = self._vision.get_latest_raw_frame()
            if frame is None or not isinstance(frame, np.ndarray) or frame.size == 0:
                time.sleep(0.05)
                continue
            if frame is last_frame:
                time.sleep(0.01)
                continue
            last_frame = frame

            gray    = cv2.cvtColor(frame, cv2.COLOR_BGR2GRAY) if frame.ndim == 3 else frame
            display = frame.copy()
            ts      = datetime.now().strftime("%H:%M:%S.%f")[:-3]

            # ── Step 1: detect ArUco markers ──────────────────────────────────
            try:
                marker_corners, marker_ids, _ = aruco_detector.detectMarkers(gray)
            except Exception as exc:
                self.bridge.frame_ready.emit(display, f"[{ts}] ERROR detect: {exc}", False)
                time.sleep(0.1)
                continue

            n_markers = 0 if marker_ids is None else len(marker_ids)

            if n_markers == 0:
                self.bridge.frame_ready.emit(display, f"[{ts}] no markers", False)
                time.sleep(0.05)
                continue

            cv2.aruco.drawDetectedMarkers(display, marker_corners, marker_ids)

            # diagnostic: in-range count
            ids_flat = marker_ids.flatten()
            in_range = int(np.sum(ids_flat <= board_max_id))
            id_info  = f"{in_range}/{(cols * rows) // 2} board markers (IDs {ids_flat.min()}–{ids_flat.max()})"

            # ── Step 2: ChArUco corner detection ──────────────────────────────
            # CharucoDetector uses the same aruco_dict + det_params internally.
            try:
                charuco_corners, charuco_ids, _, _ = charuco_detector.detectBoard(gray)
                n_corners = 0 if charuco_ids is None else len(charuco_ids)
            except Exception as exc:
                self.bridge.frame_ready.emit(display, f"[{ts}] ERROR detectBoard: {exc}", False)
                time.sleep(0.1)
                continue

            n_corners = n_corners or 0

            if n_corners < _MIN_CORNERS:
                self.bridge.frame_ready.emit(
                    display,
                    f"[{ts}] {id_info}, {n_corners}/{_MIN_CORNERS} corners",
                    False,
                )
                time.sleep(0.05)
                continue

            # ── Good detection ────────────────────────────────────────────────
            if charuco_corners is not None and charuco_ids is not None:
                cv2.aruco.drawDetectedCornersCharuco(display, charuco_corners, charuco_ids)

            with self._lock:
                auto    = self._auto_capture
                img_sz  = self._image_size

            should_capture = auto or self._pending_capture
            self._pending_capture = False

            n_frames = len(self._calib_corners)
            msg = (
                f"[{ts}] detected {n_corners} corners — "
                + ("CAPTURED" if should_capture else "press Capture")
                + f" ({n_frames}/{_MIN_CALIB_FRAMES})"
            )

            if should_capture:
                h, w = gray.shape[:2]
                with self._lock:
                    self._calib_corners.append(charuco_corners)
                    self._calib_ids.append(charuco_ids)
                    if self._image_size is None:
                        self._image_size = (w, h)
                self.bridge.capture_added.emit(len(self._calib_corners))

            self.bridge.frame_ready.emit(display, msg, True)
            time.sleep(0.05)


# ── Main window ───────────────────────────────────────────────────────────────

class _MainWindow(QMainWindow):
    def __init__(self, vision: VisionService) -> None:
        super().__init__()
        self.setWindowTitle("ChArUco Camera Calibration")
        self.resize(1280, 900)

        self._collector = _Collector(vision)
        self._collector.bridge.frame_ready.connect(self._on_frame_ready)
        self._collector.bridge.capture_added.connect(self._on_capture_added)

        central = QWidget()
        self.setCentralWidget(central)
        root = QHBoxLayout(central)
        root.setContentsMargins(8, 8, 8, 8)
        root.setSpacing(8)

        # ── Left panel ────────────────────────────────────────────────────────
        left = QWidget()
        left.setFixedWidth(320)
        left_layout = QVBoxLayout(left)
        left_layout.setContentsMargins(0, 0, 0, 0)

        # Board settings
        board_box = QGroupBox("Board Settings")
        form = QFormLayout(board_box)

        self._cols = QSpinBox()
        self._cols.setRange(2, 30)
        self._cols.setValue(_DEFAULT_COLS)
        form.addRow("Squares X (cols):", self._cols)

        self._rows = QSpinBox()
        self._rows.setRange(2, 30)
        self._rows.setValue(_DEFAULT_ROWS)
        form.addRow("Squares Y (rows):", self._rows)

        self._square_mm = QDoubleSpinBox()
        self._square_mm.setRange(1.0, 500.0)
        self._square_mm.setValue(_DEFAULT_SQUARE_MM)
        self._square_mm.setSuffix(" mm")
        form.addRow("Square size:", self._square_mm)

        self._marker_mm = QDoubleSpinBox()
        self._marker_mm.setRange(1.0, 499.0)
        self._marker_mm.setValue(_DEFAULT_MARKER_MM)
        self._marker_mm.setSuffix(" mm")
        form.addRow("Marker size:", self._marker_mm)

        left_layout.addWidget(board_box)

        # Capture controls
        ctrl_box = QGroupBox("Capture")
        ctrl_layout = QVBoxLayout(ctrl_box)

        self._frame_label = QLabel(f"Frames: 0 / {_MIN_CALIB_FRAMES}")
        self._frame_label.setStyleSheet("font-weight: bold; font-size: 12pt;")
        ctrl_layout.addWidget(self._frame_label)

        self._capture_btn = QPushButton("📷 Capture Frame")
        self._capture_btn.setFixedHeight(40)
        self._capture_btn.setEnabled(False)
        ctrl_layout.addWidget(self._capture_btn)

        self._clear_btn = QPushButton("🗑  Clear Frames")
        self._clear_btn.setFixedHeight(36)
        self._clear_btn.setEnabled(False)
        ctrl_layout.addWidget(self._clear_btn)

        left_layout.addWidget(ctrl_box)

        # Start / Stop
        btn_row = QHBoxLayout()
        self._start_btn = QPushButton("▶  Start")
        self._start_btn.setFixedHeight(40)
        self._stop_btn = QPushButton("■  Stop")
        self._stop_btn.setFixedHeight(40)
        self._stop_btn.setEnabled(False)
        btn_row.addWidget(self._start_btn)
        btn_row.addWidget(self._stop_btn)
        left_layout.addLayout(btn_row)

        # Calibrate
        self._calibrate_btn = QPushButton("🎯  Run Calibration")
        self._calibrate_btn.setFixedHeight(48)
        self._calibrate_btn.setEnabled(False)
        self._calibrate_btn.setStyleSheet(
            "QPushButton { background: #1565C0; color: white; font-weight: bold; "
            "font-size: 11pt; border-radius: 6px; }"
            "QPushButton:disabled { background: #555; color: #aaa; }"
        )
        left_layout.addWidget(self._calibrate_btn)

        # Log
        log_box = QGroupBox("Log")
        log_layout = QVBoxLayout(log_box)
        self._log = QTextEdit()
        self._log.setReadOnly(True)
        self._log.setStyleSheet("font-family: monospace; font-size: 9pt;")
        log_layout.addWidget(self._log)
        left_layout.addWidget(log_box, 1)

        root.addWidget(left)

        # ── Preview ───────────────────────────────────────────────────────────
        self._preview = QLabel("Waiting for frame…")
        self._preview.setAlignment(Qt.AlignmentFlag.AlignCenter)
        self._preview.setSizePolicy(QSizePolicy.Policy.Expanding, QSizePolicy.Policy.Expanding)
        self._preview.setStyleSheet("background: #1a1a1a; color: #888;")
        root.addWidget(self._preview, 1)

        self._start_btn.clicked.connect(self._on_start)
        self._stop_btn.clicked.connect(self._on_stop)
        self._capture_btn.clicked.connect(self._on_capture)
        self._clear_btn.clicked.connect(self._on_clear)
        self._calibrate_btn.clicked.connect(self._on_calibrate)

    def _on_start(self) -> None:
        self._collector.configure(
            cols=self._cols.value(),
            rows=self._rows.value(),
            square_mm=self._square_mm.value(),
            marker_mm=self._marker_mm.value(),
            dict_name=_DEFAULT_DICT_NAME,
            auto_capture=True,
        )
        self._collector.start()
        self._start_btn.setEnabled(False)
        self._stop_btn.setEnabled(True)
        self._capture_btn.setEnabled(True)
        self._clear_btn.setEnabled(True)

    def _on_stop(self) -> None:
        self._collector.stop()
        self._start_btn.setEnabled(True)
        self._stop_btn.setEnabled(False)
        self._capture_btn.setEnabled(False)

    def _on_capture(self) -> None:
        self._collector.request_capture()

    def _on_clear(self) -> None:
        self._collector.clear_frames()

    def _on_calibrate(self) -> None:
        self._calibrate_btn.setEnabled(False)
        self._log.append('<span style="color:#FFB300">Running calibration…</span>')
        ok, msg = self._collector.calibrate()
        color = "#00C853" if ok else "#FF5252"
        for line in msg.splitlines():
            self._log.append(f'<span style="color:{color}">{line}</span>')
        sb = self._log.verticalScrollBar()
        sb.setValue(sb.maximum())
        if not ok:
            self._calibrate_btn.setEnabled(True)

    def _on_frame_ready(self, frame: np.ndarray, msg: str, success: bool) -> None:
        color = "#00C853" if success else "#aaaaaa"
        self._log.append(f'<span style="color:{color}">{msg}</span>')
        sb = self._log.verticalScrollBar()
        sb.setValue(sb.maximum())

        h, w = frame.shape[:2]
        rgb  = frame[:, :, ::-1].copy()
        qimg = QImage(rgb.data, w, h, w * 3, QImage.Format.Format_RGB888)
        pix  = QPixmap.fromImage(qimg).scaled(
            self._preview.width(), self._preview.height(),
            Qt.AspectRatioMode.KeepAspectRatio,
            Qt.TransformationMode.SmoothTransformation,
        )
        self._preview.setPixmap(pix)

    def _on_capture_added(self, count: int) -> None:
        self._frame_label.setText(f"Frames: {count} / {_MIN_CALIB_FRAMES}")
        ready = count >= _MIN_CALIB_FRAMES
        self._calibrate_btn.setEnabled(ready)
        if ready:
            self._log.append(
                f'<span style="color:#FFB300">✔ {count} frames collected — ready to calibrate!</span>'
            )

    def closeEvent(self, event) -> None:
        self._collector.stop()
        super().closeEvent(event)


# ── Entry point ───────────────────────────────────────────────────────────────

def main() -> None:
    vision = _build_vision_service()
    vision.start()
    time.sleep(1.0)

    app    = QApplication(sys.argv)
    window = _MainWindow(vision)
    window.show()
    try:
        sys.exit(app.exec())
    finally:
        vision.stop()


if __name__ == "__main__":
    main()

