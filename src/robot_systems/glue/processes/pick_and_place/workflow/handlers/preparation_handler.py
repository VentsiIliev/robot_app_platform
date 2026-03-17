from __future__ import annotations

from dataclasses import dataclass

from src.engine.vision.implementation.VisionSystem.core.models.contour import Contour
from src.robot_systems.glue.processes.pick_and_place.errors import WorkpieceProcessResult
from src.robot_systems.glue.processes.pick_and_place.workflow.handlers.height_handler import (
    resolve_workpiece_height,
)
from src.robot_systems.glue.processes.pick_and_place.workflow.handlers.tooling_handler import (
    ensure_gripper_ready,
)
from src.robot_systems.glue.processes.pick_and_place.workflow.handlers.transform_handler import (
    transform_pickup_point,
)


def _parse_pickup_point(pickup_point):
    if pickup_point is None:
        return None
    if isinstance(pickup_point, str):
        try:
            x, y = pickup_point.split(",")
            return float(x), float(y)
        except (ValueError, AttributeError):
            return None
    if isinstance(pickup_point, (list, tuple)) and len(pickup_point) >= 2:
        return float(pickup_point[0]), float(pickup_point[1])
    return None


@dataclass(frozen=True)
class PreparedWorkpiece:
    contour: Contour
    gripper_id: int
    robot_x: float
    robot_y: float
    workpiece_height: float
    pickup_positions: object


def prepare_workpiece(workflow, workpiece, orientation: float):
    contour = Contour(workpiece.get_main_contour())
    gripper_id = workpiece.gripperID

    parsed = _parse_pickup_point(workpiece.pickupPoint)
    pickup_px = parsed if parsed is not None else contour.getCentroid()
    workflow._context.set_current_workpiece(
        workpiece_id=str(getattr(workpiece, "workpieceId", getattr(workpiece, "id", ""))),
        workpiece_name=str(getattr(workpiece, "name", "")),
        gripper_id=int(gripper_id),
        orientation=float(orientation),
        pickup_point_px=(float(pickup_px[0]), float(pickup_px[1])),
    )
    workflow._context.holding_gripper_id = getattr(workflow._tools, "current_gripper", None)
    workflow._publish_diagnostics("Preparing workpiece")
    if not workflow._checkpoint("preparation.begin"):
        return None, WorkpieceProcessResult.fail(
            workflow._make_error(
                workflow._error_code.CANCELLED,
                workflow._stage.CANCELLED,
                "Pick-and-place cancelled",
            )
        )

    robot_x, robot_y, transform_result = transform_pickup_point(workflow, pickup_px)
    if transform_result is not None:
        return None, transform_result

    tooling_result = ensure_gripper_ready(workflow, gripper_id)
    if tooling_result is not None:
        return None, tooling_result

    workpiece_height, height_result = resolve_workpiece_height(workflow, float(workpiece.height), robot_x, robot_y)
    if height_result is not None:
        return None, height_result

    pickup_positions = workflow._pickup_calc.calculate(
        robot_x, robot_y, workpiece_height, gripper_id, orientation
    )
    return PreparedWorkpiece(
        contour=contour,
        gripper_id=gripper_id,
        robot_x=robot_x,
        robot_y=robot_y,
        workpiece_height=workpiece_height,
        pickup_positions=pickup_positions,
    ), None
