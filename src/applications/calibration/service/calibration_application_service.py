import logging
import math
import os
import re
import time
from typing import Callable, Optional, Protocol, Sequence

from src.applications.calibration.service.i_calibration_service import ICalibrationService
from src.engine.core.i_coordinate_transformer import ICoordinateTransformer
from src.engine.vision.i_vision_service import IVisionService

_logger = logging.getLogger(__name__)

_DEFAULT_VELOCITY     = 30
_DEFAULT_ACCELERATION = 10


_GRID_LABEL_RE = re.compile(r"^r(\d+)c(\d+)$")


def _parse_grid_label(label: str) -> tuple[int, int] | None:
    """Return zero-based (row, col) from a label like 'r3c2', or None."""
    m = _GRID_LABEL_RE.match(label)
    if m is None:
        return None
    return int(m.group(1)) - 1, int(m.group(2)) - 1


def _point_in_polygon(px: float, py: float, polygon: list[tuple[float, float]]) -> bool:
    """Ray-casting containment test for a simple polygon."""
    inside = False
    n = len(polygon)
    j = n - 1
    for i in range(n):
        xi, yi = polygon[i]
        xj, yj = polygon[j]
        if ((yi > py) != (yj > py)) and (px < (xj - xi) * (py - yi) / (yj - yi) + xi):
            inside = not inside
        j = i
    return inside


class _IProcessController(Protocol):
    def calibrate(self) -> None: ...
    def stop_calibration(self) -> None: ...


class _IRobotService(Protocol):
    def get_current_position(self) -> list: ...
    def move_ptp(self, position, tool, user, velocity, acceleration, wait_to_reach=False) -> bool: ...
    def stop_motion(self) -> bool: ...
    def validate_pose(
        self,
        start_position,
        target_position,
        tool: int = 0,
        user: int = 0,
        start_joint_state: dict | None = None,
    ) -> dict: ...
    def enable_safety_walls(self) -> bool: ...
    def disable_safety_walls(self) -> bool: ...
    def are_safety_walls_enabled(self) -> Optional[bool]: ...


class _IHeightService(Protocol):
    def is_calibrated(self) -> bool: ...
    def measure_at(self, x: float, y: float, *, already_at_xy: bool = False) -> Optional[float]: ...
    def save_height_map(
        self,
        samples: list[list[float]],
        marker_ids: Optional[list[int]] = None,
        point_labels: Optional[list[str]] = None,
        grid_rows: int = 0,
        grid_cols: int = 0,
        planned_points: Optional[list[list[float]]] = None,
        planned_point_labels: Optional[list[str]] = None,
        unavailable_point_labels: Optional[list[str]] = None,
    ) -> None: ...
    def get_depth_map_data(self): ...


class _IRobotConfig(Protocol):
    robot_tool: int
    robot_user: int


class _ICalibConfig(Protocol):
    required_ids: list
    z_target: int
    velocity: int
    acceleration: int


class _ICameraTcpOffsetCalibrator(Protocol):
    def calibrate(self) -> tuple[bool, str]: ...

    def stop(self) -> None: ...


class _IMarkerHeightMappingService(Protocol):
    def measure_marker_heights(self) -> tuple[bool, str]: ...
    def generate_area_grid(
        self,
        corners_norm: Sequence[tuple[float, float]],
        rows: int,
        cols: int,
    ) -> list[tuple[float, float]]: ...
    def measure_area_grid(
        self,
        corners_norm: Sequence[tuple[float, float]],
        rows: int,
        cols: int,
        support_points_mm: list[tuple[str, float, float]] | None = None,
        skip_labels: set[str] | None = None,
    ) -> tuple[bool, str]: ...
    def verify_height_model(self) -> tuple[bool, str]: ...
    def stop(self) -> None: ...
    def is_ready(self) -> bool: ...


