from __future__ import annotations

import time
import threading
from dataclasses import dataclass
from typing import Any, Literal


GlueExecutionStage = Literal["positioning", "matching", "job_build", "load", "start"]


@dataclass(frozen=True)
class GlueExecutionResult:
    success: bool
    stage: GlueExecutionStage
    message: str
    matched_ids: list[str]
    workpiece_count: int
    segment_count: int
    loaded: bool = False
    started: bool = False
    job_summary: dict[str, Any] | None = None


class GlueJobExecutionService:
    def __init__(
        self,
        matching_service,
        job_builder,
        glue_process,
        navigation_service=None,
        vision_service=None,
        robot_service=None,
        stabilization_delay_s: float = 0.5,
        sleep_fn=time.sleep,
    ) -> None:
        self._matching = matching_service
        self._job_builder = job_builder
        self._glue_process = glue_process
        self._navigation = navigation_service
        self._vision = vision_service
        self._robot = robot_service
        self._stabilization_delay_s = max(0.0, float(stabilization_delay_s))
        self._sleep = sleep_fn
        self._cancel_event = threading.Event()
        self._state_lock = threading.Lock()
        self._running = False

    def prepare_and_load(self, spray_on: bool) -> GlueExecutionResult:
        return self._prepare(spray_on=spray_on, start_after_load=False)

    def prepare_load_and_start(self, spray_on: bool) -> GlueExecutionResult:
        return self._prepare(spray_on=spray_on, start_after_load=True)

    def cancel_pending(self) -> bool:
        with self._state_lock:
            was_running = self._running
            if was_running:
                self._cancel_event.set()

        if was_running and self._robot is not None:
            try:
                self._robot.stop_motion()
            except Exception:
                pass

        return was_running

    def _prepare(self, spray_on: bool, start_after_load: bool) -> GlueExecutionResult:
        self._begin_prepare()
        try:
            positioning_error = self._move_to_capture_position()
            if positioning_error is not None:
                return GlueExecutionResult(
                    success=False,
                    stage="positioning",
                    message=positioning_error,
                    matched_ids=[],
                    workpiece_count=0,
                    segment_count=0,
                )
            cancelled = self._cancel_result("positioning")
            if cancelled is not None:
                return cancelled

            result, _no_match_count, _matched, _unmatched = self._matching.run_matching()
            workpieces = list(result.get("workpieces", [])) if isinstance(result, dict) else []
            matched_ids = [self._get_workpiece_id(workpiece) for workpiece in workpieces]

            cancelled = self._cancel_result("matching", matched_ids=matched_ids)
            if cancelled is not None:
                return cancelled

            if not workpieces:
                return GlueExecutionResult(
                    success=False,
                    stage="matching",
                    message="No matched workpieces available for glue execution",
                    matched_ids=[],
                    workpiece_count=0,
                    segment_count=0,
                )

            try:
                job = self._job_builder.build_job(workpieces)
            except Exception as exc:
                return GlueExecutionResult(
                    success=False,
                    stage="job_build",
                    message=str(exc),
                    matched_ids=matched_ids,
                    workpiece_count=len(workpieces),
                    segment_count=0,
                )

            cancelled = self._cancel_result(
                "job_build",
                matched_ids=matched_ids,
                workpiece_count=len(workpieces),
            )
            if cancelled is not None:
                return cancelled

            if getattr(job, "segment_count", 0) <= 0:
                return GlueExecutionResult(
                    success=False,
                    stage="job_build",
                    message="Glue job contains no executable segments",
                    matched_ids=matched_ids,
                    workpiece_count=len(workpieces),
                    segment_count=0,
                )

            try:
                process_paths = self._job_builder.to_process_paths(job)
                self._glue_process.set_paths(process_paths, spray_on=spray_on)
            except Exception as exc:
                return GlueExecutionResult(
                    success=False,
                    stage="load",
                    message=str(exc),
                    matched_ids=matched_ids,
                    workpiece_count=getattr(job, "workpiece_count", len(workpieces)),
                    segment_count=getattr(job, "segment_count", 0),
                    job_summary=self._build_job_summary(job),
                )

            cancelled = self._cancel_result(
                "load",
                matched_ids=matched_ids,
                workpiece_count=getattr(job, "workpiece_count", len(workpieces)),
                segment_count=getattr(job, "segment_count", 0),
                job_summary=self._build_job_summary(job),
            )
            if cancelled is not None:
                return cancelled

            if not start_after_load:
                return GlueExecutionResult(
                    success=True,
                    stage="load",
                    message="Glue job prepared and loaded",
                    matched_ids=matched_ids,
                    workpiece_count=getattr(job, "workpiece_count", len(workpieces)),
                    segment_count=getattr(job, "segment_count", 0),
                    loaded=True,
                    started=False,
                    job_summary=self._build_job_summary(job),
                )

            try:
                self._glue_process.start()
            except Exception as exc:
                return GlueExecutionResult(
                    success=False,
                    stage="start",
                    message=str(exc),
                    matched_ids=matched_ids,
                    workpiece_count=getattr(job, "workpiece_count", len(workpieces)),
                    segment_count=getattr(job, "segment_count", 0),
                    loaded=True,
                    started=False,
                    job_summary=self._build_job_summary(job),
                )

            return GlueExecutionResult(
                success=True,
                stage="start",
                message="Glue job prepared, loaded, and started",
                matched_ids=matched_ids,
                workpiece_count=getattr(job, "workpiece_count", len(workpieces)),
                segment_count=getattr(job, "segment_count", 0),
                loaded=True,
                started=True,
                job_summary=self._build_job_summary(job),
            )
        finally:
            self._finish_prepare()

    def _build_job_summary(self, job) -> dict[str, Any]:
        return {
            "workpiece_count": getattr(job, "workpiece_count", 0),
            "segment_count": getattr(job, "segment_count", 0),
            "segments": [
                {
                    "workpiece_id": segment.workpiece_id,
                    "pattern_type": segment.pattern_type,
                    "segment_index": segment.segment_index,
                    "point_count": len(segment.points),
                }
                for segment in getattr(job, "segments", [])
            ],
        }

    def _get_workpiece_id(self, workpiece: Any) -> str:
        if isinstance(workpiece, dict):
            return str(workpiece.get("workpieceId") or workpiece.get("name") or "")
        return str(getattr(workpiece, "workpieceId", "") or getattr(workpiece, "name", "") or "")

    def _move_to_capture_position(self) -> str | None:
        if self._cancel_event.is_set():
            return "Cancelled by operator"
        if self._navigation is None:
            return "Navigation service is not configured for capture positioning"
        if self._vision is None:
            return "Vision service is not configured for capture positioning"

        try:
            capture_offset = float(self._vision.get_capture_pos_offset())
        except Exception as exc:
            return f"Failed to resolve capture offset: {exc}"

        try:
            moved = bool(self._navigation.move_to_calibration_position(z_offset=capture_offset))
        except Exception as exc:
            return f"Failed to move robot to calibration capture position: {exc}"

        if self._cancel_event.is_set():
            return "Cancelled by operator"
        if not moved:
            return "Robot could not move to calibration capture position"

        if self._stabilization_delay_s > 0.0:
            remaining = self._stabilization_delay_s
            while remaining > 0.0:
                if self._cancel_event.is_set():
                    return "Cancelled by operator"
                interval = min(0.05, remaining)
                self._sleep(interval)
                remaining -= interval

        return None

    def _begin_prepare(self) -> None:
        with self._state_lock:
            self._cancel_event.clear()
            self._running = True

    def _finish_prepare(self) -> None:
        with self._state_lock:
            self._running = False
            self._cancel_event.clear()

    def _cancel_result(
        self,
        stage: GlueExecutionStage,
        *,
        matched_ids: list[str] | None = None,
        workpiece_count: int = 0,
        segment_count: int = 0,
        job_summary: dict[str, Any] | None = None,
    ) -> GlueExecutionResult | None:
        if not self._cancel_event.is_set():
            return None
        return GlueExecutionResult(
            success=False,
            stage=stage,
            message="Cancelled by operator",
            matched_ids=matched_ids or [],
            workpiece_count=workpiece_count,
            segment_count=segment_count,
            loaded=False,
            started=False,
            job_summary=job_summary,
        )
