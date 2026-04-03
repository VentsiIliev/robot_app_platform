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
from src.robot_systems.paint.paint_robot_system import PaintRobotSystem

GRID_IDS = {
    1:  "TL", 8:  "TC", 13:  "TR",
    132: "ML", 140: "MC", 164: "MR",
    297: "BL", 321: "BC", 262: "BR",
}

_GRID_COLOR  = (0, 200, 255)
_OTHER_COLOR = (100, 100, 100)


def _build_vision_service(active_area: str | None) -> VisionService:
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
    if active_area is not None:
        work_area_service.set_active_area_id(active_area)

    settings_repo = settings_service.get_repo(CommonSettingsID.VISION_CAMERA_SETTINGS)
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


def _draw_markers(frame: np.ndarray, corners, ids) -> np.ndarray:
    output = frame.copy()
    if ids is None or len(ids) == 0:
        return output

    flat_ids  = ids.flatten()
    grid_mask = np.array([mid in GRID_IDS for mid in flat_ids])

    grid_corners  = [c for c, m in zip(corners, grid_mask) if m]
    other_corners = [c for c, m in zip(corners, grid_mask) if not m]
    grid_ids_arr  = ids[grid_mask]
    other_ids_arr = ids[~grid_mask]

    if other_corners:
        cv2.aruco.drawDetectedMarkers(output, other_corners, other_ids_arr)

    if grid_corners:
        cv2.aruco.drawDetectedMarkers(output, grid_corners, grid_ids_arr, _GRID_COLOR)
        for mc, mid in zip(grid_corners, grid_ids_arr.flatten()):
            center = np.mean(mc[0], axis=0)
            cx, cy = int(center[0]), int(center[1])
            cv2.circle(output, (cx, cy), 6, _GRID_COLOR, -1)
            cv2.putText(output, f"{GRID_IDS[mid]}({mid})", (cx + 10, cy - 10),
                        cv2.FONT_HERSHEY_SIMPLEX, 0.65, _GRID_COLOR, 2, cv2.LINE_AA)

    detected_grid = {mid: np.mean(mc[0], axis=0)
                     for mc, mid in zip(grid_corners, grid_ids_arr.flatten())}
    row_order = [[51, 57, 63], [183, 189, 195], [315, 321, 327]]
    for row in row_order:
        pts = [detected_grid[mid] for mid in row if mid in detected_grid]
        for a, b in zip(pts, pts[1:]):
            cv2.line(output, (int(a[0]), int(a[1])), (int(b[0]), int(b[1])),
                     _GRID_COLOR, 1, cv2.LINE_AA)
    for col_idx in range(3):
        pts = [detected_grid[row[col_idx]] for row in row_order if row[col_idx] in detected_grid]
        for a, b in zip(pts, pts[1:]):
            cv2.line(output, (int(a[0]), int(a[1])), (int(b[0]), int(b[1])),
                     _GRID_COLOR, 1, cv2.LINE_AA)

    return output


def _draw_status_bar(frame: np.ndarray, total: int, in_grid: int) -> np.ndarray:
    BAR_H = 40
    w = frame.shape[1]
    cv2.rectangle(frame, (0, 0), (w, BAR_H), (20, 20, 20), -1)
    left  = f"total markers: {total}"
    right = f"grid: {in_grid} / 9"
    font, scale, thick = cv2.FONT_HERSHEY_SIMPLEX, 0.75, 2
    (rw, _), _ = cv2.getTextSize(right, font, scale, thick)
    cv2.putText(frame, left,  (12, 28),           font, scale, _GRID_COLOR, thick, cv2.LINE_AA)
    cv2.putText(frame, right, (w - rw - 12, 28),  font, scale, _GRID_COLOR, thick, cv2.LINE_AA)
    return frame


def main() -> int:
    parser = argparse.ArgumentParser(description="ArUco viewer with 3×3 homography grid highlight.")
    parser.add_argument("--area",   default=None,          help="Active work area id.")
    parser.add_argument("--raw",    action="store_true",   help="Use raw frame instead of corrected.")
    parser.add_argument("--window", default="ArUco Grid View", help="OpenCV window title.")
    args = parser.parse_args()

    vision = _build_vision_service(args.area)
    vision.set_raw_mode(args.raw)
    vision.update_settings({"Aruco": {"Enable detection": True}})
    vision.start()

    print(f"Grid IDs: {sorted(GRID_IDS)}")
    print("Press 'q' or ESC to quit.")

    try:
        time.sleep(1.0)
        while True:
            frame = vision.get_latest_frame()
            if frame is None or not isinstance(frame, np.ndarray) or frame.size == 0:
                time.sleep(0.05)
                continue

            corners, ids, _ = vision.detect_aruco_markers(frame)
            display = _draw_markers(frame, corners, ids)

            total   = 0 if ids is None else len(ids)
            in_grid = 0 if ids is None else sum(1 for mid in ids.flatten() if mid in GRID_IDS)
            display = _draw_status_bar(display, total, in_grid)

            cv2.imshow(args.window, display)
            if cv2.waitKey(1) & 0xFF in (27, ord("q")):
                break
    finally:
        vision.stop()
        cv2.destroyAllWindows()
    return 0


if __name__ == "__main__":
    raise SystemExit(main())