from __future__ import annotations

import unittest
from unittest.mock import MagicMock

from src.robot_systems.paint.processes.paint.execution_machine.state import PaintExecutionState
from src.robot_systems.paint.timing import TimingRecorder


class TestPaintTimingRecorder(unittest.TestCase):
    def test_log_summary_keeps_info_compact_and_writes_details_to_debug(self) -> None:
        recorder = TimingRecorder("paint_process")
        start = recorder.started_at
        recorder.record(
            step="paint_process",
            label=None,
            success=True,
            elapsed_s=12.0,
            started_at=start,
            ended_at=start + 12.0,
        )
        recorder.record(
            step="pickup_plan_build",
            label="project_initial_pivot_path",
            success=True,
            elapsed_s=0.2,
            started_at=start,
            ended_at=start + 0.2,
        )
        recorder.record(
            step="pickup_to_pivot",
            label=None,
            success=True,
            elapsed_s=3.0,
            started_at=start,
            ended_at=start + 3.0,
        )
        recorder.record(
            step="execute_paint_contact_paths",
            label=None,
            success=True,
            elapsed_s=7.0,
            started_at=start + 3.0,
            ended_at=start + 10.0,
        )

        logger = MagicMock()
        recorder.log_summary(logger, csv_path="/tmp/timing.csv")

        info_formats = [call.args[0] for call in logger.info.call_args_list]
        self.assertEqual(len(info_formats), 3)
        self.assertIn("total_s=%.3f", info_formats[0])
        self.assertTrue(all("order=%d" not in fmt for fmt in info_formats))
        self.assertEqual(logger.debug.call_count, 4)

    def test_log_state_summary_emits_ordered_state_table(self) -> None:
        recorder = TimingRecorder("paint_execution_cycle_1")
        start = recorder.started_at
        recorder.record_state(
            state=PaintExecutionState.STARTING,
            next_state=PaintExecutionState.CAPTURE_WORKPIECE,
            success=True,
            elapsed_s=0.1,
            started_at=start,
            ended_at=start + 0.1,
        )
        recorder.record_state(
            state=PaintExecutionState.CAPTURE_WORKPIECE,
            next_state=PaintExecutionState.ERROR,
            success=False,
            elapsed_s=0.2,
            started_at=start + 0.1,
            ended_at=start + 0.3,
            message="No usable contour detected",
        )

        logger = MagicMock()
        recorder.log_state_summary(logger)

        info_formats = [call.args[0] for call in logger.info.call_args_list]
        self.assertEqual(len(info_formats), 3)
        self.assertIn("[STATE_TIMING_SUMMARY] name=%s", info_formats[0])
        self.assertIn("state=%s next=%s", info_formats[1])
        self.assertEqual(logger.info.call_args_list[2].args[-1], "No usable contour detected")


if __name__ == "__main__":
    unittest.main()
