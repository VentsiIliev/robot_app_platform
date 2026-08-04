from __future__ import annotations

import logging
import os
from pathlib import Path

import numpy as np

from src.engine.robot.path_preparation import config as path_prep_config
from src.engine.robot.path_preparation.pixel_to_mm import (
    GeometryPpmAnchorStrategy,
    GeometryScaleCache,
    HomographyResidualStrategy,
    PixelToMmContext,
)
from src.shared_contracts.events.process_events import ProcessState
from src.robot_systems.paint.applications.dashboard.dashboard_state import DashboardState
from src.robot_systems.paint.applications.dashboard.service.i_paint_dashboard_service import (
    ContourTransformDebugResult,
    IPaintDashboardService,
)


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
        self._geometry_scale_cache = GeometryScaleCache()
        self._geometry_ppm_strategy = GeometryPpmAnchorStrategy()
        self._homography_residual_strategy = HomographyResidualStrategy()
        self._logger = logging.getLogger(__name__)

    def get_process_id(self) -> str:
        return str(getattr(self._process.process_id, "value", self._process.process_id))

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
            raw_pixel_path, strategy_paths = self._transform_with_pixel_to_mm_strategies(largest)
        except Exception as exc:
            return ContourTransformDebugResult(False, f"Failed to transform latest contour: {exc}")

        min_rects = [self._minimum_area_rect_xy(item["path"]) for item in strategy_paths]
        try:
            from src.engine.robot.path_interpolation.new_interpolation.debug_plotting import (
                plot_pixel_to_mm_strategy_comparison,
            )

            image_path = plot_pixel_to_mm_strategy_comparison(
                raw_pixel_path,
                strategy_paths,
                min_rects_mm=min_rects,
                save_dir=self._debug_plot_dir(),
            )
        except Exception as exc:
            return ContourTransformDebugResult(False, f"Failed to create contour transform plot: {exc}")

        if not image_path:
            return ContourTransformDebugResult(False, "Contour transform plot was not created.")

        message = f"Saved contour transform debug plot to {image_path}"
        rect_lines = []
        for item, rect_info in zip(strategy_paths, min_rects):
            if rect_info is None:
                rect_lines.append(f"{item['name']}: min rect unavailable")
                continue
            rect_lines.append(
                f"{item['name']}: {rect_info['length_mm']:.1f} x {rect_info['width_mm']:.1f} mm "
                f"(angle {rect_info['angle_deg']:.1f} deg)"
            )
        if rect_lines:
            message = f"{message}\n" + "\n".join(rect_lines)

        return ContourTransformDebugResult(True, message, image_path)

    def _transform_with_pixel_to_mm_strategies(self, contour: np.ndarray) -> tuple[list[list[float]], list[dict]]:
        points = np.asarray(contour, dtype=float).reshape(-1, 2)
        raw_pixel_path = [[float(px), float(py)] for px, py in points]

        resolver = self._current_resolver()
        if resolver is None:
            raise RuntimeError("Vision resolver is not available.")

        context = PixelToMmContext(
            base_z=0.0,
            rz_offset=0.0,
            rx=180.0,
            ry=0.0,
            target_point_name=self._target_point_name,
            calibration_frame_name=self._frame_name,
            mode_name=path_prep_config.PIXEL_TO_MM_MODE_GEOMETRY_PPM_ANCHOR,
            logger=self._logger,
            geometry_scale_cache=self._geometry_scale_cache,
        )

        strategy_paths: list[dict] = []
        ppm_result = self._geometry_ppm_strategy.convert(points, resolver=resolver, context=context)
        if ppm_result is None:
            ppm_path = []
        else:
            _, ppm_xy = ppm_result
            ppm_path = self._xy_to_pose_path(ppm_xy)
        strategy_paths.append({"name": "Geometry PPM Anchor", "path": ppm_path})

        residual_context = PixelToMmContext(
            base_z=0.0,
            rz_offset=0.0,
            rx=180.0,
            ry=0.0,
            target_point_name=self._target_point_name,
            calibration_frame_name=self._frame_name,
            mode_name=path_prep_config.PIXEL_TO_MM_MODE_HOMOGRAPHY_RESIDUAL,
            logger=self._logger,
            geometry_scale_cache=self._geometry_scale_cache,
        )
        _, residual_xy = self._homography_residual_strategy.convert(points, resolver=resolver, context=residual_context)
        strategy_paths.append({"name": "Homography Residual", "path": self._xy_to_pose_path(residual_xy)})
        return raw_pixel_path, strategy_paths

    def _current_resolver(self):
        if self._resolver_getter is None:
            return None
        return self._resolver_getter()

    @staticmethod
    def _xy_to_pose_path(points: list[tuple[float, float]]) -> list[list[float]]:
        return [
            [float(x), float(y), 0.0, 180.0, 0.0, 0.0]
            for x, y in points
        ]

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
        if process_state == ProcessState.RUNNING.value:
            return ["Painting workpiece"]
        if process_state == ProcessState.PAUSED.value:
            return ["Paint job paused"]
        if process_state == ProcessState.STOPPED.value:
            return ["Paint job stopped"]
        if process_state == ProcessState.ERROR.value:
            return ["Resolve error before restart"]
        return ["Waiting for start"]
