from src.engine.vision.implementation.VisionSystem.core.models.contour import Contour
from src.robot_systems.glue.processes.pick_and_place.config import PickAndPlaceConfig
from src.robot_systems.glue.processes.pick_and_place.planning.models import (
    Position, DropOffPositions, WorkpieceDimensions, PlacementTarget,
    WorkpiecePlacement, PlacementResult,
)
from src.robot_systems.glue.processes.pick_and_place.plane import PlaneManagementService


class PlacementCalculator:

    def __init__(self, plane_mgr: PlaneManagementService, config: PickAndPlaceConfig):
        self._plane_mgr = plane_mgr
        self._config    = config

    def calculate(
        self,
        cnt_obj: Contour,
        orientation: float,
        workpiece_height: float,
        gripper_id: int,
    ) -> PlacementResult:
        contour = Contour(cnt_obj.get())
        # Align contour with X-axis for dimension measurement
        centroid = contour.getCentroid()
        contour.rotate(-orientation, centroid)

        min_rect   = contour.getMinAreaRect()
        w, h       = min_rect[1]
        if w < h:
            w, h = h, w
        bbox_center = (min_rect[0][0], min_rect[0][1])
        dims = WorkpieceDimensions(width=w, height=h, bbox_center=bbox_center)

        self._plane_mgr.update_tallest(h)

        target = self._plane_mgr.next_target(w, h)
        self._plane_mgr.handle_row_overflow(w, h, target)

        if self._plane_mgr.is_full:
            return PlacementResult(success=False, placement=None, plane_full=True, message="Plane full")

        # Translate contour to target
        tx = target.x - bbox_center[0]
        ty = target.y - bbox_center[1]
        contour.translate(tx, ty)
        new_centroid = contour.getCentroid()

        drop_off = self._build_drop_off(new_centroid, workpiece_height, gripper_id)

        placement = WorkpiecePlacement(
            dimensions=dims,
            target_position=target,
            pickup_positions=None,   # filled by PickupCalculator
            drop_off_positions=drop_off,
            pickup_height=workpiece_height,
        )
        return PlacementResult(success=True, placement=placement, plane_full=False, message="OK")

    def _build_drop_off(self, centroid, workpiece_height: float, gripper_id: int) -> DropOffPositions:
        cfg    = self._config
        z_drop = cfg.z_safe + cfg.gripper_z_offsets.get(gripper_id, 0.0) + workpiece_height
        z_app  = cfg.z_safe + cfg.descent_height_offset
        cx, cy = centroid

        return DropOffPositions(
            approach = Position(cx, cy, z_app,  cfg.orientation_rx, cfg.orientation_ry, cfg.rz_orientation),
            drop     = Position(cx, cy, z_drop, cfg.orientation_rx, cfg.orientation_ry, cfg.rz_orientation),
        )
