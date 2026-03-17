from __future__ import annotations

from src.robot_systems.glue.processes.pick_and_place.errors import WorkpieceProcessResult


def finalize_placement(workflow, workpiece, prepared, placement):
    workflow._plane_mgr.advance_for_next(placement.dimensions.width)
    workflow._context.processed_count += 1
    workflow._context.update_plane(workflow._plane)
    workflow._context.last_error = None
    workflow._context.last_message = "Workpiece placed"
    workflow._publish_diagnostics()

    if workflow._on_workpiece_placed is not None:
        dims = placement.dimensions
        tgt = placement.target_position
        try:
            workflow._on_workpiece_placed(
                workpiece_name=str(getattr(workpiece, "name", "?")),
                gripper_id=int(prepared.gripper_id),
                plane_x=tgt.x,
                plane_y=tgt.y,
                width=dims.width,
                height=dims.height,
            )
        except Exception:
            workflow._logger.warning("on_workpiece_placed callback failed", exc_info=True)

    workflow._context.clear_current_workpiece()
    workflow._publish_diagnostics()
    return WorkpieceProcessResult.success()
