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


def _draw_crosshair(frame: np.ndarray, color: tuple[int, int, int], size: int, thickness: int) -> np.ndarray:
    output = frame.copy()
    height, width = output.shape[:2]
    cx = width // 2
    cy = height // 2

    cv2.line(output, (cx - size, cy), (cx + size, cy), color, thickness, cv2.LINE_AA)
    cv2.line(output, (cx, cy - size), (cx, cy + size), color, thickness, cv2.LINE_AA)
    cv2.circle(output, (cx, cy), max(2, thickness + 1), color, -1, cv2.LINE_AA)
    return output


def main() -> int:
    parser = argparse.ArgumentParser(description="Show live vision feed with a center crosshair.")
    parser.add_argument("--area", default=None, help="Active work area id.")
    parser.add_argument("--raw", action="store_true", help="Use raw frame instead of corrected frame.")
    parser.add_argument("--window", default="Live Camera Crosshair", help="OpenCV window title.")
    parser.add_argument("--crosshair-size", type=int, default=20, help="Half-length of the crosshair in pixels.")
    parser.add_argument("--thickness", type=int, default=1, help="Crosshair line thickness.")
    args = parser.parse_args()

    vision = _build_vision_service(args.area)
    vision.set_raw_mode(args.raw)
    vision.start()

    print("Press 'q' or ESC to quit.")
    last_frame = None

    try:
        time.sleep(1.0)
        while True:
            frame = vision.get_latest_raw_frame() if args.raw else vision.get_latest_frame()
            if frame is None or not isinstance(frame, np.ndarray) or frame.size == 0:
                time.sleep(0.02)
                continue
            if frame is last_frame:
                time.sleep(0.01)
                continue
            last_frame = frame

            display = _draw_crosshair(
                frame,
                color=(0, 255, 255),
                size=max(4, int(args.crosshair_size)),
                thickness=max(1, int(args.thickness)),
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
