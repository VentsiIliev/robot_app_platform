import logging

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
        _logger.debug(f"Calculating pickup positions for robot ({robot_x}, {robot_y}), workpiece height {workpiece_height}, gripper {gripper_id}, orientation {orientation}")
        rz = cfg.rz_orientation
        px, py = robot_x, robot_y
        _logger.debug(
            "Pickup XY target already resolved upstream in transform stage: (%.3f, %.3f)",
            px,
            py,
        )
        rz_final = rz - orientation
        _logger.debug(f"Final rz value: {rz_final}")
        z_descent = cfg.z_safe + cfg.descent_height_offset
        _logger.debug(f"Calculated z_descent: {z_descent}")
        z_offset  = cfg.gripper_z_offsets.get(gripper_id, 0.0)
        _logger.debug(f"Calculated z_offset: {z_offset}")
        z_pickup  = cfg.z_safe + z_offset + workpiece_height
        _logger.debug(f"Calculated z_pickup: {z_pickup}")

        # temporary set rz_final to cfg.rz_orientation for pickup and descent to avoid gripper rotation during pickup, which can cause issues with vision-based height measurement
        # rz_final = cfg.rz_orientation
        # rz_final = 0
        pickup_positions = PickupPositions(
            descent = Position(px, py, z_descent, cfg.orientation_rx, cfg.orientation_ry, rz_final),
            pickup  = Position(px, py, z_pickup,  cfg.orientation_rx, cfg.orientation_ry, rz_final),
            lift    = Position(px, py, z_descent, cfg.orientation_rx, cfg.orientation_ry, rz_final),
        )


        return pickup_positions
