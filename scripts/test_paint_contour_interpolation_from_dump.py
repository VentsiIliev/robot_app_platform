from __future__ import annotations

import argparse
import os
import sys
import time
from datetime import datetime
from pathlib import Path
from types import SimpleNamespace

import cv2
import numpy as np


REPO_ROOT = Path(__file__).resolve().parents[1]
os.environ.setdefault("MPLCONFIGDIR", "/tmp/matplotlib-robot-app-platform")
if str(REPO_ROOT) not in sys.path:
    sys.path.insert(0, str(REPO_ROOT))

from src.robot_systems.paint.processes.paint.plan.paint_contour_interpolation import (
    PaintContourInterpolation,
    PaintContourInterpolationConfig,
)


WINDOW_NAME = "Paint Contour Interpolation"
BUTTON_RECT = (16, 16, 176, 58)
DEFAULT_OUTPUT_DIR = REPO_ROOT / "src" / "bootstrap" / "debug_plots"


class CaptureButton:
    def __init__(self) -> None:
        self.requested = False

    def on_mouse(self, event, x, y, _flags, _param) -> None:
        if event != cv2.EVENT_LBUTTONUP:
            return
        x0, y0, x1, y1 = BUTTON_RECT
        if x0 <= int(x) <= x1 and y0 <= int(y) <= y1:
            self.requested = True


def main() -> int:
    parser = argparse.ArgumentParser(
        description=(
            "Start the paint vision system, show the live frame, and run the "
            "standalone contour interpolation when the on-screen Capture button is pressed."
        )
    )
    parser.add_argument("--active-area", default="paint", help="Work area id to activate before starting vision.")
    parser.add_argument("--output-dir", type=Path, default=DEFAULT_OUTPUT_DIR)
    parser.add_argument(
        "--anchor-spacing-mm",
        type=float,
        default=0.0,
        help="Optional support-point spacing. 0 disables resampling, which is the correct default for pixel-space contours.",
    )
    parser.add_argument(
        "--execution-spacing-mm",
        type=float,
        default=0.0,
        help="Optional output spacing. 0 disables resampling, which is the correct default for pixel-space contours.",
    )
    parser.add_argument("--straight-cleanup-distance-mm", type=float, default=0.35)
    parser.add_argument("--straight-cleanup-turn-deg", type=float, default=3.0)
    parser.add_argument("--straight-cleanup-passes", type=int, default=6)
    parser.add_argument("--curvature-preserve-window", type=int, default=3)
    parser.add_argument("--curvature-preserve-total-deg", type=float, default=8.0)
    parser.add_argument("--corner-keep-turn-deg", type=float, default=12.0)
    parser.add_argument("--sharp-boundary-deg", type=float, default=45.0)
    parser.add_argument("--rz-mode", default="path_tangent", choices=("path_tangent", "constant"))
    parser.add_argument("--no-save", action="store_true", help="Do not save captured overlay images.")
    args = parser.parse_args()

    config = PaintContourInterpolationConfig(
        units="px",
        anchor_spacing_mm=args.anchor_spacing_mm,
        execution_spacing_mm=args.execution_spacing_mm,
        straight_cleanup_distance_mm=args.straight_cleanup_distance_mm,
        straight_cleanup_turn_deg=args.straight_cleanup_turn_deg,
        straight_cleanup_passes=args.straight_cleanup_passes,
        curvature_preserve_window=args.curvature_preserve_window,
        curvature_preserve_total_deg=args.curvature_preserve_total_deg,
        corner_keep_turn_deg=args.corner_keep_turn_deg,
        sharp_boundary_deg=args.sharp_boundary_deg,
        rz_mode=args.rz_mode,
    )
    interpolator = PaintContourInterpolation(config)
    vision_service = _build_paint_vision_service(active_area=args.active_area)
    button = CaptureButton()

    args.output_dir.mkdir(parents=True, exist_ok=True)
    cv2.namedWindow(WINDOW_NAME, cv2.WINDOW_NORMAL)
    cv2.setMouseCallback(WINDOW_NAME, button.on_mouse)

    last_overlay: np.ndarray | None = None
    last_status = "Starting paint vision..."

    try:
        vision_service.start()
        last_status = "Live. Click Capture, press Space/C to capture, Q/Esc to quit."
        while True:
            frame = _latest_frame(vision_service)
            if frame is None:
                display = np.zeros((720, 960, 3), dtype=np.uint8)
                _draw_status(display, "No frame from vision service")
            else:
                display = _ensure_bgr(frame)

            if button.requested:
                button.requested = False
                captured = display.copy()
                contours = _latest_contours(vision_service)
                last_overlay, last_status = _capture_and_overlay(
                    frame=captured,
                    contours=contours,
                    interpolator=interpolator,
                    output_dir=args.output_dir,
                    save=not args.no_save,
                )

            shown = last_overlay.copy() if last_overlay is not None else display.copy()
            _draw_capture_button(shown)
            _draw_status(shown, last_status)
            cv2.imshow(WINDOW_NAME, shown)

            key = cv2.waitKey(30) & 0xFF
            if key in (27, ord("q"), ord("Q")):
                break
            if key in (32, ord("c"), ord("C")):
                button.requested = True
            if key in (ord("l"), ord("L")):
                last_overlay = None
                last_status = "Live. Click Capture, press Space/C to capture, Q/Esc to quit."
    finally:
        try:
            vision_service.stop()
        finally:
            cv2.destroyAllWindows()

    return 0


