import threading
import unittest
from unittest.mock import MagicMock

import numpy as np

from src.engine.vision.i_capture_snapshot_service import VisionCaptureSnapshot
from src.robot_systems.paint.component_ids import ProcessID
from src.robot_systems.paint.processes.paint.paint_process import PaintProcess
from src.robot_systems.paint.processes.paint.paint_production_service import PaintProductionService
from src.shared_contracts.events.process_events import ProcessState, ProcessTopics


def _square(size: float) -> np.ndarray:
    return np.array(
        [[[0.0, 0.0]], [[size, 0.0]], [[size, size]], [[0.0, size]]],
        dtype=np.float32,
    )


class TestPaintProductionServiceIntegration(unittest.TestCase):

    def _make_service(self):
        return PaintProductionService(
            workpiece_preparation_service=MagicMock(),
            capture_snapshot_service=MagicMock(),
            path_preparation_service=MagicMock(),
            path_executor=MagicMock(),
        )

    def test_run_once_executes_capture_prepare_plan_and_paint_flow(self):
        service = self._make_service()
        small = _square(1.0)
        large = _square(3.0)
        snapshot = VisionCaptureSnapshot(frame="frame", contours=[small, large], source="paint_process")
        service._capture_snapshot_service.capture_snapshot.return_value = snapshot
        raw_workpiece = {"id": "wp-1"}
        execution_plan = {"plan": 1}
        service._workpiece_preparation.prepare_workpiece.return_value = (raw_workpiece, "Prepared workpiece")
        service._path_preparation_service.build_execution_plan.return_value = execution_plan
        service._path_executor.execute_pickup_and_paint.return_value = (True, "Paint completed")

        ok, msg = service.run_once()

        self.assertTrue(ok)
        self.assertEqual(msg, "Prepared workpiece: Paint completed")
        service._capture_snapshot_service.capture_snapshot.assert_called_once_with(source="paint_process")
        prepared_contour, prepared_frame = service._workpiece_preparation.prepare_workpiece.call_args.args
        self.assertTrue(np.array_equal(prepared_contour, large))
        self.assertEqual(prepared_frame, "frame")
        service._path_preparation_service.build_execution_plan.assert_called_once_with(raw_workpiece)
        service._path_executor.execute_pickup_and_paint.assert_called_once_with(execution_plan)

    def test_run_once_returns_no_contour_before_preparation(self):
        service = self._make_service()
        service._capture_snapshot_service.capture_snapshot.return_value = VisionCaptureSnapshot(
            frame="frame",
            contours=[],
            source="paint_process",
        )

        ok, msg = service.run_once()

        self.assertFalse(ok)
        self.assertEqual(msg, "No usable contour detected")
        service._workpiece_preparation.prepare_workpiece.assert_not_called()
        service._path_preparation_service.build_execution_plan.assert_not_called()

    def test_run_once_returns_plan_generation_failure(self):
        service = self._make_service()
        contour = _square(2.0)
        service._capture_snapshot_service.capture_snapshot.return_value = VisionCaptureSnapshot(
            frame="frame",
            contours=[contour],
            source="paint_process",
        )
        service._workpiece_preparation.prepare_workpiece.return_value = ({"id": "wp-1"}, "Prepared workpiece")
        service._path_preparation_service.build_execution_plan.side_effect = RuntimeError("bad dxf")

        ok, msg = service.run_once()

        self.assertFalse(ok)
        self.assertEqual(msg, "Plan generation failed: bad dxf")
        service._path_executor.execute_pickup_and_paint.assert_not_called()

    def test_run_once_honors_stop_requests_and_execution_failure(self):
        service = self._make_service()
        contour = _square(2.0)
        service._capture_snapshot_service.capture_snapshot.return_value = VisionCaptureSnapshot(
            frame="frame",
            contours=[contour],
            source="paint_process",
        )
        service._workpiece_preparation.prepare_workpiece.return_value = ({"id": "wp-1"}, "Prepared workpiece")
        service._path_preparation_service.build_execution_plan.return_value = {"plan": 1}
        service._path_executor.execute_pickup_and_paint.return_value = (False, "pump fault")

        stopped, stopped_msg = service.run_once(stop_requested=lambda: True)
        failed, failed_msg = service.run_once(stop_requested=lambda: False)

        self.assertFalse(stopped)
        self.assertEqual(stopped_msg, "Paint process stopped")
        self.assertFalse(failed)
        self.assertEqual(failed_msg, "Prepared workpiece: pump fault")


class TestPaintProcessIntegration(unittest.TestCase):

    def _make_process(self, production_result):
        production_service = MagicMock()
        production_service.run_once.return_value = production_result
        messaging = MagicMock()
        process = PaintProcess(production_service=production_service, messaging=messaging)
        return process, production_service, messaging

    def test_successful_run_transitions_process_to_stopped(self):
        process, production_service, messaging = self._make_process((True, "Paint completed"))
        published = []
        stop_seen = threading.Event()

        def _publish(topic, event):
            published.append((topic, event))
            if topic == ProcessTopics.state(ProcessID.MAIN_PROCESS) and event.state == ProcessState.STOPPED:
                stop_seen.set()

        messaging.publish.side_effect = _publish

        process.start()
        self.assertTrue(stop_seen.wait(timeout=1.0), "paint process did not reach stopped state")
        process._thread.join(timeout=1.0)

        self.assertEqual(process.state, ProcessState.STOPPED)
        self.assertTrue(process._stopping)
        production_service.run_once.assert_called_once()
        self.assertTrue(
            any(
                topic == ProcessTopics.state(ProcessID.MAIN_PROCESS) and event.state == ProcessState.RUNNING
                for topic, event in published
            )
        )
        self.assertTrue(
            any(
                topic == ProcessTopics.state(ProcessID.MAIN_PROCESS) and event.state == ProcessState.STOPPED
                for topic, event in published
            )
        )

    def test_failed_run_transitions_process_to_error(self):
        process, production_service, messaging = self._make_process((False, "No usable contour detected"))
        error_seen = threading.Event()

        def _publish(topic, event):
            if topic == ProcessTopics.state(ProcessID.MAIN_PROCESS) and event.state == ProcessState.ERROR:
                error_seen.set()

        messaging.publish.side_effect = _publish

        process.start()
        self.assertTrue(error_seen.wait(timeout=1.0), "paint process did not reach error state")
        process._thread.join(timeout=1.0)

        self.assertEqual(process.state, ProcessState.ERROR)
        production_service.run_once.assert_called_once()

    def test_exception_and_reset_paths_update_internal_stop_flag(self):
        production_service = MagicMock()
        production_service.run_once.side_effect = RuntimeError("boom")
        process = PaintProcess(production_service=production_service, messaging=MagicMock())
        set_error = MagicMock()
        process.set_error = set_error

        process._stopping = False
        process._run_in_background()
        set_error.assert_called_once_with("boom")

        set_error.reset_mock()
        process._stopping = True
        process._run_in_background()
        set_error.assert_not_called()

        process._stopping = True
        process._on_reset_errors()
        self.assertFalse(process._stopping)


if __name__ == "__main__":
    unittest.main()
