from __future__ import annotations

from src.robot_systems.glue.processes.pick_and_place.errors import WorkpieceProcessResult


def finalize_placement(workflow, workpiece, prepared, placement):
    if not workflow._checkpoint("placement.finalize"):
        error = workflow._make_error(
            workflow._error_code.CANCELLED,
            workflow._stage.CANCELLED,
            "Pick-and-place cancelled",
        )
        workflow._context.mark_error(error)
        workflow._publish_diagnostics()
        return WorkpieceProcessResult.fail(error)
    workflow._context.set_stage(workflow._stage.PLACE, "Moving to calibration position")
    workflow._publish_diagnostics()
    if not workflow._checkpoint("placement.move_to_calibration"):
        error = workflow._make_error(
            workflow._error_code.CANCELLED,
            workflow._stage.CANCELLED,
            "Pick-and-place cancelled",
        )
        workflow._context.mark_error(error)
        workflow._publish_diagnostics()
        return WorkpieceProcessResult.fail(error)
    calibration_result = workflow._motion.move_to_calibration_position()
    if not calibration_result.success:
        workflow._context.mark_error(calibration_result.error)
        workflow._publish_diagnostics()
        return WorkpieceProcessResult.fail(calibration_result.error)

    workflow._context.set_stage(workflow._stage.PLACE, "Returning home after placement")
    workflow._publish_diagnostics()
    if not workflow._checkpoint("placement.return_home"):
        error = workflow._make_error(
            workflow._error_code.CANCELLED,
            workflow._stage.CANCELLED,
            "Pick-and-place cancelled",
        )
        workflow._context.mark_error(error)
        workflow._publish_diagnostics()
        return WorkpieceProcessResult.fail(error)
    move_home_result = workflow._motion.move_home()
    if not move_home_result.success:
        workflow._context.mark_error(move_home_result.error)
        workflow._publish_diagnostics()
        return WorkpieceProcessResult.fail(move_home_result.error)

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
