from __future__ import annotations

from src.robot_systems.glue.applications.glue_process_driver.service.i_glue_process_driver_service import (
    IGlueProcessDriverService,
)

class GlueProcessDriverService(IGlueProcessDriverService):
    def __init__(self, matching_service, job_builder, glue_process) -> None:
        self._matching = matching_service
        self._job_builder = job_builder
        self._glue_process = glue_process
        self._latest_match_result = None
        self._latest_no_match_count = 0
        self._latest_matched = []
        self._latest_unmatched = []
        self._latest_job = None
        self._selected_match_indexes = None

    def capture_and_match(self) -> dict:
        result, no_match_count, matched, unmatched = self._matching.run_matching()
        self._latest_match_result = result
        self._latest_no_match_count = no_match_count
        self._latest_matched = list(result.get("workpieces", []))
        self._latest_unmatched = list(unmatched)
        self._selected_match_indexes = None
        return {
            "result": result,
            "no_match_count": no_match_count,
            "matched_contours": list(matched),
            "unmatched_contours": list(unmatched),
        }

    def get_latest_matched_workpieces(self) -> list:
        return list(self._latest_matched)

    def get_latest_match_summary(self) -> dict:
        return {
            "matched_workpiece_count": len(self._latest_matched),
            "unmatched_contour_count": self._latest_no_match_count,
            "matched_ids": [self._get_workpiece_id(workpiece) for workpiece in self._latest_matched],
        }

    def select_matched_workpieces(self, indexes: list[int]) -> None:
        if not indexes:
            self._selected_match_indexes = []
            return
        matched_count = len(self._latest_matched)
        for index in indexes:
            if index < 0 or index >= matched_count:
                raise IndexError(index)
        self._selected_match_indexes = list(indexes)

    def build_job_from_latest_match(self):
        if self._latest_match_result is None:
            raise RuntimeError("No match result available")
        selected_workpieces = self._get_selected_workpieces()
        self._latest_job = self._job_builder.build_job(selected_workpieces)
        return self._latest_job

    def load_latest_job(self, spray_on: bool) -> None:
        if self._latest_job is None:
            raise RuntimeError("No job available")
        process_paths = self._job_builder.to_process_paths(self._latest_job)
        self._glue_process.set_paths(process_paths, spray_on=spray_on)

    def get_latest_job(self):
        return self._latest_job

    def get_latest_job_summary(self):
        if self._latest_job is None:
            return None
        selected_workpieces = self._get_selected_workpieces()
        return {
            "workpiece_count": self._latest_job.workpiece_count,
            "segment_count": self._latest_job.segment_count,
            "selected_workpiece_ids": [
                self._get_workpiece_id(workpiece) for workpiece in selected_workpieces
            ],
            "segments": [
                {
                    "workpiece_id": segment.workpiece_id,
                    "pattern_type": segment.pattern_type,
                    "segment_index": segment.segment_index,
                    "point_count": len(segment.points),
                    "first_point": list(segment.points[0]) if segment.points else None,
                    "settings": dict(segment.settings),
                }
                for segment in self._latest_job.segments
            ],
        }

    def get_process_snapshot(self):
        return self._glue_process.get_dispensing_snapshot()

    def set_manual_mode(self, enabled: bool) -> None:
        self._glue_process.set_manual_mode(enabled)

    def is_manual_mode_enabled(self) -> bool:
        return self._glue_process.is_manual_mode_enabled()

    def step_once(self):
        return self._glue_process.step_once()

    def start(self) -> None:
        self._glue_process.start()

    def pause(self) -> None:
        self._glue_process.pause()

    def resume(self) -> None:
        self._glue_process.resume()

    def stop(self) -> None:
        self._glue_process.stop()

    def reset_errors(self) -> None:
        self._glue_process.reset_errors()

    def _get_selected_workpieces(self) -> list:
        if self._selected_match_indexes is None:
            return list(self._latest_matched)
        return [self._latest_matched[index] for index in self._selected_match_indexes]

    def _get_workpiece_id(self, workpiece) -> str:
        if isinstance(workpiece, dict):
            return str(workpiece.get("workpieceId") or workpiece.get("name") or "")
        return str(getattr(workpiece, "workpieceId", "") or getattr(workpiece, "name", "") or "")
