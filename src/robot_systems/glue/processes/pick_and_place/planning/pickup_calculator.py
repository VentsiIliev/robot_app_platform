import logging
import math

from src.robot_systems.glue.processes.pick_and_place.config import PickAndPlaceConfig
from src.robot_systems.glue.processes.pick_and_place.planning.models import Position, PickupPositions

_logger = logging.getLogger(__name__)

class PickupCalculator:

    def __init__(self, config: PickAndPlaceConfig):
        self._config = config

    def calculate(
        self,
        robot_x: float,
        robot_y: float,
        workpiece_height: float,
        gripper_id: int,
        orientation: float,
    ) -> PickupPositions:
        cfg = self._config

        # 90° coordinate rotation (camera frame → robot frame)
        rx, ry = -robot_y, robot_x

        # Gripper XY offsets rotated by (rz_orientation - orientation)
        rz = cfg.rz_orientation
        angle_rad = math.radians(rz - orientation)
        cos_a, sin_a = math.cos(angle_rad), math.sin(angle_rad)
        ox = cfg.gripper_x_offset * cos_a - cfg.gripper_y_offset * sin_a
        oy = cfg.gripper_x_offset * sin_a + cfg.gripper_y_offset * cos_a

        px, py = rx + ox, ry + oy
        rz_final = rz - orientation

        z_descent = cfg.z_safe + cfg.descent_height_offset
        z_offset  = cfg.gripper_z_offsets.get(gripper_id, 0.0)
        z_pickup  = cfg.z_safe + z_offset + workpiece_height


        pickup_positions = PickupPositions(
            descent = Position(px, py, z_descent, cfg.orientation_rx, cfg.orientation_ry, rz_final),
            pickup  = Position(px, py, z_pickup,  cfg.orientation_rx, cfg.orientation_ry, rz_final),
            lift    = Position(px, py, z_descent, cfg.orientation_rx, cfg.orientation_ry, rz_final),
        )


        _logger.debug(f"Calculated pickup positions for robot ({robot_x}, {robot_y}), workpiece height {workpiece_height}, gripper {gripper_id}, orientation {orientation}: {pickup_positions}")
        return pickup_positions
