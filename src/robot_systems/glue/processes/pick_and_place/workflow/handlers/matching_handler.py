from __future__ import annotations

from src.robot_systems.glue.processes.pick_and_place.errors import (
    PickAndPlaceErrorCode,
    PickAndPlaceErrorInfo,
    PickAndPlaceWorkflowResult,
)


def run_matching_cycle(workflow):
    try:
        workflow._context.match_attempt += 1
        workflow._context.set_stage(workflow._stage.MATCHING, "Running contour matching")
        workflow._context.current_capture_pose = None
        workflow._publish_diagnostics()
        if not workflow._checkpoint("matching.run"):
            return None, PickAndPlaceWorkflowResult.stopped("")
        result, no_match_count, _, _ = workflow._matching.run_matching()
        snapshot = workflow._matching.get_last_capture_snapshot()
        if snapshot is not None and snapshot.robot_pose is not None and len(snapshot.robot_pose) >= 6:
            workflow._context.current_capture_pose = tuple(float(v) for v in snapshot.robot_pose[:6])
    except Exception as exc:
        workflow._logger.exception("Matching failed")
        workflow._context.mark_error(
            PickAndPlaceErrorInfo(
                code=PickAndPlaceErrorCode.MATCHING_FAILED,
                stage=workflow._stage.MATCHING,
                message="Matching failed during pick-and-place",
                detail=str(exc),
            )
        )
        workflow._publish_diagnostics()
        return None, PickAndPlaceWorkflowResult.error_result(
            PickAndPlaceErrorCode.MATCHING_FAILED,
            workflow._stage.MATCHING,
            "Matching failed during pick-and-place",
            detail=str(exc),
        )

    workpieces = result.get("workpieces", [])
    orientations = result.get("orientations", [])
    selected = workflow._selection_policy.select(workpieces, orientations)

    if not selected:
        if no_match_count == 0:
            workflow._logger.warning("No contours detected — check camera and placement area")
            workflow._context.set_stage(workflow._stage.MATCHING, "No contours detected")
            workflow._publish_diagnostics()
            return None, PickAndPlaceWorkflowResult.stopped("No workpieces detected")
        workflow._logger.info("No workpieces matched — done")
        workflow._context.set_stage(workflow._stage.MATCHING, "No workpieces matched")
        workflow._publish_diagnostics()
        return None, PickAndPlaceWorkflowResult.stopped("No workpieces matched any known template")

    workflow._logger.info("Matched %d workpiece(s), %d unmatched", len(selected), no_match_count)
    if workflow._on_match_result:
        try:
            workflow._on_match_result(
                [item.workpiece for item in selected],
                [item.orientation for item in selected],
                no_match_count,
            )
        except Exception:
            workflow._logger.warning("on_match_result callback failed", exc_info=True)

    return selected, None
