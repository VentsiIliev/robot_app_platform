import unittest
from unittest.mock import MagicMock

from src.robot_systems.glue.applications.glue_process_driver.service.glue_process_driver_service import (
    GlueProcessDriverService,
)


def _matched_workpiece(workpiece_id="wp-1"):
    return {
        "workpieceId": workpiece_id,
        "name": workpiece_id,
        "sprayPattern": {
            "Contour": [
                {
                    "contour": [[[1.0, 2.0]], [[3.0, 4.0]]],
                    "settings": {"glue_type": "Type A", "motor_speed": "500"},
                }
            ],
            "Fill": [],
        },
    }


class TestGlueProcessDriverService(unittest.TestCase):
    def test_capture_and_match_exposes_match_summary(self):
        matching = MagicMock()
        matching.run_matching.return_value = (
            {"workpieces": [_matched_workpiece("wp-1"), _matched_workpiece("wp-2")], "orientations": [15.0, 30.0]},
            3,
            ["matched-1", "matched-2"],
            ["unmatched-1", "unmatched-2", "unmatched-3"],
        )
        service = GlueProcessDriverService(
            matching_service=matching,
            job_builder=MagicMock(),
            glue_process=MagicMock(),
        )

        service.capture_and_match()

        summary = service.get_latest_match_summary()
        self.assertEqual(summary["matched_workpiece_count"], 2)
        self.assertEqual(summary["unmatched_contour_count"], 3)
        self.assertEqual(summary["matched_ids"], ["wp-1", "wp-2"])

    def test_capture_and_match_stores_latest_match_result(self):
        matching = MagicMock()
        matching.run_matching.return_value = (
            {"workpieces": [_matched_workpiece("wp-22")], "orientations": [15.0]},
            1,
            ["matched"],
            ["unmatched"],
        )
        builder = MagicMock()
        process = MagicMock()
        service = GlueProcessDriverService(matching_service=matching, job_builder=builder, glue_process=process)

        result = service.capture_and_match()

        self.assertEqual(result["result"]["workpieces"][0]["workpieceId"], "wp-22")
        self.assertEqual(result["no_match_count"], 1)
        self.assertEqual(service.get_latest_matched_workpieces()[0]["workpieceId"], "wp-22")

    def test_build_job_from_latest_match_uses_job_builder(self):
        matching = MagicMock()
        matching.run_matching.return_value = (
            {"workpieces": [_matched_workpiece("wp-22")]},
            0,
            [],
            [],
        )
        builder = MagicMock()
        builder.build_job.return_value = "job-object"
        process = MagicMock()
        service = GlueProcessDriverService(matching_service=matching, job_builder=builder, glue_process=process)
        service.capture_and_match()

        job = service.build_job_from_latest_match()

        self.assertEqual(job, "job-object")
        builder.build_job.assert_called_once()

    def test_load_latest_job_passes_process_ready_paths_to_glue_process(self):
        matching = MagicMock()
        builder = MagicMock()
        builder.build_job.return_value = "job-object"
        builder.to_process_paths.return_value = [([[1.0, 2.0], [3.0, 4.0]], {"glue_type": "Type A"}, {"segment_index": 0})]
        process = MagicMock()
        service = GlueProcessDriverService(matching_service=matching, job_builder=builder, glue_process=process)
        service._latest_job = "job-object"

        service.load_latest_job(spray_on=True)

        process.set_paths.assert_called_once_with(
            [([[1.0, 2.0], [3.0, 4.0]], {"glue_type": "Type A"}, {"segment_index": 0})],
            spray_on=True,
        )

    def test_get_latest_job_summary_exposes_segment_metadata(self):
        matching = MagicMock()
        matching.run_matching.return_value = (
            {"workpieces": [_matched_workpiece("wp-1"), _matched_workpiece("wp-2")]},
            0,
            [],
            [],
        )
        builder = MagicMock()
        job = MagicMock()
        job.workpiece_count = 2
        job.segment_count = 2
        job.segments = [
            MagicMock(
                workpiece_id="wp-1",
                pattern_type="Contour",
                segment_index=0,
                points=[[1.0, 2.0], [3.0, 4.0]],
                settings={"glue_type": "Type A"},
            ),
            MagicMock(
                workpiece_id="wp-2",
                pattern_type="Fill",
                segment_index=1,
                points=[[5.0, 6.0]],
                settings={"glue_type": "Type B"},
            ),
        ]
        builder.build_job.return_value = job
        service = GlueProcessDriverService(matching_service=matching, job_builder=builder, glue_process=MagicMock())
        service.capture_and_match()
        service.select_matched_workpieces([0, 1])
        service.build_job_from_latest_match()

        summary = service.get_latest_job_summary()

        self.assertEqual(summary["workpiece_count"], 2)
        self.assertEqual(summary["segment_count"], 2)
        self.assertEqual(summary["selected_workpiece_ids"], ["wp-1", "wp-2"])
        self.assertEqual(summary["segments"][0]["pattern_type"], "Contour")
        self.assertEqual(summary["segments"][1]["point_count"], 1)
        self.assertEqual(summary["segments"][0]["first_point"], [1.0, 2.0])

    def test_build_job_from_latest_match_requires_prior_match_result(self):
        service = GlueProcessDriverService(
            matching_service=MagicMock(),
            job_builder=MagicMock(),
            glue_process=MagicMock(),
        )

        with self.assertRaises(RuntimeError):
            service.build_job_from_latest_match()

    def test_select_matched_workpieces_limits_job_build_input(self):
        matching = MagicMock()
        matching.run_matching.return_value = (
            {"workpieces": [_matched_workpiece("wp-1"), _matched_workpiece("wp-2"), _matched_workpiece("wp-3")]},
            0,
            [],
            [],
        )
        builder = MagicMock()
        builder.build_job.return_value = "job-object"
        service = GlueProcessDriverService(
            matching_service=matching,
            job_builder=builder,
            glue_process=MagicMock(),
        )
        service.capture_and_match()

        service.select_matched_workpieces([1, 2])
        service.build_job_from_latest_match()

        builder.build_job.assert_called_once_with(
            [_matched_workpiece("wp-2"), _matched_workpiece("wp-3")]
        )

    def test_select_matched_workpieces_rejects_invalid_index(self):
        matching = MagicMock()
        matching.run_matching.return_value = (
            {"workpieces": [_matched_workpiece("wp-1")]},
            0,
            [],
            [],
        )
        service = GlueProcessDriverService(
            matching_service=matching,
            job_builder=MagicMock(),
            glue_process=MagicMock(),
        )
        service.capture_and_match()

        with self.assertRaises(IndexError):
            service.select_matched_workpieces([1])

    def test_process_control_methods_delegate_to_glue_process(self):
        process = MagicMock()
        process.is_manual_mode_enabled.return_value = True
        process.step_once.return_value = {"process_state": "running", "manual_mode": True}
        service = GlueProcessDriverService(
            matching_service=MagicMock(),
            job_builder=MagicMock(),
            glue_process=process,
        )

        service.set_manual_mode(True)
        service.start()
        service.pause()
        service.resume()
        service.stop()
        service.reset_errors()
        snapshot = service.step_once()

        process.set_manual_mode.assert_called_once_with(True)
        process.start.assert_called_once_with()
        process.pause.assert_called_once_with()
        process.resume.assert_called_once_with()
        process.stop.assert_called_once_with()
        process.reset_errors.assert_called_once_with()
        process.step_once.assert_called_once_with()
        self.assertEqual(snapshot["manual_mode"], True)
        self.assertTrue(service.is_manual_mode_enabled())

    def test_prepare_and_load_delegates_to_execution_service(self):
        execution_service = MagicMock()
        execution_service.prepare_and_load.return_value = {"success": True, "stage": "load"}
        service = GlueProcessDriverService(
            matching_service=MagicMock(),
            job_builder=MagicMock(),
            glue_process=MagicMock(),
            execution_service=execution_service,
        )

        result = service.prepare_and_load(spray_on=True)

        execution_service.prepare_and_load.assert_called_once_with(spray_on=True)
        self.assertEqual(result["stage"], "load")

    def test_prepare_load_and_start_delegates_to_execution_service(self):
        execution_service = MagicMock()
        execution_service.prepare_load_and_start.return_value = {"success": True, "stage": "start"}
        service = GlueProcessDriverService(
            matching_service=MagicMock(),
            job_builder=MagicMock(),
            glue_process=MagicMock(),
            execution_service=execution_service,
        )

        result = service.prepare_load_and_start(spray_on=True)

        execution_service.prepare_load_and_start.assert_called_once_with(spray_on=True)
        self.assertEqual(result["stage"], "start")

    def test_getters_expose_latest_job_and_process_snapshot(self):
        process = MagicMock()
        process.get_dispensing_snapshot.return_value = {"state": "STARTING"}
        service = GlueProcessDriverService(
            matching_service=MagicMock(),
            job_builder=MagicMock(),
            glue_process=process,
        )
        service._latest_job = "job-object"

        self.assertEqual(service.get_latest_job(), "job-object")
        self.assertEqual(service.get_process_snapshot(), {"state": "STARTING"})


if __name__ == "__main__":
    unittest.main()