class CalibrationApplicationService(ICalibrationService):

    def __init__(self, vision_service: IVisionService, process_controller: _IProcessController,
                 robot_service: _IRobotService = None, height_service: _IHeightService = None,
                 robot_config: _IRobotConfig = None, calib_config: _ICalibConfig = None,
                 transformer: ICoordinateTransformer = None,
                 camera_tcp_offset_calibrator: Optional[_ICameraTcpOffsetCalibrator] = None,
                 marker_height_mapping_service: Optional[_IMarkerHeightMappingService] = None,
                 use_marker_centre: bool = False):
        self._vision_service      = vision_service
        self._process_controller  = process_controller
        self._robot_service       = robot_service
        self._height_service      = height_service
        self._robot_config        = robot_config
        self._calib_config        = calib_config
        self._transformer         = transformer
        self._camera_tcp_offset_calibrator = camera_tcp_offset_calibrator
        self._marker_height_mapping_service = marker_height_mapping_service
        self._use_marker_centre   = use_marker_centre
        self._stop_test           = False
        self._pending_support_points_mm: list[tuple[str, float, float]] = []
        self._pending_skip_labels: set[str] = set()

    # ── Helpers ───────────────────────────────────────────────────────

    def _robot_tool(self) -> int:
        return self._robot_config.robot_tool if self._robot_config else 0

    def _robot_user(self) -> int:
        return self._robot_config.robot_user if self._robot_config else 0

    def _required_ids(self) -> set | None:
        if self._calib_config is None:
            return None
        return set(self._calib_config.required_ids)

    def _movement_velocity(self) -> int:
        if self._calib_config is None:
            return _DEFAULT_VELOCITY
        return self._calib_config.velocity

    def _movement_acceleration(self) -> int:
        if self._calib_config is None:
            return _DEFAULT_ACCELERATION
        return self._calib_config.acceleration

    # ── ICalibrationService ───────────────────────────────────────────

    def capture_calibration_image(self) -> tuple[bool, str]:
        return self._vision_service.capture_calibration_image()

    def calibrate_camera(self) -> tuple[bool, str]:
        return self._vision_service.calibrate_camera()

    def calibrate_robot(self) -> tuple[bool, str]:
        self._process_controller.calibrate()
        return True, "Robot calibration started"

    def calibrate_camera_and_robot(self) -> tuple[bool, str]:
        ok, msg = self.calibrate_camera()
        if not ok:
            return False, f"Camera calibration failed: {msg}"
        self._process_controller.calibrate()
        return True, "Camera calibrated — robot calibration started"

    def calibrate_camera_tcp_offset(self) -> tuple[bool, str]:
        if not self.is_calibrated():
            return False, "System not calibrated — run robot calibration first"
        if self._camera_tcp_offset_calibrator is None:
            return False, "Camera TCP offset calibration is not configured"
        return self._camera_tcp_offset_calibrator.calibrate()

    def stop_calibration(self) -> None:
        self._process_controller.stop_calibration()
        if self._camera_tcp_offset_calibrator is not None:
            self._camera_tcp_offset_calibrator.stop()
        if self._marker_height_mapping_service is not None:
            self._marker_height_mapping_service.stop()

    def is_calibrated(self) -> bool:
        if self._vision_service is None:
            return False
        robot_matrix = self._vision_service.camera_to_robot_matrix_path
        storage_dir = os.path.dirname(robot_matrix)
        camera_matrix = os.path.join(storage_dir, "camera_calibration.npz")
        return os.path.isfile(robot_matrix) and os.path.isfile(camera_matrix)

    def test_calibration(self) -> tuple[bool, str]:
        self._stop_test = False

        if self._vision_service is None:
            return False, "Vision service unavailable"
        if self._robot_service is None:
            return False, "Robot service unavailable"

        frame = self._vision_service.get_latest_frame()
        if frame is None:
            return False, "No camera frame available"

        corners, ids, _ = self._vision_service.detect_aruco_markers(frame)
        if ids is None or len(ids) == 0:
            return False, "No ArUco markers detected in current frame"

        if self._transformer is not None:
            self._transformer.reload()

        if self._transformer is None or not self._transformer.is_available():
            return False, "System not calibrated — run calibration first"

        current_pos = self._robot_service.get_current_position()
        if not current_pos or len(current_pos) < 6:
            return False, "Failed to get current robot position"

        rx, ry, rz = current_pos[3], current_pos[4], current_pos[5]
        required = self._required_ids()
        tool     = self._robot_tool()
        user     = self._robot_user()
        velocity = self._movement_velocity()
        accel    = self._movement_acceleration()
        z_target = self._calib_config.z_target if self._calib_config else 300

        _logger.info(
            "test_calibration: tool=%d user=%d vel=%d acc=%d z=%d required=%s",
            tool, user, velocity, accel, z_target, required,
        )

        # Sort detections by marker ID (smallest → largest)
        sorted_pairs = sorted(zip(ids.flatten(), corners), key=lambda p: int(p[0]))

        moved = 0
        for marker_id, marker_corners in sorted_pairs:
            if self._stop_test:
                return True, f"Test stopped — moved to {moved}/{len(ids)} marker(s)"

            if required is not None and int(marker_id) not in required:
                _logger.debug("Skipping marker %d — not in required_ids", marker_id)
                continue

            # Use marker centre (mean of 4 corners) or top-left corner (index 0)
            # depending on how the homography was computed.
            if self._use_marker_centre:
                px, py = marker_corners[0].mean(axis=0)
            else:
                px, py = marker_corners[0][0]
            x_mm, y_mm = self._transformer.transform(float(px), float(py))

            _logger.info("Moving to marker %d: (%.2f, %.2f) mm", marker_id, x_mm, y_mm)
            ok = self._robot_service.move_ptp(
                position=[x_mm, y_mm, z_target, rx, ry, rz],
                tool=tool,
                user=user,
                velocity=velocity,
                acceleration=accel,
                wait_to_reach=True,
            )
            if not ok:
                return False, f"Move to marker {marker_id} failed"
            moved += 1
            time.sleep(1)

        return True, f"Test complete — moved to {moved} marker(s)"

    def stop_test_calibration(self) -> None:
        self._stop_test = True

    def measure_marker_heights(self) -> tuple[bool, str]:
        if not self.is_calibrated():
            return False, "System not calibrated — run robot calibration first"
        if self._marker_height_mapping_service is None:
            return False, "Marker height mapping is not configured"
        return self._marker_height_mapping_service.measure_marker_heights()

    def generate_area_grid(
        self,
        corners_norm: Sequence[tuple[float, float]],
        rows: int,
        cols: int,
    ) -> list[tuple[float, float]]:
        if self._marker_height_mapping_service is None:
            return []
        return self._marker_height_mapping_service.generate_area_grid(corners_norm, rows, cols)

    def measure_area_grid(
        self,
        corners_norm: Sequence[tuple[float, float]],
        rows: int,
        cols: int,
    ) -> tuple[bool, str]:
        if not self.is_calibrated():
            return False, "System not calibrated — run robot calibration first"
        if self._marker_height_mapping_service is None:
            return False, "Area grid height mapping is not configured"
        support = list(self._pending_support_points_mm)
        skip = set(self._pending_skip_labels)
        if support:
            _logger.info(
                "measure_area_grid: injecting %d support point(s) from last verification: %s",
                len(support),
                [lbl for lbl, _, _ in support],
            )
        if skip:
            _logger.info(
                "measure_area_grid: pre-skipping %d known-unreachable point(s): %s",
                len(skip), sorted(skip),
            )
        return self._marker_height_mapping_service.measure_area_grid(
            corners_norm, rows, cols,
            support_points_mm=support or None,
            skip_labels=skip or None,
        )

    def verify_area_grid(
        self,
        corners_norm: Sequence[tuple[float, float]],
        rows: int,
        cols: int,
        progress_callback: Callable[[str, str, int, int], None] | None = None,
    ) -> tuple[bool, str, dict]:
        if not self.is_calibrated():
            return False, "System not calibrated — run robot calibration first", {}
        if self._robot_service is None:
            return False, "Robot service unavailable", {}
        if self._height_service is None or not self._height_service.is_calibrated():
            return False, "Height measuring is not calibrated", {}
        if self._transformer is None:
            return False, "Homography transformer unavailable", {}
        if rows < 2 or cols < 2:
            return False, "Grid rows and cols must both be at least 2", {}
        if len(corners_norm) != 4:
            return False, "Exactly 4 area corners are required", {}

        self._transformer.reload()
        if not self._transformer.is_available():
            return False, "System not calibrated — run robot calibration first", {}

        points = self.generate_area_grid(corners_norm, rows, cols)
        if not points:
            return False, "Failed to generate area grid points", {}

        calib = self._height_service.get_calibration_data()
        if calib is None or not getattr(calib, "robot_initial_position", None):
            return False, "Height measurement calibration pose is unavailable", {}

        ref = list(calib.robot_initial_position)
        pose_suffix = [float(ref[2]), float(ref[3]), float(ref[4]), float(ref[5])]
        current = self._robot_service.get_current_position()
        if not current or len(current) < 6:
            return False, "Failed to get current robot position", {}

        anchor_state = None
        point_states = []
        width = float(self._vision_service.get_camera_width())
        height = float(self._vision_service.get_camera_height())
        for index, (xn, yn) in enumerate(points):
            row_idx = index // cols
            col_idx = index % cols
            px = xn * width
            py = yn * height
            x_mm, y_mm = self._transformer.transform(float(px), float(py))
            state = [float(x_mm), float(y_mm), *pose_suffix]
            label = f"r{row_idx + 1}c{col_idx + 1}"
            point_states.append((label, state))
            if anchor_state is None:
                anchor_state = state

        area_corners_robot_xy: list[tuple[float, float]] = [
            self._transformer.transform(float(xn * width), float(yn * height))
            for xn, yn in corners_norm
        ]
        existing_grid_xy = [(float(s[0]), float(s[1])) for _, s in point_states]
        # label → list of normalised pixel coords (one entry per support point found)
        substitutes: dict[str, list[tuple[float, float]]] = {}
        substitute_polygons: dict[str, list[tuple[float, float]]] = {}
        # label → list of robot XY (one entry per support point found)
        substitute_robot_xy: dict[str, list[tuple[float, float]]] = {}

        simulated_state = [
            float(current[0]),
            float(current[1]),
            float(current[2]),
            float(current[3]),
            float(current[4]),
            float(current[5]),
        ]
        tool = self._robot_tool()
        user = self._robot_user()
        unreachable_labels: list[str] = []
        via_anchor_labels: list[str] = []
        reachable_labels: list[str] = []
        walls_were_enabled = False
        validation_cache: dict[tuple[tuple[float, ...], tuple[float, ...]], dict] = {}
        state_joint_seeds: dict[tuple[float, ...], dict] = {}

        def _state_key(state: Sequence[float]) -> tuple[float, ...]:
            return tuple(round(float(v), 3) for v in state[:6])

        def _is_same_state(a: Sequence[float], b: Sequence[float]) -> bool:
            return _state_key(a) == _state_key(b)

        def _validate_cached(
            start_state: Sequence[float],
            target_state: Sequence[float],
            start_joint_state: dict | None = None,
        ) -> dict:
            if _is_same_state(start_state, target_state):
                return {
                    "reachable": True,
                    "reason": "same_state",
                    "target_joint_state": (
                        state_joint_seeds.get(_state_key(start_state)) or start_joint_state
                    ),
                }
            cache_key = (_state_key(start_state), _state_key(target_state))
            cached = validation_cache.get(cache_key)
            if cached is not None:
                return cached
            result = self._robot_service.validate_pose(
                list(start_state),
                list(target_state),
                tool=tool,
                user=user,
                start_joint_state=start_joint_state or state_joint_seeds.get(_state_key(start_state)),
            )
            if bool(result.get("reachable")) and isinstance(result.get("target_joint_state"), dict):
                state_joint_seeds[_state_key(target_state)] = result["target_joint_state"]
            validation_cache[cache_key] = result
            return result

        try:
            walls_enabled = self._robot_service.are_safety_walls_enabled()
            walls_were_enabled = bool(walls_enabled)
            if walls_were_enabled and not self._robot_service.disable_safety_walls():
                return False, "Failed to disable safety walls before grid verification", {}

            total = len(point_states)
            anchor_joint_seed: dict | None = None
            if anchor_state is None:
                return False, "Failed to determine grid anchor point", {}

            to_anchor = _validate_cached(simulated_state, anchor_state, None)
            if not bool(to_anchor.get("reachable")):
                return False, "Current pose cannot reach the grid anchor point", {
                    "reachable_labels": [],
                    "direct_labels": [],
                    "via_anchor_labels": [],
                    "unreachable_labels": [label for label, _ in point_states],
                }
            anchor_joint_seed = to_anchor.get("target_joint_state")
            state_joint_seeds[_state_key(anchor_state)] = anchor_joint_seed

            for index, (label, target_state) in enumerate(point_states, start=1):
                if _is_same_state(anchor_state, target_state):
                    status = "direct"
                    reachable_labels.append(label)
                else:
                    result = _validate_cached(anchor_state, target_state, anchor_joint_seed)
                    if bool(result.get("reachable")):
                        status = "direct"
                        reachable_labels.append(label)
                    else:
                        status = "unreachable"
                        unreachable_labels.append(label)
                        sub_results = self.find_substitute_points(
                            unreachable_xy=(float(target_state[0]), float(target_state[1])),
                            unreachable_label=label,
                            point_states=point_states,
                            area_corners_robot_xy=area_corners_robot_xy,
                            existing_grid_xy=existing_grid_xy,
                            pose_suffix=pose_suffix,
                            anchor_state=anchor_state,
                            anchor_joint_seed=anchor_joint_seed,
                            tool=tool,
                            user=user,
                        )
                        if sub_results:
                            ux, uy = float(target_state[0]), float(target_state[1])
                            subs_norm: list[tuple[float, float]] = []
                            subs_xy: list[tuple[float, float]] = []
                            for i, (sub_x, sub_y, search_r) in enumerate(sub_results):
                                subs_xy.append((sub_x, sub_y))
                                try:
                                    sub_px, sub_py = self._transformer.inverse_transform(sub_x, sub_y)
                                    subs_norm.append((sub_px / width, sub_py / height))
                                except Exception:
                                    subs_norm.append((-1.0, -1.0))
                                n_pts = 24
                                poly_norm = []
                                for k in range(n_pts):
                                    angle = 2 * math.pi * k / n_pts
                                    try:
                                        cpx, cpy = self._transformer.inverse_transform(
                                            ux + search_r * math.cos(angle),
                                            uy + search_r * math.sin(angle),
                                        )
                                        poly_norm.append((cpx / width, cpy / height))
                                    except Exception:
                                        pass
                                if poly_norm:
                                    substitute_polygons[f"{label}_{i}"] = poly_norm
                            substitutes[label] = subs_norm
                            substitute_robot_xy[label] = subs_xy
                if progress_callback is not None:
                    progress_callback(label, status, index, total)
        finally:
            if walls_were_enabled:
                self._robot_service.enable_safety_walls()

        point_robot_xy: dict[str, tuple[float, float]] = {
            label: (float(state[0]), float(state[1])) for label, state in point_states
        }

        self._pending_support_points_mm = [
            (f"{lbl}_support_{i}", float(sx), float(sy))
            for lbl, pts in substitute_robot_xy.items()
            for i, (sx, sy) in enumerate(pts)
        ]
        self._pending_skip_labels = set(unreachable_labels)

        summary = (
            f"Grid verification complete — reachable {len(reachable_labels)}, "
            f"unreachable {len(unreachable_labels)}"
        )
        details = {
            "reachable_labels": reachable_labels,
            "direct_labels": reachable_labels,
            "via_anchor_labels": via_anchor_labels,
            "unreachable_labels": unreachable_labels,
            "substitutes": substitutes,
            "substitute_polygons": substitute_polygons,
            "point_robot_xy": point_robot_xy,
            "substitute_robot_xy": substitute_robot_xy,
        }
        return True, summary, details

    def find_substitute_points(
        self,
        unreachable_xy: tuple[float, float],
        unreachable_label: str,
        point_states: list[tuple[str, list[float]]],
        area_corners_robot_xy: list[tuple[float, float]],
        existing_grid_xy: list[tuple[float, float]],
        pose_suffix: list[float],
        anchor_state: Sequence[float],
        anchor_joint_seed: dict | None,
        tool: int,
        user: int,
        max_substitutes: int = 2,
        step_mm: float = 10.0,
        max_radius_mm: float = 150.0,
    ) -> list[tuple[float, float, float]]:
        """Find up to *max_substitutes* reachable support points near an unreachable grid point.

        Strategy
        --------
        1. **Column search** — find the nearest same-column grid neighbour, build a
           cell-band polygon spanning that neighbour row to the unreachable row (±1 col),
           then divide the segment [neighbour → unreachable] into *max_substitutes + 1*
           equal parts and validate each interior point.
        2. **Spiral fallback** — if column search finds nothing, search outward in
           expanding rings of *step_mm* (8 angles per ring).

        In both phases the search polygon is the cell-band (when a column neighbour
        exists) so candidates can never escape past the neighbouring row.

        Returns list of (x_mm, y_mm, dist_from_unreachable_mm).
        """
        if self._robot_service is None:
            return []

        ux, uy = unreachable_xy
        min_dist_sq = (step_mm * 0.5) ** 2

        # --- helpers ---
        def _state_xy(row: int, col: int) -> tuple[float, float] | None:
            lbl = f"r{row + 1}c{col + 1}"
            for l, s in point_states:
                if l == lbl:
                    return float(s[0]), float(s[1])
            return None

        def _valid(cx: float, cy: float, poly: list[tuple[float, float]]) -> bool:
            if not _point_in_polygon(cx, cy, poly):
                return False
            if any((cx - gx) ** 2 + (cy - gy) ** 2 < min_dist_sq for gx, gy in existing_grid_xy):
                return False
            r = self._robot_service.validate_pose(
                list(anchor_state), [cx, cy, *pose_suffix],
                tool=tool, user=user, start_joint_state=anchor_joint_seed,
            )
            return bool(r.get("reachable"))

        results: list[tuple[float, float, float]] = []
        search_polygon: list[tuple[float, float]] = area_corners_robot_xy  # default

        # ── 1. Column-aligned search ──────────────────────────────────────────
        parsed_u = _parse_grid_label(unreachable_label)
        if parsed_u is not None:
            row_u, col_u = parsed_u

            same_col: list[tuple[int, int, float, float]] = []
            for lbl, state in point_states:
                p = _parse_grid_label(lbl)
                if p is None or p[1] != col_u or lbl == unreachable_label:
                    continue
                same_col.append((abs(p[0] - row_u), p[0], float(state[0]), float(state[1])))
            same_col.sort(key=lambda t: t[0])

            if same_col:
                _, row_n, nx, ny = same_col[0]  # nearest column neighbour

                # Build cell-band polygon: rows [row_n .. row_u], cols [col_u-1 .. col_u+1]
                band_pts: list[tuple[float, float]] = []
                for bc in (col_u - 1, col_u, col_u + 1):
                    for br in (row_n, row_u):
                        pt = _state_xy(br, bc)
                        if pt is not None:
                            band_pts.append(pt)
                # Deduplicate then sort by angle around centroid → convex polygon
                seen: set[tuple[float, float]] = set()
                unique_pts = [p for p in band_pts if not (p in seen or seen.add(p))]  # type: ignore[func-returns-value]
                if len(unique_pts) >= 3:
                    cx_c = sum(p[0] for p in unique_pts) / len(unique_pts)
                    cy_c = sum(p[1] for p in unique_pts) / len(unique_pts)
                    unique_pts.sort(key=lambda p: math.atan2(p[1] - cy_c, p[0] - cx_c))
                    search_polygon = unique_pts
                    _logger.debug(
                        "find_substitute_points: cell-band polygon for %s has %d vertices",
                        unreachable_label, len(unique_pts),
                    )

            for _, _row_n, nx, ny in same_col:
                if len(results) >= max_substitutes:
                    break
                remaining = max_substitutes - len(results)
                for k in range(1, remaining + 1):
                    t = k / (remaining + 1)
                    cx = nx + t * (ux - nx)
                    cy = ny + t * (uy - ny)
                    if _valid(cx, cy, search_polygon):
                        results.append((cx, cy, math.hypot(cx - ux, cy - uy)))
                if results:
                    break  # found from this neighbor — done with column phase


        return results

    def stop_marker_height_measurement(self) -> None:
        if self._marker_height_mapping_service is not None:
            self._marker_height_mapping_service.stop()

    def can_measure_marker_heights(self) -> bool:
        if not self.is_calibrated():
            return False
        if self._marker_height_mapping_service is None:
            return False
        return self._marker_height_mapping_service.is_ready()

    def verify_height_model(self) -> tuple[bool, str]:
        if self._marker_height_mapping_service is None:
            return False, "Marker height mapping is not configured"
        return self._marker_height_mapping_service.verify_height_model()

    def has_saved_height_model(self) -> bool:
        data = self.get_height_calibration_data()
        return bool(data is not None and data.has_data())

    def get_height_calibration_data(self):
        if self._height_service is None:
            return None
        return self._height_service.get_depth_map_data()

    def restore_pending_safety_walls(self) -> bool:
        if self._marker_height_mapping_service is None:
            return False
        restore = getattr(self._marker_height_mapping_service, "restore_pending_safety_walls", None)
        if restore is None:
            return False
        return bool(restore())
