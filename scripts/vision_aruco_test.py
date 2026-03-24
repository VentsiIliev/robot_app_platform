from __future__ import annotations

import argparse
import os
import sys
import time

import cv2
import numpy as np

PROJECT_ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
if PROJECT_ROOT not in sys.path:
    sys.path.insert(0, PROJECT_ROOT)

from src.engine.common_settings_ids import CommonSettingsID
from src.engine.core.message_broker import MessageBroker
from src.engine.repositories.settings_service_factory import build_from_specs
from src.engine.vision.implementation.VisionSystem.VisionSystem import VisionSystem
from src.engine.vision.implementation.VisionSystem.core.service.internal_service import Service
from src.engine.vision.vision_service import VisionService
from src.engine.work_areas.work_area_service import WorkAreaService
from src.robot_systems.glue.glue_robot_system import GlueRobotSystem


def _build_vision_service(active_area: str | None) -> VisionService:
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
    if active_area is not None:
        work_area_service.set_active_area_id(active_area)

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


def _draw_markers(frame: np.ndarray, corners, ids) -> np.ndarray:
    output = frame.copy()
    if ids is not None and len(ids) > 0:
        cv2.aruco.drawDetectedMarkers(output, corners, ids)
        for marker_corners, marker_id in zip(corners, ids.flatten()):
            center = np.mean(marker_corners[0], axis=0)
            cx, cy = int(center[0]), int(center[1])
            cv2.circle(output, (cx, cy), 4, (0, 255, 0), -1)
            cv2.putText(
                output,
                f"id={int(marker_id)}",
                (cx + 8, cy - 8),
                cv2.FONT_HERSHEY_SIMPLEX,
                0.6,
                (0, 255, 0),
                2,
                cv2.LINE_AA,
            )
    return output


def main() -> int:
    parser = argparse.ArgumentParser(description="Temporary standalone ArUco viewer using the real VisionSystem.")
    parser.add_argument("--area", default=None, help="Optional active work area id, e.g. spray or pickup.")
    parser.add_argument("--raw", action="store_true", help="Use raw mode instead of corrected frame.")
    parser.add_argument("--window", default="Vision ArUco Test", help="OpenCV window title.")
    args = parser.parse_args()

    vision = _build_vision_service(args.area)
    vision.set_raw_mode(args.raw)
    vision.update_settings({"Aruco": {"Enable detection": True}})

    vision.start()
    print("Vision started. Press 'q' or ESC to quit.")
    try:
        time.sleep(1.0)
        while True:
            frame = vision.get_latest_frame()
            if frame is None or not isinstance(frame, np.ndarray) or frame.size == 0:
                time.sleep(0.05)
                continue

            corners, ids, _debug_image = vision.detect_aruco_markers(frame)
            display = _draw_markers(frame, corners, ids)
            count = 0 if ids is None else len(ids)
            cv2.putText(
                display,
                f"markers={count}",
                (12, 28),
                cv2.FONT_HERSHEY_SIMPLEX,
                0.8,
                (0, 255, 255),
                2,
                cv2.LINE_AA,
            )
            cv2.imshow(args.window, display)
            key = cv2.waitKey(1) & 0xFF
            if key in (27, ord("q")):
                break
    finally:
        vision.stop()
        cv2.destroyAllWindows()
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
