"""Paint a measured command-path prefix, then move to an inspection pose."""

from __future__ import annotations

from math import dist
from time import sleep

from src.engine.robot.motion_sequence import (
    OrderedMotionLimitProfile,
    OrderedMotionProfile,
    OrderedMotionType,
    OrderedPathCommand,
    OrderedPositionCommand,
)
from src.robot_systems.paint.processes.paint.incremental_adjustment import PaintPathCursor
from src.robot_systems.paint.processes.paint.execute.workpiece_path_executor import (
    _paint_axis_staging_offset_pose,
)


def run_incremental_paint_contact(ctx) -> tuple[bool, str]:
    """Hold after every section; only an explicit Finish proceeds to dropoff."""
    owner = ctx.production_service._path_executor
    session = ctx.adjustment_session
    paths: list[list[list[float]]] = []
    jobs = []
    ok, message, _ = owner._paint_contact.execute(
        ctx.execution_plan,
        execute_robot=False,
        append_retreat=False,
        collected_command_paths=paths,
        collected_command_jobs=jobs,
    )
    if not ok or not paths or len(paths) != len(jobs):
        session.fail()
        return False, message or "No paint-contact path was generated"
    if len(paths) != 1:
        session.fail()
        return False, "Incremental paint adjustment currently requires one paint-contact path"

    cursors = [PaintPathCursor(path) for path in paths]
    total_mm = sum(cursor.total_mm for cursor in cursors)
    travelled_mm = 0.0
    path_index = 0
    previous_axis_clear_pose = None
    session.inspection_ready(0.0, total_mm, complete=False)

    while not ctx.should_stop():
        command = session.wait_for_command(ctx.should_stop)
        if command is None:
            return False, "Paint adjustment stopped"
        action, step = command
        if action == "finish":
            return True, ""
        while not ctx.run_allowed.is_set() or ctx.control.pause_requested():
            if ctx.should_stop():
                return False, "Paint adjustment stopped"
            sleep(0.1)
        if step is None:
            session.fail()
            return False, "Paint adjustment step is missing"
        while path_index < len(cursors) and cursors[path_index].complete:
            path_index += 1
        if path_index >= len(cursors):
            session.fail()
            return False, "Paint path is already complete"

        cursor = cursors[path_index]
        before = cursor.travelled_mm
        chunk = cursor.take(step.length_mm)
        if len(chunk) < 2:
            session.fail()
            return False, "Paint section has no motion"
        axis_clear_pose = _paint_axis_staging_offset_pose(
            list(chunk[-1]),
            owner._contact_motion_config,
            paint_axis_offset_mm=step.paint_axis_offset_mm,
        )
        inspect_pose = _paint_axis_staging_offset_pose(
            list(axis_clear_pose),
            owner._contact_motion_config,
            perpendicular_axis_offset_mm=step.perpendicular_axis_offset_mm,
        )
        if dist(chunk[-1][:3], axis_clear_pose[:3]) < 1.0 - 1e-6:
            session.fail()
            return False, "Paint-axis inspection offset does not clear the contact pose"
        staging = owner._paint_process_config().contact_staging
        job = jobs[path_index]
        commands = []
        if previous_axis_clear_pose is not None:
            commands.append(OrderedPositionCommand(
                label="Adjustment return to paint-axis clearance",
                motion_type=OrderedMotionType.LINEAR,
                position=tuple(previous_axis_clear_pose),
                profile=OrderedMotionProfile(
                    velocity_percent=staging.attach_vel_percent,
                    acceleration_percent=staging.attach_acc_percent,
                    blend_radius=0.0,
                ),
            ))
        commands.extend([
            OrderedPositionCommand(
                label="Adjustment attach to paint contact",
                motion_type=OrderedMotionType.LINEAR,
                position=chunk[0],
                profile=OrderedMotionProfile(
                    velocity_percent=staging.attach_vel_percent,
                    acceleration_percent=staging.attach_acc_percent,
                    blend_radius=0.0,
                ),
            ),
            OrderedPathCommand(
                label=f"Adjustment paint section {path_index + 1}",
                path=tuple(chunk),
                profile=OrderedMotionProfile(
                    velocity_percent=job.velocity_percent,
                    acceleration_percent=job.acceleration_percent,
                    blend_radius=0.0,
                ),
                limit_profile=OrderedMotionLimitProfile.PAINT_CONTACT,
            ),
            OrderedPositionCommand(
                label="Adjustment detach along paint axis",
                motion_type=OrderedMotionType.LINEAR,
                position=tuple(axis_clear_pose),
                profile=OrderedMotionProfile(
                    velocity_percent=staging.attach_vel_percent,
                    acceleration_percent=staging.attach_acc_percent,
                    blend_radius=0.0,
                ),
            ),
        ])
        if dist(axis_clear_pose[:3], inspect_pose[:3]) > 1e-6:
            commands.append(OrderedPositionCommand(
                label="Adjustment move to camera inspection pose",
                motion_type=OrderedMotionType.LINEAR,
                position=tuple(inspect_pose),
                profile=OrderedMotionProfile(
                    velocity_percent=staging.attach_vel_percent,
                    acceleration_percent=staging.attach_acc_percent,
                    blend_radius=0.0,
                ),
            ))
        result = owner._robot_service.execute_ordered_motion_chain(
            segments=commands,
            tool=owner._pickup_tool,
            user=owner._pickup_user,
            blocking=True,
        )
        if result is False or result not in (0, True, None):
            session.fail()
            return False, owner._robot_service.get_last_motion_error() or "Paint section motion failed"
        if ctx.should_stop():
            return False, "Paint adjustment stopped"
        owner._last_process_end_pose = list(inspect_pose)
        owner._last_paint_contact_end_rz = float(chunk[-1][5])
        previous_axis_clear_pose = axis_clear_pose
        travelled_mm += cursor.travelled_mm - before
        complete = all(item.complete for item in cursors)
        session.inspection_ready(travelled_mm, total_mm, complete=complete)
    return False, "Paint adjustment stopped"
