import unittest
from unittest.mock import MagicMock

from src.robot_systems.glue.applications.glue_process_driver.model.glue_process_driver_model import (
    GlueProcessDriverModel,
)


class TestGlueProcessDriverModel(unittest.TestCase):
    def test_load_caches_initial_process_snapshot(self):
        service = MagicMock()
        service.get_process_snapshot.return_value = {"process_state": "idle", "dispensing": None}
        model = GlueProcessDriverModel(service)

        snapshot = model.load()

        self.assertEqual(snapshot["process_state"], "idle")
        self.assertEqual(model.get_process_snapshot()["process_state"], "idle")

    def test_capture_and_match_updates_match_cache(self):
        service = MagicMock()
        service.capture_and_match.return_value = {
            "result": {"workpieces": [{"workpieceId": "wp-1"}]},
            "no_match_count": 2,
            "matched_contours": [],
            "unmatched_contours": [],
        }
        service.get_latest_matched_workpieces.return_value = [{"workpieceId": "wp-1"}]
        service.get_latest_match_summary.return_value = {
            "matched_workpiece_count": 1,
            "unmatched_contour_count": 2,
            "matched_ids": ["wp-1"],
        }
        model = GlueProcessDriverModel(service)

        result = model.capture_and_match()

        self.assertEqual(result["result"]["workpieces"][0]["workpieceId"], "wp-1")
        self.assertEqual(model.get_match_summary()["matched_ids"], ["wp-1"])
        self.assertEqual(model.get_latest_matched_workpieces(), [{"workpieceId": "wp-1"}])

    def test_select_and_build_job_updates_cached_job(self):
        service = MagicMock()
        service.build_job_from_latest_match.return_value = "job-object"
        service.get_latest_job.return_value = "job-object"
        service.get_latest_job_summary.return_value = {"segment_count": 2}
        model = GlueProcessDriverModel(service)

        job = model.build_job(selected_indexes=[0, 2])

        self.assertEqual(job, "job-object")
        service.select_matched_workpieces.assert_called_once_with([0, 2])
        self.assertEqual(model.get_latest_job(), "job-object")
        self.assertEqual(model.get_latest_job_summary(), {"segment_count": 2})

    def test_process_commands_delegate_to_service(self):
        service = MagicMock()
        service.step_once.return_value = {"process_state": "running", "manual_mode": True}
        service.get_process_snapshot.return_value = {"process_state": "idle", "manual_mode": False}
        model = GlueProcessDriverModel(service)

        model.load_job(spray_on=True)
        model.set_manual_mode(True)
        snapshot = model.step_once()
        model.start()
        model.pause()
        model.resume()
        model.stop()
        model.reset_errors()

        service.load_latest_job.assert_called_once_with(spray_on=True)
        service.set_manual_mode.assert_called_once_with(True)
        service.step_once.assert_called_once_with()
        service.start.assert_called_once_with()
        service.pause.assert_called_once_with()
        service.resume.assert_called_once_with()
        service.stop.assert_called_once_with()
        service.reset_errors.assert_called_once_with()
        self.assertEqual(snapshot["manual_mode"], True)


if __name__ == "__main__":
    unittest.main()
