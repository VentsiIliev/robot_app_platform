from __future__ import annotations

import logging
import os
from dataclasses import replace
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
from src.robot_systems.paint.applications.dashboard.dashboard_state import DashboardCardState, DashboardState
from src.robot_systems.paint.applications.dashboard.service.i_paint_dashboard_service import (
    ContourTransformDebugResult,
    DashboardCommandResult,
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
        robot_service=None,
        vision_service=None,
        vacuum_pump=None,
        fan_control=None,
        paint_process_config_service=None,
        target_point_name: str = "camera",
        frame_name: str = "calibration",
    ) -> None:
        self._process = process
        self._capture_snapshot_service = capture_snapshot_service
        self._path_preparation_service = path_preparation_service
        self._resolver_getter = resolver_getter
        self._robot_service = robot_service
        self._vision_service = vision_service
        self._paint_process_config_service = paint_process_config_service
        self._auxiliary_devices = {
            "pump": vacuum_pump,
            "fan": fan_control,
        }
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
            card_states={
                1: self._robot_status_card(),
                2: self._vision_status_card(),
                3: self._process_status_card(process_state),
            },
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

    def get_unmatched_paint_settings(self) -> dict[str, float | bool]:
        service = self._paint_process_config_service
        if service is None:
            return {}
        config = service.get_snapshot()
        return {
            "velocity_percent": float(config.default_paint_velocity_percent),
            "acceleration_percent": float(config.default_paint_acceleration_percent),
            "offset_mm": float(config.default_paint_offset_mm),
            "matching_enabled": bool(config.enable_workpiece_matching),
        }

    def save_unmatched_paint_settings(
        self,
        velocity_percent: float,
        acceleration_percent: float,
        offset_mm: float,
    ) -> DashboardCommandResult:
        service = self._paint_process_config_service
        if service is None:
            return DashboardCommandResult(False, "Paint process settings are not available.")
        process_state = str(getattr(getattr(self._process, "state", None), "value", ""))
        if process_state in {ProcessState.RUNNING.value, ProcessState.PAUSED.value}:
            return DashboardCommandResult(
                False,
                "Stop the paint process before changing unmatched paint settings.",
            )
        velocity = float(velocity_percent)
        acceleration = float(acceleration_percent)
        offset = float(offset_mm)
        if not 0.0 < velocity <= 100.0 or not 0.0 < acceleration <= 100.0:
            return DashboardCommandResult(
                False,
                "Velocity and acceleration must be greater than 0 and at most 100 percent.",
            )
        try:
            updated = replace(
                service.get_snapshot(),
                default_paint_velocity_percent=velocity,
                default_paint_acceleration_percent=acceleration,
                default_paint_offset_mm=offset,
            )
            service.save(updated)
        except Exception as exc:
            self._logger.exception("Could not save unmatched paint settings")
            return DashboardCommandResult(False, f"Could not save unmatched paint settings: {exc}")
        return DashboardCommandResult(True, "Unmatched paint settings saved.")

    def relieve_cable(self) -> DashboardCommandResult:
        if self._robot_service is None:
            return DashboardCommandResult(False, "Robot service is not available.")
        try:
            success = bool(self._robot_service.unwind_joint6())
        except Exception as exc:
            self._logger.exception("Dashboard cable relief failed")
            return DashboardCommandResult(False, f"Cable relief failed: {exc}")
        return DashboardCommandResult(
            success,
            "Cable relief completed." if success else "Cable relief command was rejected.",
        )

    def get_auxiliary_states(self) -> dict[str, bool]:
        states = {}
        for device_id, device in self._auxiliary_devices.items():
            if device is None:
                continue
            try:
                # The dashboard state controls button availability, not whether
                # the output is currently ON.  Raw fan/pump read_state() values
                # are active-state booleans, so using them here disabled the OFF
                # button whenever the device was correctly switched off.
                health_getter = getattr(device, "is_healthy", None)
                states[device_id] = bool(health_getter()) if callable(health_getter) else True
            except Exception:
                self._logger.exception("Could not read %s state", device_id)
        return states

    def set_auxiliary_enabled(self, device_id: str, enabled: bool) -> DashboardCommandResult:
        device = self._auxiliary_devices.get(device_id)
        if device is None:
            self._logger.error(
                "[DASHBOARD_AUX] %s command=%s rejected: device unavailable",
                device_id,
                "ON" if enabled else "OFF",
            )
            return DashboardCommandResult(False, f"{device_id.title()} is not available.", device_id)
        try:
            self._logger.info(
                "[DASHBOARD_AUX] Sending %s command to %s (%s)",
                "ON" if enabled else "OFF",
                device_id,
                type(device).__name__,
            )
            result = device.turn_on() if enabled else device.turn_off()
            success = result is not False
            self._logger.info(
                "[DASHBOARD_AUX] %s command=%s returned=%r success=%s",
                device_id,
                "ON" if enabled else "OFF",
                result,
                success,
            )
        except Exception as exc:
            self._logger.exception("[DASHBOARD_AUX] Could not switch %s", device_id)
            return DashboardCommandResult(False, f"Could not switch {device_id}: {exc}", device_id)
        state = "ON" if enabled else "OFF"
        return DashboardCommandResult(success, f"{device_id.title()} switched {state}.", device_id, enabled)

    def _robot_status_card(self) -> DashboardCardState:
        robot = self._robot_service
        if robot is None:
            return DashboardCardState("Robot Status", "UNAVAILABLE", "Robot service is not registered")
        try:
            details_getter = getattr(robot, "get_connection_details", None)
            details = details_getter() if callable(details_getter) else {}
            details = details if isinstance(details, dict) else {}
            connection_state_getter = getattr(robot, "get_connection_state", None)
            connection_state = str(details.get("state") or "").lower()
            if callable(connection_state_getter):
                live_connection_state = connection_state_getter()
                if isinstance(live_connection_state, str) and live_connection_state.strip():
                    connection_state = live_connection_state.strip().lower()
            if connection_state == "disconnected":
                note = self._robot_connection_note(details.get("last_error"))
                return DashboardCardState("Robot Status", "DISCONNECTED", note)
            if connection_state == "starting":
                startup = details.get("startup")
                note = self._robot_startup_note(startup if isinstance(startup, dict) else {})
                return DashboardCardState("Robot Status", "STARTING", note)
            if connection_state in {"error", "fault"}:
                note = self._robot_connection_note(details.get("last_error"))
                return DashboardCardState("Robot Status", "ERROR", note)

            drive_status_getter = getattr(robot, "get_drive_status", None)
            drive_status = drive_status_getter() if callable(drive_status_getter) else {}
            drive_status = drive_status if isinstance(drive_status, dict) else {}
            drive_warning = self._robot_drive_warning(drive_status)
            if drive_warning:
                return DashboardCardState("Robot Status", "DRIVE NOT READY", drive_warning)

            state_getter = getattr(robot, "get_state", None)
            state = str(connection_state or (state_getter() if callable(state_getter) else "unknown"))
            healthy_getter = getattr(robot, "is_healthy", None)
            healthy = bool(healthy_getter()) if callable(healthy_getter) else state not in {
                "disconnected",
                "error",
                "fault",
            }
        except Exception as exc:
            return DashboardCardState("Robot Status", "ERROR", self._robot_connection_note(exc))
        value = state.upper() if state else "UNKNOWN"
        note = "Robot service healthy" if healthy else "Robot needs attention"
        return DashboardCardState("Robot Status", value, note)

    @staticmethod
    def _robot_connection_note(last_error: object) -> str:
        message = str(last_error or "").strip()
        if not message:
            return "Robot bridge is disconnected"
        lowered = message.lower()
        if "connection refused" in lowered or "failed to establish a new connection" in lowered:
            return "ROS2 bridge is not reachable"
        if "timed out" in lowered or "timeout" in lowered:
            return "ROS2 bridge health check timed out"
        if "max retries exceeded" in lowered:
            return "ROS2 bridge is not responding"
        return "Robot bridge is disconnected"

    @staticmethod
    def _robot_startup_note(startup: dict) -> str:
        message = str(startup.get("message") or "").strip()
        if message:
            return message
        phase = str(startup.get("phase") or "").strip()
        if phase:
            return f"Runtime startup phase: {phase}"
        return "Robot runtime is starting"

    @staticmethod
    def _robot_drive_warning(drive_status: dict) -> str:
        if not drive_status:
            return ""
        if drive_status.get("success") is False:
            return PaintDashboardService._robot_drive_error_note(drive_status.get("error"))

        motion_allowed = drive_status.get("motion_allowed_by_drive_enable")
        actual_enabled = drive_status.get("actual_enabled")
        requested_enabled = drive_status.get("requested_enabled")
        if motion_allowed is False:
            if requested_enabled is False:
                return "Robot drives are disabled"
            if actual_enabled is False:
                return PaintDashboardService._robot_drive_status_note(drive_status)
            return "Robot drives are not motion-ready"
        return ""

    @staticmethod
    def _robot_drive_status_note(drive_status: dict) -> str:
        status_state = drive_status.get("status_state")
        if isinstance(status_state, (list, tuple)) and status_state:
            states = sorted({str(state) for state in status_state if str(state)})
            if states:
                return "Drive state: " + ", ".join(states[:3])
        state = str(drive_status.get("state") or "").strip()
        if state:
            return f"Drive state: {state}"
        return "EtherCAT/drives are not operation enabled"

    @staticmethod
    def _robot_drive_error_note(error: object) -> str:
        message = str(error or "").strip()
        lowered = message.lower()
        if "sdo" in lowered or "ethercat" in lowered:
            return "EtherCAT communication error"
        if "timed out" in lowered or "timeout" in lowered:
            return "Drive status request timed out"
        if "connection refused" in lowered or "failed to establish a new connection" in lowered:
            return "ROS2 bridge is not reachable"
        return "Drive status is unavailable"

    def _vision_status_card(self) -> DashboardCardState:
        vision = self._vision_service
        if vision is None:
            return DashboardCardState("Vision Status", "UNAVAILABLE", "Vision service is not registered")
        try:
            healthy_getter = getattr(vision, "is_healthy", None)
            details_getter = getattr(vision, "get_health_details", None)
            details = details_getter() if callable(details_getter) else {}
            details = details if isinstance(details, dict) else {}
            health_ok = bool(healthy_getter()) if callable(healthy_getter) else True
            healthy = bool(details.get("healthy", health_ok))
            value = "ONLINE" if healthy else "OFFLINE"
            note = str(
                details.get("message")
                or ("Vision service healthy" if healthy else "Vision service is stopped or unhealthy")
            )
        except Exception as exc:
            return DashboardCardState("Vision Status", "ERROR", f"Could not read vision state: {exc}")
        return DashboardCardState("Vision Status", value, note)

    @staticmethod
    def _process_status_card(process_state: str) -> DashboardCardState:
        value = str(process_state or "idle").upper()
        note = PaintDashboardService._status_lines(process_state)[0]
        return DashboardCardState("Process Status", value, note)

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
