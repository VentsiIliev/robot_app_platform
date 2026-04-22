"""
Live ChArUco detection using the paint system's VisionService.
Detector and calibrator come from the engine module:
    src.engine.vision.implementation.VisionSystem.features.calibration.charuco

Board parameters — edit the constants below to match your physical board.

Press  q  to quit.
"""
from __future__ import annotations

import os
import sys
import time

import cv2
import numpy as np

PROJECT_ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
if PROJECT_ROOT not in sys.path:
    sys.path.insert(0, PROJECT_ROOT)

from src.engine.vision.implementation.VisionSystem.features.calibration.charuco import AutoCharucoBoardDetector

from src.engine.common_settings_ids import CommonSettingsID
from src.engine.core.message_broker import MessageBroker
from src.engine.repositories.settings_service_factory import build_from_specs
from src.engine.vision.implementation.VisionSystem.VisionSystem import VisionSystem
from src.engine.vision.implementation.VisionSystem.core.service.internal_service import Service
from src.engine.vision.vision_service import VisionService
from src.engine.work_areas.work_area_service import WorkAreaService
from src.robot_systems.paint.paint_robot_system import PaintRobotSystem


# ── Board config — edit to match your physical board ─────────────────────────
SQUARES_X     = 27
SQUARES_Y     = 18
SQUARE_LENGTH = 0.015          # metres
MARKER_LENGTH = 0.011          # metres
DICT_ID       = cv2.aruco.DICT_4X4_1000
#
# SQUARES_X     = 27
# SQUARES_Y     = 18
# SQUARE_LENGTH = 0.015          # metres
# MARKER_LENGTH = 0.012          # metres
# DICT_ID       = cv2.aruco.DICT_4X4_1000
# ─────────────────────────────────────────────────────────────────────────────


def _build_vision() -> VisionService:
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
    settings_repo    = settings_service.get_repo(CommonSettingsID.VISION_CAMERA_SETTINGS)
    data_storage_path = PaintRobotSystem.storage_path("settings", "vision", "data")
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


def _overlay(frame: np.ndarray, text: str, good: bool) -> np.ndarray:
    colour = (0, 220, 80) if good else (80, 80, 80)
    cv2.rectangle(frame, (0, 0), (frame.shape[1], 36), (0, 0, 0), -1)
    cv2.putText(frame, text, (8, 26), cv2.FONT_HERSHEY_SIMPLEX,
                0.7, colour, 2, cv2.LINE_AA)
    return frame


def main() -> None:
    print("Building vision service…")
    vision = _build_vision()
    vision.start()
    time.sleep(1.0)                     # let camera warm up

    detector = AutoCharucoBoardDetector(
        squares_x=SQUARES_X,
        squares_y=SQUARES_Y,
        square_length=SQUARE_LENGTH,
        marker_length=MARKER_LENGTH,
        dictionary_id=DICT_ID,
    )

    # Pull real intrinsics if calibrated; fall back to demo approximation otherwise.
    K    = vision._vision_system.cameraMatrix
    dist = vision._vision_system.cameraDist

    print("Press  q  to quit.")
    last_frame = None

    while True:
        frame = vision.get_latest_raw_frame()
        if frame is None or not isinstance(frame, np.ndarray) or frame.size == 0:
            time.sleep(0.02)
            continue
        if frame is last_frame:
            time.sleep(0.01)
            continue
        last_frame = frame

        result = detector.detect(frame, camera_matrix=K, dist_coeffs=dist)

        n_markers = 0 if result.marker_ids is None else len(result.marker_ids)
        n_corners = 0 if result.charuco_ids is None else len(result.charuco_ids)
        good      = n_corners > 0

        label = (
            f"mode={result.mode}  markers={n_markers}  charuco_corners={n_corners}"
            + ("  pose=OK" if result.rvec is not None else "")
        )
        display = _overlay(result.vis, label, good)

        cv2.imshow("ChArUco live", display)
        if cv2.waitKey(1) & 0xFF == ord("q"):
            break

    cv2.destroyAllWindows()
    vision.stop()
    print("Done.")


if __name__ == "__main__":
    main()