def _build_paint_vision_service(*, active_area: str):
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


def _latest_frame(vision_service) -> np.ndarray | None:
    try:
        frame = vision_service.get_latest_frame()
    except Exception:
        return None
    if frame is None:
        return None
    return np.asarray(frame)


def _latest_contours(vision_service) -> list[np.ndarray]:
    try:
        return list(vision_service.get_latest_contours())
    except Exception:
        return []


def _capture_and_overlay(
    *,
    frame: np.ndarray,
    contours: list[np.ndarray],
    interpolator: PaintContourInterpolation,
    output_dir: Path,
    save: bool,
) -> tuple[np.ndarray, str]:
    overlay = _ensure_bgr(frame).copy()
    contour = _pick_largest_contour(contours)
    if contour is None:
        return overlay, "Capture: no valid contour found"

    robot_path = _contour_to_pose_path(contour)
    result = interpolator.build(robot_path)
    raw_xy = np.asarray(result.raw_path, dtype=float)[:, :2]
    execution_xy = np.asarray(result.execution_path, dtype=float)[:, :2]
    cleaned_xy = (
        np.asarray(result.cleaned_anchor_xy, dtype=float).reshape(-1, 2)
        if result.cleaned_anchor_xy else np.empty((0, 2), dtype=float)
    )

    _draw_polyline(overlay, raw_xy, color=(0, 0, 255), thickness=2)
    _draw_polyline(overlay, execution_xy, color=(255, 0, 255), thickness=2)
    if len(cleaned_xy):
        _draw_points(overlay, cleaned_xy, color=(0, 255, 255), radius=2)

    status = (
        f"Captured raw={len(raw_xy)} cleaned={len(cleaned_xy)} "
        f"execution={len(execution_xy)} spacing={_spacing_summary(execution_xy)}px"
    )
    _draw_legend(overlay)
    if save:
        output = output_dir / f"paint_contour_interpolation_capture_{datetime.now().strftime('%Y%m%d_%H%M%S_%f')}.png"
        cv2.imwrite(str(output), overlay)
        status += f" saved={output}"
    print(status)
    return overlay, status


def _pick_largest_contour(contours: list[np.ndarray]) -> np.ndarray | None:
    best = None
    best_area = 0.0
    for contour in contours or []:
        try:
            points = np.asarray(contour, dtype=float).reshape(-1, 2)
        except Exception:
            continue
        if len(points) < 3:
            continue
        area = abs(float(cv2.contourArea(points.astype(np.float32).reshape(-1, 1, 2))))
        if area > best_area:
            best_area = area
            best = points
    return best


