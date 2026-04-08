import numpy as np
import logging

_logger = logging.getLogger(__name__)


class CalibrationRobotController:
    def __init__(self, robot_service, navigation_service, tool: int, user: int, adaptive_movement_config,
                 velocity: int = 30, acceleration: int = 10,
                 iterative_velocity: int | None = None, iterative_acceleration: int | None = None):
        self.robot_service = robot_service
        self._navigation_service = navigation_service
        self._tool = tool
        self._user = user
        self._velocity = velocity
        self._acceleration = acceleration
        self._iterative_velocity = iterative_velocity if iterative_velocity is not None else velocity
        self._iterative_acceleration = iterative_acceleration if iterative_acceleration is not None else acceleration
        self.adaptive_movement_config = adaptive_movement_config
        self._calibration_position = None

    # ── Helpers ───────────────────────────────────────────────────────

    @staticmethod
    def _require_pose(pose, caller: str) -> list:
        if not pose or len(pose) < 6:
            raise RuntimeError(
                f"Robot position unavailable in {caller}: got {pose!r}. "
                "Is the robot connected and ready?"
            )
        return list(pose)

    # ── Motion ────────────────────────────────────────────────────────

    def move_to_position(self, position, blocking=False, velocity=None, acceleration=None):
        return self.robot_service.move_ptp(
            position=position,
            tool=self._tool,
            user=self._user,
            velocity=velocity if velocity is not None else self._velocity,
            acceleration=acceleration if acceleration is not None else self._acceleration,
            wait_to_reach=blocking,
        )

    def move_to_iterative_position(self, position, blocking=False, velocity=None, acceleration=None):
        return self.robot_service.move_ptp(
            position=position,
            tool=self._tool,
            user=self._user,
            velocity=velocity if velocity is not None else self._iterative_velocity,
            acceleration=acceleration if acceleration is not None else self._iterative_acceleration,
            wait_to_reach=blocking,
        )

    def get_iterative_align_position(self, current_error_mm, offset_x_mm, offset_y_mm, alignment_threshold_mm,
                                     preserve_current_orientation=False):
        min_step_mm        = self.adaptive_movement_config.min_step_mm
        max_step_mm        = self.adaptive_movement_config.max_step_mm
        target_error_mm    = alignment_threshold_mm
        max_error_ref      = self.adaptive_movement_config.max_error_ref
        k                  = self.adaptive_movement_config.k
        derivative_scaling = self.adaptive_movement_config.derivative_scaling

        normalized_error = min(current_error_mm / max_error_ref, 1.0)
        step_scale  = np.tanh(k * normalized_error)
        max_move_mm = min_step_mm + step_scale * (max_step_mm - min_step_mm)

        if current_error_mm < target_error_mm * 2:
            damping_ratio = (current_error_mm / (target_error_mm * 2)) ** 2
            max_move_mm *= max(damping_ratio, 0.05)

        if hasattr(self, 'previous_error_mm'):
            error_change = current_error_mm - self.previous_error_mm
            if error_change > 0:  # error increased → possible overshoot, dampen
                derivative_factor = 1.0 / (1.0 + derivative_scaling * error_change)
                max_move_mm *= derivative_factor

        self.previous_error_mm = current_error_mm

        if current_error_mm < target_error_mm * 0.5:
            max_move_mm = min_step_mm

        magnitude = np.sqrt(offset_x_mm ** 2 + offset_y_mm ** 2)
        if magnitude > max_move_mm:
            scale = max_move_mm / magnitude
        else:
            scale = 1.0   # magnitude fits within the allowed step — take the full correction
        move_x_mm = offset_x_mm * scale
        move_y_mm = offset_y_mm * scale

        _logger.debug("Adaptive movement: max_move=%.1fmm (error=%.3fmm)", max_move_mm, current_error_mm)
        _logger.debug("Making iterative movement: X+=%.3fmm, Y+=%.3fmm", move_x_mm, move_y_mm)

        raw = self.robot_service.get_current_position()
        x, y, z, rx, ry, rz = self._require_pose(raw, "get_iterative_align_position")
        if preserve_current_orientation:
            # Keep the robot's current orientation (e.g. after a TCP-capture rotation).
            return [x + move_x_mm, y + move_y_mm, z, rx, ry, rz]
        cx, cy, cz, crx, cry, crz = self._require_pose(
            self._calibration_position, "get_iterative_align_position/calibration_position"
        )
        # Preserve the original calibration orientation during fine alignment.
        return [x + move_x_mm, y + move_y_mm, z, crx, cry, crz]

    def move_to_calibration_position(self):
        if self._navigation_service:
            self._navigation_service.move_to_calibration_position()
        self._calibration_position = self.robot_service.get_current_position()
        _logger.info("Calibration position captured: %s", self._calibration_position)

    def get_current_z_value(self):
        raw = self.robot_service.get_current_position()
        pose = self._require_pose(raw, "get_current_z_value")
        _logger.info("Current Z value: %s mm", pose[2])
        return pose[2]

    def get_current_position(self):
        return self.robot_service.get_current_position()

    def get_calibration_position(self):
        return self._calibration_position

    def move_y_relative(self, dy_mm, blocking=False):
        raw = self.robot_service.get_current_position()
        x, y, z, _, _, _ = self._require_pose(raw, "move_y_relative")
        _, _, _, crx, cry, crz = self._require_pose(
            self._calibration_position, "move_y_relative/calibration_position"
        )
        return self.robot_service.move_ptp(
            position=[x, y + dy_mm, z, crx, cry, crz],
            tool=self._tool,
            user=self._user,
            velocity=self._velocity,
            acceleration=self._acceleration,
            wait_to_reach=blocking,
        )

    def move_x_relative(self, dx_mm, blocking=False):
        raw = self.robot_service.get_current_position()
        x, y, z, _, _, _ = self._require_pose(raw, "move_x_relative")
        _, _, _, crx, cry, crz = self._require_pose(
            self._calibration_position, "move_x_relative/calibration_position"
        )
        return self.robot_service.move_ptp(
            position=[x + dx_mm, y, z, crx, cry, crz],
            tool=self._tool,
            user=self._user,
            velocity=self._velocity,
            acceleration=self._acceleration,
            wait_to_reach=blocking,
        )

    def reset_derivative_state(self):
        """Clear the derivative term so the first iteration of a new marker is not wrongly damped."""
        if hasattr(self, 'previous_error_mm'):
            del self.previous_error_mm
