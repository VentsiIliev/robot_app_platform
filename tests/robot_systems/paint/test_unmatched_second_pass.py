from __future__ import annotations

import unittest
from dataclasses import replace

from src.robot_systems.paint.processes.paint.config import (
    PaintProcessConfig,
    UnmatchedSecondPassConfig,
    scale_paint_process_accelerations,
)
from src.robot_systems.paint.processes.paint.execution_machine.handlers.workflow.pickup_handler import (
    build_ordered_second_pass_segments,
)
from src.robot_systems.paint.processes.paint.paint_process_config_serializer import (
    PaintProcessConfigSerializer,
)


class TestUnmatchedSecondPass(unittest.TestCase):
    def test_process_acceleration_scale_changes_cycle_copy_only(self) -> None:
        config = replace(PaintProcessConfig(), paint_process_acceleration_scale_percent=10.0)

        scaled = scale_paint_process_accelerations(config)

        self.assertEqual(
            scaled.contact_staging.attach_acc_percent,
            config.contact_staging.attach_acc_percent * 0.1,
        )
        self.assertEqual(
            scaled.navigation_return.unwind_acc_percent,
            config.navigation_return.unwind_acc_percent * 0.1,
        )
        self.assertEqual(scaled.paint_process_acceleration_scale_percent, 10.0)
        self.assertEqual(config.contact_staging.attach_acc_percent, 5.0)

    def test_config_roundtrip_preserves_second_pass_overrides(self) -> None:
        config = replace(
            PaintProcessConfig(),
            unmatched_paint_pass_count=2,
            unmatched_second_pass=UnmatchedSecondPassConfig(
                use_pass_1_settings=False,
                velocity_percent=22.0,
                acceleration_percent=33.0,
                offset_mm=-1.5,
            ),
        )

        restored = PaintProcessConfigSerializer().from_dict(
            PaintProcessConfigSerializer().to_dict(config)
        )

        self.assertEqual(restored.unmatched_paint_pass_count, 2)
        self.assertEqual(restored.unmatched_second_pass, config.unmatched_second_pass)

    def test_second_pass_chain_unwinds_before_attach_and_contact(self) -> None:
        config = PaintProcessConfig()
        path = [[1.0, 2.0, 3.0, 0.0, 0.0, 0.0], [2.0, 2.0, 3.0, 0.0, 0.0, 5.0]]

        segments = build_ordered_second_pass_segments(
            [path], [{"vel": 21.0, "acc": 31.0, "pattern_type": "Workpiece"}], config
        )

        self.assertEqual([segment["type"] for segment in segments], ["unwind_joint6", "linear", "path"])
        self.assertTrue(segments[0]["protected"])
        self.assertEqual(segments[1]["position"], path[0])
        self.assertEqual(segments[2]["path"], path)
        self.assertEqual(segments[2]["vel"], 21.0)
        self.assertEqual(segments[1]["readiness_group"], "paint_pass_2_contact_1")
        self.assertEqual(segments[2]["execution_group"], "paint_pass_2_contact_1")


if __name__ == "__main__":
    unittest.main()