def _contour_to_pose_path(contour: np.ndarray) -> list[list[float]]:
    points = np.asarray(contour, dtype=float).reshape(-1, 2)
    if len(points) >= 3 and float(np.linalg.norm(points[0] - points[-1])) > 1e-9:
        points = np.vstack([points, points[0]])
    return [[float(x), float(y), 0.0, 0.0, 0.0, 0.0] for x, y in points]


def _ensure_bgr(frame: np.ndarray) -> np.ndarray:
    image = np.asarray(frame)
    if image.ndim == 2:
        return cv2.cvtColor(image, cv2.COLOR_GRAY2BGR)
    if image.ndim == 3 and image.shape[2] == 4:
        return cv2.cvtColor(image, cv2.COLOR_BGRA2BGR)
    if image.ndim == 3 and image.shape[2] == 3:
        return image.copy()
    return np.zeros((720, 960, 3), dtype=np.uint8)


def _draw_capture_button(frame: np.ndarray) -> None:
    x0, y0, x1, y1 = BUTTON_RECT
    cv2.rectangle(frame, (x0, y0), (x1, y1), (32, 32, 32), thickness=-1)
    cv2.rectangle(frame, (x0, y0), (x1, y1), (255, 255, 255), thickness=1)
    cv2.putText(frame, "Capture", (x0 + 24, y0 + 29), cv2.FONT_HERSHEY_SIMPLEX, 0.7, (255, 255, 255), 2)


def _draw_status(frame: np.ndarray, text: str) -> None:
    y = frame.shape[0] - 20
    cv2.rectangle(frame, (0, max(0, y - 26)), (frame.shape[1], frame.shape[0]), (0, 0, 0), thickness=-1)
    cv2.putText(frame, text[:180], (12, y), cv2.FONT_HERSHEY_SIMPLEX, 0.55, (255, 255, 255), 1, cv2.LINE_AA)


def _draw_legend(frame: np.ndarray) -> None:
    rows = [("raw", (0, 0, 255)), ("interpolated", (255, 0, 255)), ("cleaned anchors", (0, 255, 255))]
    x = 16
    y = 78
    for label, color in rows:
        cv2.line(frame, (x, y), (x + 28, y), color, thickness=3)
        cv2.putText(frame, label, (x + 36, y + 5), cv2.FONT_HERSHEY_SIMPLEX, 0.5, color, 1, cv2.LINE_AA)
        y += 24


def _draw_polyline(frame: np.ndarray, xy: np.ndarray, *, color: tuple[int, int, int], thickness: int) -> None:
    if len(xy) < 2:
        return
    points = np.round(xy).astype(np.int32).reshape(-1, 1, 2)
    cv2.polylines(frame, [points], isClosed=False, color=color, thickness=thickness, lineType=cv2.LINE_AA)


def _draw_points(frame: np.ndarray, xy: np.ndarray, *, color: tuple[int, int, int], radius: int) -> None:
    for point in np.round(xy).astype(np.int32):
        cv2.circle(frame, (int(point[0]), int(point[1])), radius, color, thickness=-1, lineType=cv2.LINE_AA)


def _spacing_summary(xy: np.ndarray) -> str:
    if len(xy) < 2:
        return "min=0.000 mean=0.000 max=0.000"
    lengths = np.linalg.norm(np.diff(xy, axis=0), axis=1)
    positive = lengths[lengths > 1e-9]
    if len(positive) == 0:
        return "min=0.000 mean=0.000 max=0.000"
    return (
        f"min={float(np.min(positive)):.3f} "
        f"mean={float(np.mean(positive)):.3f} "
        f"max={float(np.max(positive)):.3f}"
    )


if __name__ == "__main__":
    raise SystemExit(main())
