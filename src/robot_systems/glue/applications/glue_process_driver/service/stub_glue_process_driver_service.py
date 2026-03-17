from src.robot_systems.glue.applications.glue_process_driver.service.i_glue_process_driver_service import (
    IGlueProcessDriverService,
)


class StubGlueProcessDriverService(IGlueProcessDriverService):
    def __init__(self):
        self._snapshot = {
            "process_state": "idle",
            "manual_mode": False,
            "worker_alive": False,
            "machine": None,
            "dispensing": None,
        }
        self._summary = {"matched_workpiece_count": 0, "unmatched_contour_count": 0, "matched_ids": []}
        self._job = None
        self._manual_mode = False

    def capture_and_match(self) -> dict:
        self._summary = {
            "matched_workpiece_count": 1,
            "unmatched_contour_count": 0,
            "matched_ids": ["stub-workpiece"],
        }
        return {"result": {"workpieces": [{"workpieceId": "stub-workpiece"}]}, "no_match_count": 0, "matched_contours": [], "unmatched_contours": []}

    def get_latest_match_summary(self) -> dict:
        return dict(self._summary)

    def get_latest_matched_workpieces(self) -> list:
        return [{"workpieceId": workpiece_id} for workpiece_id in self._summary["matched_ids"]]

    def select_matched_workpieces(self, indexes: list[int]) -> None:
        return None

    def build_job_from_latest_match(self):
        self._job = "stub-job"
        return self._job

    def get_latest_job(self):
        return self._job

    def get_latest_job_summary(self):
        if self._job is None:
            return None
        return {
            "workpiece_count": 1,
            "segment_count": 1,
            "selected_workpiece_ids": ["stub-workpiece"],
            "segments": [
                {
                    "workpiece_id": "stub-workpiece",
                    "pattern_type": "Contour",
                    "segment_index": 0,
                    "point_count": 2,
                    "first_point": [100.0, 200.0, 120.0, 180.0, 0.0, 0.0],
                    "settings": {"glue_type": "Type A"},
                }
            ],
        }

    def load_latest_job(self, spray_on: bool) -> None:
        return None

    def get_process_snapshot(self):
        return dict(self._snapshot)

    def set_manual_mode(self, enabled: bool) -> None:
        self._manual_mode = bool(enabled)
        self._snapshot["manual_mode"] = self._manual_mode

    def is_manual_mode_enabled(self) -> bool:
        return self._manual_mode

    def step_once(self):
        self._snapshot = {
            **self._snapshot,
            "process_state": "running",
            "machine": {
                "initial_state": "STARTING",
                "current_state": "LOADING_PATH",
                "is_running": False,
                "step_count": 1,
                "last_state": "STARTING",
                "last_next_state": "LOADING_PATH",
                "last_error": None,
            },
        }
        return dict(self._snapshot)

    def start(self) -> None:
        self._snapshot = {**self._snapshot, "process_state": "running"}

    def pause(self) -> None:
        self._snapshot = {**self._snapshot, "process_state": "paused"}

    def resume(self) -> None:
        self._snapshot = {**self._snapshot, "process_state": "running"}

    def stop(self) -> None:
        self._snapshot = {**self._snapshot, "process_state": "stopped"}

    def reset_errors(self) -> None:
        self._snapshot = {**self._snapshot, "process_state": "idle"}
