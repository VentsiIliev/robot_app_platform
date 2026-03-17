import unittest
import threading
from unittest.mock import MagicMock

import numpy as np

from src.robot_systems.glue.domain.glue_job_execution_service import (
    GlueExecutionResult,
    GlueJobExecutionService,
)
from src.robot_systems.glue.domain.glue_job_builder_service import GlueJob, GlueJobSegment
from src.shared_contracts.events.glue_overlay_events import GlueOverlayJobLoadedEvent, GlueOverlayTopics


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


def _job() -> GlueJob:
    return GlueJob(
        segments=[
            GlueJobSegment(
                workpiece_id="wp-1",
                pattern_type="Contour",
                segment_index=0,
                points=[[10.0, 20.0, 30.0, 180.0, 0.0, 0.0]],
                image_points=[(1.0, 2.0), (3.0, 4.0)],
                settings={"glue_type": "Type A", "motor_speed": "500"},
            )
        ]
    )


class TestGlueJobExecutionService(unittest.TestCase):
    def test_cancel_pending_stops_robot_when_prepare_running(self):
        matching = MagicMock()
        start_wait = threading.Event()
        release_wait = threading.Event()

        def _run_matching():
            start_wait.set()
            release_wait.wait(timeout=1.0)
            return ({}, 0, [], [])

        matching.run_matching.side_effect = _run_matching
        builder = MagicMock()
        glue_process = MagicMock()
        robot = MagicMock()
        navigation = MagicMock()
        navigation.move_to_calibration_position.return_value = True
        vision = MagicMock()
        vision.get_capture_pos_offset.return_value = -4.0
        service = GlueJobExecutionService(
            matching,
            builder,
            glue_process,
            navigation_service=navigation,
            vision_service=vision,
            robot_service=robot,
            sleep_fn=lambda _seconds: None,
        )

        result_holder = {}

        def _run():
            result_holder["result"] = service.prepare_and_load(spray_on=True)

        thread = threading.Thread(target=_run)
        thread.start()
        self.assertTrue(start_wait.wait(timeout=1.0))

        self.assertTrue(service.cancel_pending())
        release_wait.set()
        thread.join(timeout=1.0)

        robot.stop_motion.assert_called_once_with()
        self.assertEqual(result_holder["result"].stage, "matching")
        self.assertEqual(result_holder["result"].message, "Cancelled by operator")

    def test_prepare_and_load_fails_when_robot_cannot_reach_capture_position(self):
        matching = MagicMock()
        builder = MagicMock()
        glue_process = MagicMock()
        navigation = MagicMock()
        navigation.move_to_calibration_position.return_value = False
        vision = MagicMock()
        vision.get_capture_pos_offset.return_value = -4.0

        service = GlueJobExecutionService(
            matching,
            builder,
            glue_process,
            navigation_service=navigation,
            vision_service=vision,
            sleep_fn=lambda _seconds: None,
        )

        result = service.prepare_and_load(spray_on=True)

        self.assertFalse(result.success)
        self.assertEqual(result.stage, "positioning")
        self.assertEqual(result.message, "Robot could not move to calibration capture position")
        matching.run_matching.assert_not_called()
        builder.build_job.assert_not_called()
        glue_process.set_paths.assert_not_called()

    def test_prepare_and_load_moves_to_capture_position_and_waits_before_matching(self):
        matching = MagicMock()
        matching.run_matching.return_value = (
            {"workpieces": [_matched_workpiece("wp-1")]},
            0,
            [],
            [],
        )
        builder = MagicMock()
        builder.build_job.return_value = _job()
        builder.to_process_paths.return_value = [
            ([[10.0, 20.0, 30.0, 180.0, 0.0, 0.0]], {"glue_type": "Type A"}, {"segment_index": 0})
        ]
        glue_process = MagicMock()
        navigation = MagicMock()
        navigation.move_to_calibration_position.return_value = True
        vision = MagicMock()
        vision.get_capture_pos_offset.return_value = -4.0
        slept = []

        service = GlueJobExecutionService(
            matching,
            builder,
            glue_process,
            navigation_service=navigation,
            vision_service=vision,
            stabilization_delay_s=0.25,
            sleep_fn=lambda seconds: slept.append(seconds),
        )

        result = service.prepare_and_load(spray_on=True)

        self.assertTrue(result.success)
        navigation.move_to_calibration_position.assert_called_once()
        _, kwargs = navigation.move_to_calibration_position.call_args
        self.assertEqual(kwargs["z_offset"], -4.0)
        self.assertTrue(callable(kwargs["wait_cancelled"]))
        self.assertAlmostEqual(sum(slept), 0.25, places=6)
        matching.run_matching.assert_called_once_with()

    def test_prepare_and_load_publishes_overlay_snapshot_when_job_loads(self):
        matching = MagicMock()
        matching.run_matching.return_value = (
            {"workpieces": [_matched_workpiece("wp-1")]},
            0,
            [],
            [],
        )
        builder = MagicMock()
        builder.build_job.return_value = _job()
        builder.to_process_paths.return_value = [
            ([[10.0, 20.0, 30.0, 180.0, 0.0, 0.0]], {"glue_type": "Type A"}, {"segment_index": 0})
        ]
        glue_process = MagicMock()
        navigation = MagicMock()
        navigation.move_to_calibration_position.return_value = True
        vision = MagicMock()
        vision.get_capture_pos_offset.return_value = -4.0
        vision.get_latest_frame.return_value = np.zeros((120, 160, 3), dtype=np.uint8)
        messaging = MagicMock()

        service = GlueJobExecutionService(
            matching,
            builder,
            glue_process,
            navigation_service=navigation,
            vision_service=vision,
            messaging_service=messaging,
            sleep_fn=lambda _seconds: None,
        )

        result = service.prepare_and_load(spray_on=True)

        self.assertTrue(result.success)
        messaging.publish.assert_called_once()
        topic, event = messaging.publish.call_args[0]
        self.assertEqual(topic, GlueOverlayTopics.JOB_LOADED)
        self.assertIsInstance(event, GlueOverlayJobLoadedEvent)
        self.assertEqual(event.image_width, 160)
        self.assertEqual(event.image_height, 120)
        self.assertEqual(event.segments[0].points, [(1.0, 2.0), (3.0, 4.0)])

    def test_prepare_and_load_returns_cancelled_when_cancelled_during_stabilization(self):
        matching = MagicMock()
        builder = MagicMock()
        glue_process = MagicMock()
        navigation = MagicMock()
        navigation.move_to_calibration_position.return_value = True
        vision = MagicMock()
        vision.get_capture_pos_offset.return_value = -4.0
        service = GlueJobExecutionService(
            matching,
            builder,
            glue_process,
            navigation_service=navigation,
            vision_service=vision,
            sleep_fn=lambda _seconds: service.cancel_pending(),
        )

        result = service.prepare_and_load(spray_on=True)

        self.assertFalse(result.success)
        self.assertEqual(result.stage, "positioning")
        self.assertEqual(result.message, "Cancelled by operator")
        matching.run_matching.assert_not_called()

    def test_prepare_and_load_returns_cancelled_when_navigation_wait_is_cancelled(self):
        matching = MagicMock()
        builder = MagicMock()
        glue_process = MagicMock()
        vision = MagicMock()
        vision.get_capture_pos_offset.return_value = -4.0
        robot = MagicMock()

        def _move_to_calibration_position(*, z_offset, wait_cancelled):
            self.assertEqual(z_offset, -4.0)
            service.cancel_pending()
            self.assertTrue(wait_cancelled())
            return False

        navigation = MagicMock()
        navigation.move_to_calibration_position.side_effect = _move_to_calibration_position
        service = GlueJobExecutionService(
            matching,
            builder,
            glue_process,
            navigation_service=navigation,
            vision_service=vision,
            robot_service=robot,
            sleep_fn=lambda _seconds: None,
        )

        result = service.prepare_and_load(spray_on=True)

        self.assertFalse(result.success)
        self.assertEqual(result.stage, "positioning")
        self.assertEqual(result.message, "Cancelled by operator")
        robot.stop_motion.assert_called()
        matching.run_matching.assert_not_called()

    def test_prepare_and_load_fails_when_no_workpieces_match(self):
        matching = MagicMock()
        matching.run_matching.return_value = ({}, 0, [], [])
        service = GlueJobExecutionService(
            matching,
            MagicMock(),
            MagicMock(),
            navigation_service=MagicMock(move_to_calibration_position=MagicMock(return_value=True)),
            vision_service=MagicMock(get_capture_pos_offset=MagicMock(return_value=-4.0)),
            sleep_fn=lambda _seconds: None,
        )

        result = service.prepare_and_load(spray_on=True)

        self.assertIsInstance(result, GlueExecutionResult)
        self.assertFalse(result.success)
        self.assertEqual(result.stage, "matching")
        self.assertEqual(result.workpiece_count, 0)
        self.assertEqual(result.segment_count, 0)

    def test_prepare_and_load_fails_when_job_build_raises(self):
        matching = MagicMock()
        matching.run_matching.return_value = (
            {"workpieces": [_matched_workpiece("wp-1")]},
            0,
            [],
            [],
        )
        builder = MagicMock()
        builder.build_job.side_effect = ValueError("transformer unavailable")
        service = GlueJobExecutionService(
            matching,
            builder,
            MagicMock(),
            navigation_service=MagicMock(move_to_calibration_position=MagicMock(return_value=True)),
            vision_service=MagicMock(get_capture_pos_offset=MagicMock(return_value=-4.0)),
            sleep_fn=lambda _seconds: None,
        )

        result = service.prepare_and_load(spray_on=True)

        self.assertFalse(result.success)
        self.assertEqual(result.stage, "job_build")
        self.assertEqual(result.message, "transformer unavailable")
        self.assertEqual(result.matched_ids, ["wp-1"])

    def test_prepare_and_load_fails_when_built_job_has_no_segments(self):
        matching = MagicMock()
        matching.run_matching.return_value = (
            {"workpieces": [_matched_workpiece("wp-1")]},
            0,
            [],
            [],
        )
        builder = MagicMock()
        builder.build_job.return_value = GlueJob(segments=[])
        service = GlueJobExecutionService(
            matching,
            builder,
            MagicMock(),
            navigation_service=MagicMock(move_to_calibration_position=MagicMock(return_value=True)),
            vision_service=MagicMock(get_capture_pos_offset=MagicMock(return_value=-4.0)),
            sleep_fn=lambda _seconds: None,
        )

        result = service.prepare_and_load(spray_on=True)

        self.assertFalse(result.success)
        self.assertEqual(result.stage, "job_build")
        self.assertEqual(result.segment_count, 0)

    def test_prepare_and_load_sets_paths_and_returns_loaded_result(self):
        matching = MagicMock()
        matching.run_matching.return_value = (
            {"workpieces": [_matched_workpiece("wp-1")]},
            0,
            [],
            [],
        )
        builder = MagicMock()
        builder.build_job.return_value = _job()
        builder.to_process_paths.return_value = [
            ([[10.0, 20.0, 30.0, 180.0, 0.0, 0.0]], {"glue_type": "Type A"}, {"segment_index": 0})
        ]
        glue_process = MagicMock()
        service = GlueJobExecutionService(
            matching,
            builder,
            glue_process,
            navigation_service=MagicMock(move_to_calibration_position=MagicMock(return_value=True)),
            vision_service=MagicMock(get_capture_pos_offset=MagicMock(return_value=-4.0)),
            sleep_fn=lambda _seconds: None,
        )

        result = service.prepare_and_load(spray_on=False)

        self.assertTrue(result.success)
        self.assertEqual(result.stage, "load")
        self.assertTrue(result.loaded)
        self.assertFalse(result.started)
        glue_process.set_paths.assert_called_once_with(
            [([[10.0, 20.0, 30.0, 180.0, 0.0, 0.0]], {"glue_type": "Type A"}, {"segment_index": 0})],
            spray_on=False,
        )
        glue_process.start.assert_not_called()

    def test_prepare_load_and_start_starts_process(self):
        matching = MagicMock()
        matching.run_matching.return_value = (
            {"workpieces": [_matched_workpiece("wp-1"), _matched_workpiece("wp-2")]},
            0,
            [],
            [],
        )
        builder = MagicMock()
        builder.build_job.return_value = _job()
        builder.to_process_paths.return_value = [
            ([[10.0, 20.0, 30.0, 180.0, 0.0, 0.0]], {"glue_type": "Type A"}, {"segment_index": 0})
        ]
        glue_process = MagicMock()
        service = GlueJobExecutionService(
            matching,
            builder,
            glue_process,
            navigation_service=MagicMock(move_to_calibration_position=MagicMock(return_value=True)),
            vision_service=MagicMock(get_capture_pos_offset=MagicMock(return_value=-4.0)),
            sleep_fn=lambda _seconds: None,
        )

        result = service.prepare_load_and_start(spray_on=True)

        self.assertTrue(result.success)
        self.assertEqual(result.stage, "start")
        self.assertTrue(result.loaded)
        self.assertTrue(result.started)
        self.assertEqual(result.matched_ids, ["wp-1", "wp-2"])
        glue_process.start.assert_called_once_with()

    def test_prepare_load_and_start_returns_start_failure(self):
        matching = MagicMock()
        matching.run_matching.return_value = (
            {"workpieces": [_matched_workpiece("wp-1")]},
            0,
            [],
            [],
        )
        builder = MagicMock()
        builder.build_job.return_value = _job()
        builder.to_process_paths.return_value = [
            ([[10.0, 20.0, 30.0, 180.0, 0.0, 0.0]], {"glue_type": "Type A"}, {"segment_index": 0})
        ]
        glue_process = MagicMock()
        glue_process.start.side_effect = RuntimeError("glue already running")
        service = GlueJobExecutionService(
            matching,
            builder,
            glue_process,
            navigation_service=MagicMock(move_to_calibration_position=MagicMock(return_value=True)),
            vision_service=MagicMock(get_capture_pos_offset=MagicMock(return_value=-4.0)),
            sleep_fn=lambda _seconds: None,
        )

        result = service.prepare_load_and_start(spray_on=True)

        self.assertFalse(result.success)
        self.assertEqual(result.stage, "start")
        self.assertTrue(result.loaded)
        self.assertFalse(result.started)
        self.assertEqual(result.message, "glue already running")


if __name__ == "__main__":
    unittest.main()
