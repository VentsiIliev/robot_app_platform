from __future__ import annotations

import os
from pathlib import Path

import numpy as np

from src.shared_contracts.events.process_events import ProcessState
from src.robot_systems.paint.applications.dashboard.dashboard_state import DashboardState
from src.robot_systems.paint.applications.dashboard.service.i_paint_dashboard_service import (
    ContourTransformDebugResult,
    IPaintDashboardService,
)

_REFERENCE_DXF_PATH = "scripts/dxf/part2_venci.dxf"


class PaintDashboardService(IPaintDashboardService):

    def __init__(
        self,
        process,
        *,
        capture_snapshot_service=None,
        path_preparation_service=None,
        resolver_getter=None,
        target_point_name: str = "camera",
        frame_name: str = "calibration",
    ) -> None:
        self._process = process
        self._capture_snapshot_service = capture_snapshot_service
        self._path_preparation_service = path_preparation_service
        self._resolver_getter = resolver_getter
        self._target_point_name = str(target_point_name or "camera").strip().lower()
        self._frame_name = str(frame_name or "calibration").strip().lower()

    def get_process_id(self) -> str:
        return str(self._process.process_id)

    def load_state(self) -> DashboardState:
        process_state = self._process.state.value
        is_paused = self._process.state == ProcessState.PAUSED
        return DashboardState(
            process_state=process_state,
            mode_label="Paint Mode",
            active_job_label=self._active_job_label(process_state),
            status_lines=self._status_lines(process_state),
            can_start=process_state in (ProcessState.IDLE.value, ProcessState.STOPPED.value),
            can_stop=process_state in (ProcessState.RUNNING.value, ProcessState.PAUSED.value),
            can_pause=process_state in (ProcessState.RUNNING.value, ProcessState.PAUSED.value),
            pause_label="Resume" if is_paused else "Pause",
        )

    def start(self) -> None:
        self._process.start()

    def stop(self) -> None:
        self._process.stop()

    def pause(self) -> None:
        self._process.pause()

    def resume(self) -> None:
        self._process.resume()

    def reset_errors(self) -> None:
        self._process.reset_errors()

    def capture_latest_contour_transform_debug(self) -> ContourTransformDebugResult:
        if self._capture_snapshot_service is None:
            return ContourTransformDebugResult(False, "Capture snapshot service is not available.")

        snapshot = self._capture_snapshot_service.capture_snapshot(source="paint_dashboard")
        largest = self._pick_largest_contour(snapshot.contours)
        if largest is None:
            return ContourTransformDebugResult(False, "No usable contour detected.")

        try:
            raw_pixel_path, camera_path, homography_path = self._transform_like_pick_target(largest)
        except Exception as exc:
            return ContourTransformDebugResult(False, f"Failed to transform latest contour: {exc}")

        rect_info = self._minimum_area_rect_xy(camera_path)
        dxf_rect_info = self._reference_dxf_minimum_area_rect()
        measurement_text = self._format_min_rect_comparison(rect_info, dxf_rect_info)
        try:
            from src.engine.robot.path_interpolation.new_interpolation.debug_plotting import (
                plot_pixel_to_mm_debug,
            )

            image_path = plot_pixel_to_mm_debug(
                [camera_path],
                raw_pixel_paths=[raw_pixel_path],
                homography_paths=[homography_path],
                min_rects_mm=[rect_info],
                measurement_text=measurement_text,
                save_dir=self._debug_plot_dir(),
            )
        except Exception as exc:
            return ContourTransformDebugResult(False, f"Failed to create contour transform plot: {exc}")

        if not image_path:
            return ContourTransformDebugResult(False, "Contour transform plot was not created.")

        message = f"Saved contour transform debug plot to {image_path}"
        if rect_info is not None:
            message = (
                f"{message}\n"
                f"Min rect: {rect_info['length_mm']:.1f} x {rect_info['width_mm']:.1f} mm "
                f"(angle {rect_info['angle_deg']:.1f} deg)"
            )
        if dxf_rect_info is not None:
            message = (
                f"{message}\n"
                f"DXF rect: {dxf_rect_info['length_mm']:.1f} x {dxf_rect_info['width_mm']:.1f} mm "
                f"({_REFERENCE_DXF_PATH})"
            )
        if rect_info is not None and dxf_rect_info is not None:
            message = (
                f"{message}\n"
                f"Delta: {rect_info['length_mm'] - dxf_rect_info['length_mm']:+.1f} x "
                f"{rect_info['width_mm'] - dxf_rect_info['width_mm']:+.1f} mm"
            )

        return ContourTransformDebugResult(True, message, image_path)

    def _transform_like_pick_target(self, contour: np.ndarray) -> tuple[list[list[float]], list[list[float]], list[list[float]]]:
        resolver = self._resolver_getter() if callable(self._resolver_getter) else None
        if resolver is None:
            raise RuntimeError("Vision target resolver is not available.")

        from src.engine.robot.targeting import VisionPoseRequest

        target_point = resolver.registry.by_name(self._target_point_name)
        points = np.asarray(contour, dtype=float).reshape(-1, 2)
        raw_pixel_path: list[list[float]] = []
        camera_path: list[list[float]] = []
        homography_path: list[list[float]] = []

        for px, py in points:
            raw_pixel_path.append([float(px), float(py)])
            result = resolver.resolve(
                VisionPoseRequest(
                    x_pixels=float(px),
                    y_pixels=float(py),
                    z_mm=0.0,
                    rz_degrees=0.0,
                    rx_degrees=180.0,
                    ry_degrees=0.0,
                ),
                target_point,
                frame=self._frame_name,
            )
            camera_path.append([
                float(result.final_xy[0]),
                float(result.final_xy[1]),
                float(result.z),
                float(result.rx),
                float(result.ry),
                float(result.rz),
            ])

        homography_xy = self._homography_only_xy(resolver, points)
        for x, y in homography_xy:
            homography_path.append([float(x), float(y), 0.0, 180.0, 0.0, 0.0])

        return raw_pixel_path, camera_path, homography_path

    @staticmethod
    def _homography_only_xy(resolver, points: np.ndarray) -> np.ndarray:
        base_transformer = getattr(resolver, "_base", None)
        model = getattr(base_transformer, "_model", None)
        homography_matrix = getattr(model, "homography_matrix", None)
        if homography_matrix is None:
            return np.empty((0, 2), dtype=float)

        import cv2

        pts = np.asarray(points, dtype=np.float32).reshape(-1, 1, 2)
        return cv2.perspectiveTransform(
            pts,
            np.asarray(homography_matrix, dtype=np.float64).reshape(3, 3),
        ).reshape(-1, 2)

    @staticmethod
    def _minimum_area_rect_xy(path: list[list[float]]) -> dict | None:
        points = np.asarray(path, dtype=np.float32)
        if points.ndim != 2 or points.shape[0] < 3 or points.shape[1] < 2:
            return None

        import cv2

        contour_xy = np.ascontiguousarray(points[:, :2].reshape(-1, 1, 2), dtype=np.float32)
        center, size, angle_deg = cv2.minAreaRect(contour_xy)
        width_mm, height_mm = float(size[0]), float(size[1])
        if width_mm <= 0.0 or height_mm <= 0.0:
            return None

        corners = cv2.boxPoints((center, size, angle_deg)).astype(float)
        length_mm = max(width_mm, height_mm)
        short_width_mm = min(width_mm, height_mm)
        return {
            "center": [float(center[0]), float(center[1])],
            "corners": corners.tolist(),
            "length_mm": float(length_mm),
            "width_mm": float(short_width_mm),
            "angle_deg": float(angle_deg),
        }

    def _reference_dxf_minimum_area_rect(self) -> dict | None:
        dxf_path = self._repo_root() / _REFERENCE_DXF_PATH
        if not dxf_path.exists():
            return None

        try:
            from src.engine.cad import parse_dxf_to_geometry

            path = parse_dxf_to_geometry(str(dxf_path)).largest_closed_path()
        except Exception:
            return None
        return self._minimum_area_rect_xy([[float(x), float(y)] for x, y in path])

    @staticmethod
    def _format_min_rect_comparison(captured: dict | None, reference: dict | None) -> str:
        if captured is None and reference is None:
            return ""
        if captured is None:
            return (
                "Captured min rect: unavailable\n"
                f"DXF min rect: {reference['length_mm']:.1f} x {reference['width_mm']:.1f} mm"
            )
        if reference is None:
            return (
                f"Captured min rect: {captured['length_mm']:.1f} x {captured['width_mm']:.1f} mm\n"
                "DXF min rect: unavailable"
            )

        delta_length = captured["length_mm"] - reference["length_mm"]
        delta_width = captured["width_mm"] - reference["width_mm"]
        return (
            f"Captured min rect: {captured['length_mm']:.1f} x {captured['width_mm']:.1f} mm\n"
            f"DXF min rect: {reference['length_mm']:.1f} x {reference['width_mm']:.1f} mm\n"
            f"Delta: {delta_length:+.1f} x {delta_width:+.1f} mm"
        )

    @staticmethod
    def _pick_largest_contour(contours) -> np.ndarray | None:
        best = None
        best_area = 0.0
        for contour in contours or []:
            try:
                points = np.asarray(contour, dtype=float).reshape(-1, 2)
            except Exception:
                continue
            if len(points) < 3:
                continue
            area = abs(PaintDashboardService._polygon_area(points))
            if area > best_area:
                best_area = area
                best = points
        return best

    @staticmethod
    def _polygon_area(points: np.ndarray) -> float:
        x = points[:, 0]
        y = points[:, 1]
        return float(0.5 * abs(np.dot(x, np.roll(y, -1)) - np.dot(y, np.roll(x, -1))))

    @staticmethod
    def _debug_plot_dir() -> str:
        return os.path.normpath(str(PaintDashboardService._repo_root() / "src" / "bootstrap" / "debug_plots"))

    @staticmethod
    def _repo_root() -> Path:
        return Path(__file__).resolve().parents[6]

    @staticmethod
    def _active_job_label(process_state: str) -> str:
        if process_state == ProcessState.RUNNING.value:
            return "Paint job running"
        if process_state == ProcessState.PAUSED.value:
            return "Paint job paused"
        if process_state == ProcessState.STOPPED.value:
            return "Paint job stopped"
        if process_state == ProcessState.ERROR.value:
            return "Paint job error"
        return "No active job"

    @staticmethod
    def _status_lines(process_state: str) -> list[str]:
        return [
            f"Paint process state: {process_state}",
        ]
